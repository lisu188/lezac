"""Prove the coupled replay does not take later clock state or observed IRQ positions as inputs."""
import argparse
import os
from pathlib import Path
import struct
import subprocess
import tempfile


def run(binary, cpu, clock=None):
    command=[str(binary),'--device-clock-projection' if clock else '--observed-irq-projection',str(cpu)]
    if clock:
        command.append(str(clock))
    return subprocess.run(command,capture_output=True,text=True,timeout=180,
        env=dict(os.environ,SDL_AUDIODRIVER='dummy',PYTHONDONTWRITEBYTECODE='1'))


def controls(binary,cpu_path,clock_path):
    cpu=bytearray(cpu_path.read_bytes());clock=bytearray(clock_path.read_bytes())
    assert cpu[:8]==b'LZFPAC01' and clock[:8]==b'LZPDCL01'
    header=struct.unpack_from('<12HB3I',cpu,12)
    assert header[15]>0
    irq_offset=12+struct.calcsize('<12HB3I')
    state_offset=irq_offset+4*header[15]+header[9]
    first_clock=16
    queue_count=struct.unpack_from('<H',clock,first_clock+76)[0]
    device_offset=first_clock+78+queue_count*13
    tickers=clock[device_offset+31*8]
    second_clock=device_offset+31*8+1+tickers
    checked=0
    with tempfile.TemporaryDirectory(prefix='lezac-pacing-coupling-') as folder:
        root=Path(folder);c=root/'cpu.bin';k=root/'clock.bin'
        changed=bytearray(cpu)
        for index in range(header[15]):
            struct.pack_into('<I',changed,irq_offset+index*4,0)
        c.write_bytes(changed);k.write_bytes(clock)
        result=run(binary,c,k)
        assert result.returncode==0 and 'observed_irq_boundaries_external=0 irq_eligibility_claim=1' in result.stdout,result.stderr
        assert run(binary,c).returncode!=0,'Observed-IRQ control ignored the deliberately wrong input'
        checked+=2
        c.write_bytes(cpu)
        for label,offset in [('later_budget',second_clock),('later_device',second_clock+78+
                struct.unpack_from('<H',clock,second_clock+76)[0]*13)]:
            changed=bytearray(clock);changed[offset]^=1;k.write_bytes(changed)
            result=run(binary,c,k)
            assert result.returncode!=0,label+' later observation was used as computed state'
            checked+=1
        k.write_bytes(clock)
        changed=bytearray(cpu);changed[state_offset+211+8]^=1;c.write_bytes(changed)
        assert run(binary,c,k).returncode!=0,'Later CPU observation was injected'
        checked+=1
    print('pacing_clock_coupling_controls=ok controls='+str(checked)+' observed_irq_positions_are_not_inputs=1')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--cpu',type=Path,required=True)
    parser.add_argument('--clock',type=Path,required=True)
    args=parser.parse_args()
    controls(args.binary,args.cpu,args.clock)
