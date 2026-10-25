"""Transcribe original collapse updater and map/record helpers."""
import argparse
from pathlib import Path
from generate_transient_queue_instructions import generate

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    generate(args.repo.resolve(),args.out,cuts=((0x4d3c,0x568a),),entry=(0,0x5102),
        extra_delegated={(0,0x3bb2):8,(0,0x3d46):8},prefix='Collapse')
