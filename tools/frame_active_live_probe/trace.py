"""Validate continuous active-window traces; no reference state is injected."""
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
                if length>1024*1024**2:
                    raise ValueError('Keyboard trace exceeded its expanded reserve')
                digest.update(raw);yield raw.decode('ascii')
        reader=csv.reader(lines())
        if next(reader)!=['active-sparse-v1']:
            raise ValueError('Active trace encoding differs')
        header=next(reader);previous=None
        if len(header)!=len(set(header)) or header[-8:]!=['hud_globals','hud_font','hud_pixels','hud_vga_profile','psp_bytes','render_palette','gfx_format','native_palette']:
            raise ValueError('Keyboard trace header differs')
        ended=False;palette=None
        for values in reader:
            if values==['end']:
                ended=True
                if next(reader,None) is not None:
                    raise ValueError('Keyboard trace continues after end')
                break
            if len(values)!=len(header):
                raise ValueError('Keyboard trace is truncated or capped')
            if '~' in values:
                if previous is None or values[0]=='keyboard_enter':
                    raise ValueError('Active inherited value has no complete entry')
                values=[old if value=='~' else value for old,value in zip(previous,values)]
            previous=values
            row=dict(zip(header,values))
            if row['kind'] not in ('identified','keyboard_enter','instruction','keyboard_return'):
                raise ValueError('Unexpected keyboard boundary')
            if (int(row['cycle_max']),int(row['id_toggle']),int(row['queue_overflow']))!=(6000,0x200000,0):
                raise ValueError('Keyboard host profile differs')
            for name,size in [('stack',128),('globals',10),('crt_globals',2),('bios_keyboard',132),('keyboard_stub',20),('drain_key',1),
                ('hud_globals',86),('hud_pixels',272),('psp_bytes',32),('frame_globals',11),('display_globals',5),('pacing_globals',9)]:
                if len(bytes.fromhex(row[name]))!=size:
                    raise ValueError('Keyboard memory scope differs')
            if row['kind']!='identified' and row['hud_vga_profile']!='1':
                raise ValueError('HUD video profile differs')
            if row['render_palette']:
                palette=row['render_palette']
                parts=palette.split(';')
                if len(parts)!=7 or len(parts[4])!=2048 or len(parts[5])!=2048 or len(parts[6])!=512:
                    raise ValueError('Renderer palette token differs')
                for part in parts[:4]: int(part)
                for part in parts[4:]: bytes.fromhex(part)
            if palette is None or (row['kind']=='keyboard_enter' and not row['render_palette']):
                raise ValueError('Renderer palette entry is missing')
            row['render_palette']=palette
            if len(row['gfx_format'].split(';'))!=18:
                raise ValueError('Graphics format scope differs')
            yield row
        if not ended:
            raise ValueError('Keyboard trace has no terminal marker')
    metadata.update(trace_end_marker=True,trace_uncompressed_bytes=length,trace_uncompressed_sha256=digest.hexdigest())


def inspect_trace(path, endpoint=0x7a57):
    if endpoint not in (0x7a57, 0x7ebb):
        raise ValueError('Unsupported active-window endpoint')
    metadata={};windows=[];current=None;identified=False;classes=set()
    for row in rows(path,metadata):
        kind=row['kind'];cs=int(row['cs']);ip=int(row['ip'])
        if kind=='identified':
            if identified or current:
                raise ValueError('Active identification order differs')
            identified=True
            continue
        if not identified:
            raise ValueError('Active trace has no identification')
        if kind=='keyboard_enter':
            if current or len(windows)>=4 or ip!=0x7903 or int(row['return_ip'])!=endpoint:
                raise ValueError('Active entry differs')
            category=int(row['keyboard_class'])
            if category not in (0,1) or int(row['call'])!=len(windows)+1:
                raise ValueError('Active case identity differs')
            current=dict(window=int(row['call']),category=category,states=0,irq_entries=0,
                render_irq_entries=0,render_entry=False,dispatch=int(row['dispatch'])-1,
                hud_entries=0,render_instructions=0,post_render_entry=False,waiting_entry=False,post_render_states=0,
                post_render_irq_entries=0)
            continue
        if current is None or int(row['call'])!=current['window'] or int(row['dispatch'])!=current['dispatch']+1:
            raise ValueError('Active dispatch is not contiguous')
        current['dispatch']=int(row['dispatch']);current['states']+=1
        if (cs,ip)==(int(row['return_cs']),0x7a13):
            current['render_entry']=True
        if kind!='keyboard_return' and (cs,ip)==(int(row['return_cs']),0x7a57):
            current['post_render_entry']=True
        if kind!='keyboard_return' and (cs,ip)==(int(row['return_cs']),0x7c3d):
            current['waiting_entry']=True
        current['hud_entries']+=(cs,ip)==(int(row['return_cs']),0x3184)
        if (cs,ip)==(0xf000,0xfea5):
            current['irq_entries']+=1
            current['render_irq_entries']+=current['render_entry'] and not current['post_render_entry']
            current['post_render_irq_entries']+=current['post_render_entry']
        current['render_instructions']+=current['render_entry'] and not current['post_render_entry']
        current['post_render_states']+=current['post_render_entry']
        if kind=='keyboard_return':
            if (cs,ip)!=(int(row['return_cs']),endpoint) or not current['render_entry'] or (
                    endpoint==0x7ebb and not (current['post_render_entry'] and current['waiting_entry'])):
                raise ValueError('Active return differs')
            if current['category']==0:
                if not current['hud_entries']:
                    raise ValueError('Changed-HUD active window has no HUD entry')
                classes.add(0)
            elif current['render_irq_entries']:
                classes.add(1)
            current['target_completed']=row['target_completed']=='1'
            windows.append(current);current=None
    if current or not identified or not windows:
        raise ValueError('Incomplete active window')
    metadata.update(keyboard_windows=windows,active_live_windows=windows,observed_end_ip=endpoint,
        validated_target_completed=classes=={0,1} and windows[-1]['target_completed'])
    return metadata
