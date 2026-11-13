"""Explicit controlled flat-memory inputs for the original raster routine."""
import hashlib
from pathlib import Path
import struct

ASSETS={
    'LEZAC.EXE':'7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec',
    'CARO.CAR':'949cce4db6071d6675a291c978d725c6e4ee1730b2c7a428bc1c8a8185cbd8d8',
    'BOMOMIMK.SPR':'08dfd0e59ba191c52af2529bdfa140fd15a57829f0c6c13bbb78e156769ac0d1',
    'BOMPAL.PAL':'f2559164074ca529ba6c275a9831b11c6da9e6317f09b3d9228c299d6f8f8319'}
SCRATCH=(0xc1e8,0xc200,0xc202,0xc210,0xc21a,0xc21c)
DATA=0x1aa20
MAP=0x30000
BUFFER=0x40010
BACKDROP=0x50020
SPRITES=0x60030
STACK=0x83fa4


def assets(root):
    files={name:(root/name).read_bytes() for name in ASSETS}
    if any(hashlib.sha256(files[name]).hexdigest()!=digest for name,digest in ASSETS.items()):
        raise ValueError('Canonical raster asset differs')
    tile_count=int.from_bytes(files['CARO.CAR'][:2],'big')
    tiles=files['CARO.CAR'][2:]
    if tile_count!=132 or len(tiles)!=tile_count*64:
        raise ValueError('Raw tile bank differs')
    raw=files['BOMOMIMK.SPR']
    descriptors=[]
    pixels=bytearray()
    at=1
    for _ in range(raw[0]):
        width,height=raw[at:at+2];at+=2
        if not width or not height:
            raise ValueError('Zero-size sprite is outside this declared corpus')
        descriptors.append((width,height,len(pixels)))
        pixels.extend(raw[at:at+width*height]);at+=width*height
    if at!=len(raw) or len(pixels)>65536:
        raise ValueError('Raw sprite bank differs')
    return files,tiles,descriptors,bytes(pixels)


def profiles():
    result=[(pitch,mode,df,0,2,7,7,48,0,22,0)
        for pitch in (320,160,168) for mode in (0,1,2) for df in (0,1)]
    result.extend(((320,1,0,65535,65530,15,7,65535,7,22,1),
        (168,1,0,0,65535,7,7,65530,65535,0,1),
        (160,255,0,1,65534,0,0,0,0,79,1),(320,0,1,65535,65535,0,0,0,0,1,1)))
    return result


def initial_memory(index,profile,loaded):
    files,tiles,descriptors,pixels=loaded
    pitch,mode,df,buffer,map_start,fine_x,fine_y,back_offset,back_gap,count,all_tiles=profile
    exe=files['LEZAC.EXE'];mz=struct.unpack_from('<14H',exe)
    image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4)
        at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    memory=bytearray(1048576)
    memory[0x10000:0x10000+len(image)]=image
    memory[DATA:DATA+65538]=bytes((i*13+(i>>5)*7+(i>>16)*61+index)&255 for i in range(65538))
    memory[MAP:MAP+65538]=bytes((i*17+(i>>6)*3+index)%(256 if all_tiles else 132) for i in range(65538))
    memory[BUFFER:BUFFER+65538]=bytes((i*37+(i>>8)*11+(i>>16)*109+(index+1)*13)&255 for i in range(65538))
    memory[BACKDROP:BACKDROP+65538]=bytes(6+(i%pitch//16+i//pitch//8+index)%40 for i in range(65538))
    memory[SPRITES:SPRITES+65538]=bytes(0 if i%7==0 else (i*13+index)&255 for i in range(65538))
    memory[DATA+0x36:DATA+0x36+len(tiles)]=tiles
    memory[DATA+0x2136:DATA+0x2136+len(tiles)]=bytes(255 if value==0 else 0 for value in tiles)
    memory[SPRITES:SPRITES+len(pixels)]=pixels
    memory[STACK:STACK+72]=bytes((i*29+index*7+11)&255 for i in range(72))
    for offset,value in ((0xc1ea,pitch//8),(0xc1ec,pitch),(0xc1ee,160),(0xc1f0,map_start),
            (0xc1f6,back_gap),(0xc1f8,pitch),(0xc1fa,0x6003),(0xc1fe,0x3000),(0xc208,0x36),
            (0xc20a,fine_x),(0xc20c,fine_y),(0xc212,0x4001),(0xc214,buffer),(0xc216,16),
            (0xc218,8),(0xc498,back_offset),(0xc49a,0x5002)):
        struct.pack_into('<H',memory,DATA+offset,value)
    for offset in SCRATCH:
        struct.pack_into('<H',memory,DATA+offset,0xa55a)
    memory[DATA+0xc49c]=mode
    memory[DATA+0xc496]=count
    for i in range(count):
        width,height,source=descriptors[(i*7)%len(descriptors)]
        positions=((20,20),(-width,20),(-width+1,20),(-1,20),(pitch-1,20),(pitch,20),
            (pitch-width,20),(pitch-width+1,20),(20,-height),(20,-height+1),(20,-1),
            (20,159),(20,160),(20,160-height),(20,161-height),(-1,-1),(pitch-1,159),
            (-32768,20),(32767,20),(20,-32768),(20,32767),(pitch-width,160-height))
        x,y=positions[i%len(positions)]
        struct.pack_into('<HHBBH',memory,DATA+0xc21e+i*8,(x+16)&65535,(y+8)&65535,width,height,source)
    return_ip=0x7a2a if index%2==0 else 0x7a4c
    struct.pack_into('<HH',memory,0x83fe4,return_ip,0x1000)
    values=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x3ffe,
        0x18ac,0x1aa2,0x40,0x8000,0x3fe4,0xf4,0x602 if df else 0x202)
    return memory,values,return_ip
