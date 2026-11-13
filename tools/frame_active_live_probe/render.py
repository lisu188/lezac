"""Render independently captured original VGA and C++ replay outputs, not SDL screenshots."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from frame_active_live_probe.trace import rows


def render(capture,cpp,out):
    capture=capture.resolve(strict=True);cpp=cpp.resolve();out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only image directory')
    endpoints=[row for row in rows(capture/'guest-keyboard.csv.gz',{}) if row['kind']=='keyboard_return']
    out.mkdir();proofs=[]
    for index,row in enumerate(endpoints):
        identity=int(row['call'])
        with gzip.open(capture/('atomic-%d-final.ram.gz'%identity),'rb') as stream:
            original=stream.read(1048577)
        actual=Path(str(cpp)+'-%d.ram'%index).read_bytes()
        assert len(original)==len(actual)==1048576 and original==actual
        token=row['render_palette'].split(';')[4]
        palette=b''.join(int(token[i:i+8],16).to_bytes(4,'big')[1:] for i in range(0,2048,8))
        actual_palette=Path(str(cpp)+'-%d.pal'%index).read_bytes()
        assert actual_palette==palette and len(palette)==768
        frames=[]
        for label,memory,colors in (('original',original,palette),('cpp',actual,actual_palette)):
            pixels=memory[0xa0000:0xa0000+64000]
            rgb=b''.join(colors[value*3:value*3+3] for value in pixels)
            image=Image.frombytes('RGB',(320,200),rgb)
            image.save(out/('%s-%d.png'%(label,index)))
            frames.append(image)
        comparison=Image.new('RGB',(644,200));comparison.paste(frames[0],(0,0));comparison.paste(frames[1],(324,0))
        comparison.resize((1288,400),Image.Resampling.NEAREST).save(out/('comparison-%d.png'%index))
        proofs.append(dict(case=index,original_window=identity,pixel_differences=0,indexed_pixels=64000,
            rgb_sha256=hashlib.sha256(frames[0].tobytes()).hexdigest(),
            scope='Atomic VGA memory and independently computed palette; original left, C++ operation replay right; not production App'))
    (out/'report.json').write_text(json.dumps(dict(cases=proofs,actual_app_integration=False),indent=2)+'\n')
    print(json.dumps(proofs),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','cpp','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();render(args.capture,args.cpp,args.out)
