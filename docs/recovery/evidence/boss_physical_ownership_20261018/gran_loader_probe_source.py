from pathlib import Path
import struct
import sys
import json

root=Path('/dev/shm/lezac-boss-owners-t238')
sys.path[:0]=['/dev/shm/lezac-unicorn-t237',str(root/'tools')]
import unicorn
from frame_camera_oracle import REGS,EXE_SHA,LIB_SHA,sha
from unicorn.unicorn_py3.unicorn import uclib

assert sha((root/'LEZAC.EXE').read_bytes())==EXE_SHA
assert sha(Path(uclib._name).read_bytes())==LIB_SHA
exe=(root/'LEZAC.EXE').read_bytes()
mz=struct.unpack_from('<14H',exe)
image=bytearray(exe[mz[4]*16:])
for i in range(mz[3]):
    offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4)
    at=segment*16+offset
    struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
initial=bytearray(1048576)
initial[0x10000:0x10000+len(image)]=image
data=0x1aa20
for offset,value in ((0x1afa,0x200),(0xc1fa,0xd000)):
    struct.pack_into('<H',initial,data+offset,value)
initial[data+0x208d]=0
initial[data+0x79f9]=0
initial[data+0xc496]=2
sprites=(root/'PROVA.SPR').read_bytes()
at=1
packed=bytearray()
for index in range(sprites[0]):
    width,height=sprites[at:at+2];at+=2
    struct.pack_into('<BBH',initial,data+0xc322+(index+1)*4,width,height,len(packed))
    packed.extend(sprites[at:at+width*height]);at+=width*height
assert at==len(sprites)
initial[0xd0000:0xd0000+len(packed)]=packed
struct.pack_into('<5H',initial,0x73fe4,0x2e9c,100,100,0x2ad3,0x1000)
values=(0,0,0,0,0,0,0x3ffe,0x1000,0x1aa2,0,0x7000,0x3fe4,0x8a5,0x202)
engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
engine.mem_map(0,1048576)
engine.mem_write(0,bytes(initial))
for reg,value in zip(REGS,values):
    engine.reg_write(reg,value)
file=(root/'GRAN.MST').read_bytes()
position=[0]
calls=[]
last=[]
def read_string(uc,segment,offset):
    return bytes(uc.mem_read(segment*16+offset,128)).split(bytes([0]),1)[0]
def interrupt(uc,number,user):
    r=[uc.reg_read(reg) for reg in REGS]
    ax,bx,cx,dx=r[:4]
    record=dict(interrupt=number,ax=ax,bx=bx,cx=cx,dx=dx,ds=r[8],cs=r[7],ip=r[12])
    if number!=0x21:
        raise ValueError('Unmodeled interrupt '+str(record))
    if ax>>8==0x3d:
        name=read_string(uc,r[8],dx)
        record['name']=name.decode('ascii')
        if name.upper()!=b'GRAN.MST':
            raise ValueError('Unexpected original open '+str(record))
        position[0]=0
        uc.reg_write(REGS[0],5)
    elif ax>>8==0x3f and bx==5:
        result=file[position[0]:position[0]+cx]
        uc.mem_write(r[8]*16+dx,result)
        position[0]+=len(result)
        uc.reg_write(REGS[0],len(result))
        record['returned']=len(result)
    elif ax>>8==0x3e and bx==5:
        uc.reg_write(REGS[0],0)
    else:
        raise ValueError('Unmodeled DOS service '+str(record))
    uc.reg_write(REGS[13],r[13]&~1)
    calls.append(record)
def code(uc,address,size,user):
    row=tuple(uc.reg_read(reg) for reg in REGS)
    last.append(row)
    if len(last)>12:
        del last[0]
    if row[7:8]+row[12:13]==(0x1920,0xe2):
        raise ValueError('Original runtime error AX='+hex(row[0]))
engine.hook_add(unicorn.UC_HOOK_INTR,interrupt)
engine.hook_add(unicorn.UC_HOOK_CODE,code)
try:
    engine.emu_start(0x108a5,0x12e9c,count=2000000)
    final=bytes(engine.mem_read(0,1048576))
    registers=[engine.reg_read(reg) for reg in REGS]
    print(json.dumps(dict(status='stopped',registers=registers,calls=calls,consumed=position[0],
        actor_count=final[data+0x208d],visual_count=final[data+0xc496],link_count=final[data+0x79f9],
        code_unchanged=final[0x10000:data]==initial[0x10000:data]),indent=2))
    if (registers[7],registers[12])==(0x1000,0x2e9c):
        out=Path('/dev/shm/lezac-gran-loader-probe-t238.bin')
        assert not out.exists()
        out.write_bytes(final)
except Exception as error:
    print(json.dumps(dict(status='failed',error=str(error),calls=calls,last=last),indent=2))
    raise
