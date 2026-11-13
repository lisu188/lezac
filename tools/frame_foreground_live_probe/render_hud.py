"""Render actual C++ HUD-buffer dumps beside independently observed original pixels."""
import argparse,hashlib,json,struct
from pathlib import Path
from PIL import Image

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();raw=args.input.read_bytes();out=args.out.resolve()
assert out.is_relative_to(Path('/dev/shm')) and not out.exists() and raw[:8]==b'LZHUDPIX'
count=struct.unpack_from('<I',raw,8)[0];assert count==2 and len(raw)==12+count*(8+768+544)
out.mkdir();cursor=12;records=[]
for _ in range(count):
 case,counter=struct.unpack_from('<2I',raw,cursor);cursor+=8;palette=raw[cursor:cursor+768];cursor+=768
 actual=raw[cursor:cursor+272];cursor+=272;expected=raw[cursor:cursor+272];cursor+=272
 assert actual==expected
 images=[]
 for name,pixels in [('cpp',actual),('original',expected)]:
  rgb=b''.join(palette[index*3:index*3+3] for index in pixels)
  image=Image.frombytes('RGB',(17,16),rgb).resize((204,192),Image.Resampling.NEAREST)
  path=out/('%s-case%d.png'%(name,case));image.save(path);images.append(image)
 comparison=Image.new('RGB',(432,192));comparison.paste(images[1],(0,0));comparison.paste(images[0],(228,0))
 comparison.save(out/('comparison-case%d.png'%case))
 records.append(dict(case=case,entry_counter=counter,indexed_pixels=272,pixel_differences=0,cpp_indices_sha256=hashlib.sha256(actual).hexdigest(),
  original_indices_sha256=hashlib.sha256(expected).hexdigest(),scope='two 17x8 HUD regions stacked, original left, C++ replay right, not a full App frame'))
(out/'report.json').write_text(json.dumps(dict(input_sha256=hashlib.sha256(raw).hexdigest(),cases=records,whole_frame_claim=False),indent=2)+'\n')
print(json.dumps(records),flush=True)
