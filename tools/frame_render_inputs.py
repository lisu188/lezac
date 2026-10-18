"""Controlled shared-bus inputs for the unchanged per-player render caller."""
import struct

from frame_world_raster_inputs import ASSETS,DATA,STACK,assets,initial_memory


def profiles():
    common=(1,0,100,100,250,140,0,0)
    result=[(1,state,0,*common) for state in (0,1,2,255)]
    result.extend((2,first,second,*common)
        for first in (0,1,2,255) for second in (0,1,2,255))
    result.extend(((2,1,1,0,0,65532,65535,1000,1200,65535,0),
        (2,2,255,2,0,0,0,488,640,1,0),
        (1,255,0,1,1,32767,32768,80,80,0,0),
        (2,1,0,255,1,32768,32767,80,80,0,0),
        (1,1,0,1,0,100,100,250,140,0,65535),
        (2,0,1,1,0,100,100,250,140,0,65535)))
    return result


def memory(index,profile,loaded):
    players,first,second,mode,df,x1,y1,x2,y2,buffer,limit=profile
    pitch=320 if players==1 else 160
    initial,values,_=initial_memory(index,(pitch,mode,df,buffer,2,7,7,48,0,22,0),loaded)
    half=pitch//2-8
    initial[DATA+0x79e6:DATA+0x79e8]=bytes((first,second))
    for offset,value in ((0x1afa,limit),(0x78bc,half),(0x78be,half//8),
            (0x2094,(60-pitch//8)*8),(0x2096,480),(0x2098,0),
            (0x79f0,1284),(0x79f2,1444),(0xc204,60),(0xc206,320-pitch),
            (0xc21e,x1),(0xc220,y1),(0xc226,x2),(0xc228,y2)):
        struct.pack_into('<H',initial,DATA+offset,value)
    initial[0xa0000:0xb0002]=bytes((i*11+(i>>8)*7+index)&255 for i in range(65538))
    values=list(values)
    values[7]=0x1000
    values[12]=0x7a13
    return initial,tuple(values)
