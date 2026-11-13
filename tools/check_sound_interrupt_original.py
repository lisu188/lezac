"""Compare compiled IRQ and signed-priority transitions with pinned original opcode models."""
import argparse
import hashlib
from pathlib import Path
import struct
import subprocess

EXE_SHA='7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
BANK_SHA='b5bc702a27ac85554cc76a62fced07567921b07d5c16f2027a62fbc956df701d'
WINDOWS=((0x172e,0x1801,'8505700f9f878bc49cb2ae0a62d2bd2c5ae9ca2849b8581bcc7cf95f6e06aecc'),
         (0x1dca,0x1dee,'91fe295674daff2c5d46e15fdcbb680a8a53e71dbda72b6f68cd39b7e91e9fc6'),
         (0x2f0e,0x2f29,'fb8eb172c58f762ce1053a2d7ceb6d359271bbd5f3fc48c2947948f38c4ceddd'),
         (0x306b,0x3075,'9bd5e7a72bc574c857ab0548e57197a122e20f453a7d6d6e024c66f6b285db6c'))


def mix(value,data):
    for byte in data:
        value=((value^byte)*1099511628211)&0xffffffffffffffff
    return value


def state(active,selector,cursor,acc,gate,period,frequency,tone,silence):
    return struct.pack('<BBHBBBHBB',active,selector,cursor,acc,gate,period,frequency,tone,silence)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent)
    args=parser.parse_args()
    exe=(args.root/'LEZAC.EXE').read_bytes()
    bank=(args.root/'PROEFS.SON').read_bytes()
    if hashlib.sha256(exe).hexdigest()!=EXE_SHA or hashlib.sha256(bank).hexdigest()!=BANK_SHA:
        raise RuntimeError('pinned original executable or bank changed')
    for start,end,digest in WINDOWS:
        if hashlib.sha256(exe[start:end]).hexdigest()!=digest:
            raise RuntimeError(f'original sound opcode window changed: {start:x}')
    result=subprocess.run([str(args.exe.resolve()),str(args.root/'PROEFS.SON')],
        capture_output=True,text=True,check=True,timeout=90)
    fields=dict(token.split('=',1) for token in result.stdout.split() if '=' in token)
    if fields.get('sound_interrupt')!='ok' or fields.get('phase_cases')!='16777216':
        raise RuntimeError('compiled interrupt scan incomplete')
    bank_hash=14695981039346656037
    boundary=(0,1,2,255)
    for cursor in range(130):
        frequency,entry_gate,entry_period,_=struct.unpack_from('<HBBH',bank,2+cursor*6)
        for acc in boundary:
            for period in boundary:
                for gate in boundary:
                    next_acc=(acc+1)&255
                    advance=next_acc==period
                    stop=advance and frequency==0x7530
                    data=state(not stop,5,cursor+advance,0 if advance else next_acc,
                        entry_gate if advance and not stop else gate,
                        1 if stop else entry_period if advance else period,
                        frequency if advance and not stop else 0,
                        advance and not stop,stop or (not advance and next_acc==gate))
                    bank_hash=mix(bank_hash,data)
    direct_hash=14695981039346656037
    for cursor in range(0xea61,0x10000):
        for acc in (0,1,255):
            for period in (0,1,255):
                for gate in (0,1,255):
                    end=cursor-4<=0xea60
                    direct_hash=mix(direct_hash,state(not end,5,cursor-4,acc,gate,period,
                                                      cursor-0xea42,True,end))
    priority_hash=14695981039346656037
    unsigned_differences=0
    for current in range(256):
        left=(current-1)&255
        for pending in range(256):
            subtraction=(left-pending)&255
            sign=bool(subtraction&0x80)
            overflow=bool((left^pending)&(left^subtraction)&0x80)
            accept=sign!=overflow  # 7d JGE rejects when SF == OF.
            unsigned_differences+=accept!=(left<pending)
            data=bytes([accept])+state(True,pending if accept else current,
                0x21 if accept else 0xea7e,255,7,0,0,False,False)
            priority_hash=mix(priority_hash,data)
    for name,expected in (('bank_hash',bank_hash),('direct_hash',direct_hash),('priority_hash',priority_hash)):
        if int(fields[name],16)!=expected:
            raise RuntimeError(f'compiled {name} differs from original instruction model')
    if not unsigned_differences:
        raise RuntimeError('signed priority oracle failed to distinguish unsigned comparison')
    print('sound_interrupt_original=ok windows=4 phase_cases=16777216 bank_cases=8320'
          ' direct_cases=149445 priority_cases=65536'
          f' unsigned_priority_differences={unsigned_differences}'
          f' bank_hash={bank_hash:x} direct_hash={direct_hash:x} priority_hash={priority_hash:x}'
          ' native_irq_claim=0 runtime_scheduler_integrated=0 whole_game_complete=0')


if __name__=='__main__':
    main()
