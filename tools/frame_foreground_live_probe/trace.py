"""Require actual glyph work and natural timer delivery in complete foreground windows."""
import struct

from frame_foreground_probe.trace import rows,inspect_trace as inspect_common

def inspect_trace(path):
    metadata=inspect_common(path);proofs=[];current=None;previous_pixels=None
    for row in rows(path,{}):
        if row['kind']=='identified':continue
        if row['kind']=='keyboard_enter':
            hud=bytes.fromhex(row['hud_globals']);pacing=bytes.fromhex(row['pacing_globals'])
            counter,step,delay=struct.unpack_from('<3H',pacing)
            category=int(row['keyboard_class']);now=(int(row['cycle_max'])-int(row['cpu_cycles'])-int(row['cpu_left']))/int(row['cycle_max'])
            pit=[struct.unpack('<f',struct.pack('<I',int(item.split(':')[0],16)))[0]-now for item in row['queue'].split(';') if item.split(':')[1]=='1']
            word,cache=struct.unpack_from('<HH',hud,26)
            if counter%30==29 or category not in (0,1) or len(pit)!=1:raise ValueError('Live foreground entry profile differs')
            if category==0 and (not (word!=cache or hud[32]!=hud[33]) or delay>20):raise ValueError('Live HUD entry has no stale cache')
            if category==1 and not (2<=delay<=8 and 0<pit[0]<delay-0.25):raise ValueError('Live timer was not due in the observed delay')
            current=dict(category=category,counter=counter,entry_delay=delay,pit_due_ms=pit[0],hud_entries=0,rep_dispatches=0,
                irq_entries=0,pixel_state_changes=0)
            previous_pixels=row['hud_pixels'];continue
        if current is None:raise ValueError('Live foreground boundary has no entry')
        current['hud_entries']+=(int(row['cs']),int(row['ip']))==(int(row['return_cs']),0x3184)
        current['irq_entries']+=(int(row['cs']),int(row['ip']))==(0xf000,0xfea5)
        op=bytes.fromhex(row['opcode']);current['rep_dispatches']+=op[0] in (0xf2,0xf3) and op[1] in (0xa4,0xa5)
        current['pixel_state_changes']+=row['hud_pixels']!=previous_pixels;previous_pixels=row['hud_pixels']
        if row['kind']=='keyboard_return':
            if current['category']==0 and not (current['hud_entries'] and current['rep_dispatches']):raise ValueError('Original HUD drawing did not execute')
            if current['category']==1 and not current['irq_entries']:raise ValueError('Original timer interrupt did not execute')
            proofs.append(current);current=None
    if current or {p['category'] for p in proofs}!={0,1}:raise ValueError('Live foreground coverage incomplete')
    metadata['foreground_live_windows']=proofs
    return metadata
