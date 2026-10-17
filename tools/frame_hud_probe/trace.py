"""Stream complete original HUD-to-keyboard frame bridges."""
import csv
import gzip
import hashlib


def rows(path,metadata):
    digest=hashlib.sha256();length=0
    with gzip.open(path,'rb') as stream:
        def lines():
            nonlocal length
            for raw in stream:
                length+=len(raw)
                if length>384*1024**2:
                    raise ValueError('Keyboard trace exceeded its expanded reserve')
                digest.update(raw);yield raw.decode('ascii')
        reader=csv.reader(lines());header=next(reader)
        if len(header)!=len(set(header)) or header[-4:]!=['hud_globals','hud_font','hud_pixels','hud_vga_profile']:
            raise ValueError('Keyboard trace header differs')
        ended=False
        for values in reader:
            if values==['end']:
                ended=True
                if next(reader,None) is not None:
                    raise ValueError('Keyboard trace continues after end')
                break
            if len(values)!=len(header):
                raise ValueError('Keyboard trace is truncated or capped')
            row=dict(zip(header,values))
            if row['kind'] not in ('identified','keyboard_enter','instruction','keyboard_return'):
                raise ValueError('Unexpected keyboard boundary')
            if (int(row['cycle_max']),int(row['id_toggle']),int(row['queue_overflow']))!=(6000,0x200000,0):
                raise ValueError('Keyboard host profile differs')
            for name,size in [('stack',128),('globals',10),('crt_globals',2),('bios_keyboard',132),('keyboard_stub',20),('drain_key',1),
                ('hud_globals',86),('hud_pixels',272)]:
                if len(bytes.fromhex(row[name]))!=size:
                    raise ValueError('Keyboard memory scope differs')
            if row['kind']!='identified' and row['hud_vga_profile']!='1':
                raise ValueError('HUD video profile differs')
            yield row
        if not ended:
            raise ValueError('Keyboard trace has no terminal marker')
    metadata.update(trace_end_marker=True,trace_uncompressed_bytes=length,trace_uncompressed_sha256=digest.hexdigest())


def inspect_trace(path):
    metadata={};windows=[];current=None;identified=False;classes=set()
    for row in rows(path,metadata):
        kind=row['kind']
        if kind=='identified':
            if identified or current:
                raise ValueError('Keyboard identification order differs')
            identified=True;continue
        if not identified:
            raise ValueError('Keyboard trace has no identification')
        if kind=='keyboard_enter':
            category=int(row['keyboard_class'])
            if current or len(windows)>=4 or category in classes or category not in range(4) or int(row['ip'])!=0x79e8:
                raise ValueError('Keyboard entry or class differs')
            if len(bytes.fromhex(row['bank']))!=780 or len(bytes.fromhex(row['hud_font']))!=640:
                raise ValueError('Keyboard entry bank differs')
            current=dict(window=int(row['call']),category=category,states=0,irq_entries=0,dispatch=int(row['dispatch'])-1)
            continue
        if current is None or int(row['call'])!=current['window'] or int(row['dispatch'])!=current['dispatch']+1:
            raise ValueError('Keyboard dispatch is not contiguous')
        current['dispatch']=int(row['dispatch']);current['states']+=1
        current['irq_entries']+=(int(row['cs']),int(row['ip']))==(0xf000,0xfea5)
        if kind=='keyboard_return':
            if (int(row['cs']),int(row['ip']))!=(int(row['return_cs']),int(row['return_ip'])):
                raise ValueError('Keyboard return differs')
            classes.add(current['category']);windows.append(current);current=None
    if current or not identified:
        raise ValueError('Incomplete keyboard window')
    metadata['keyboard_windows']=windows
    metadata['validated_target_completed']=0 in classes and bool(classes & {1,2,3})
    return metadata
