"""Execute original pacing/feedback/CRT bytes with a declared scripted DOS service."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

import unicorn
from unicorn.x86_const import (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX,
    UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES,
    UC_X86_REG_SS, UC_X86_REG_SP, UC_X86_REG_IP, UC_X86_REG_EFLAGS, UC_X86_INS_IN, UC_X86_INS_OUT)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from frame_display_probe.oracle import next_mask as real48_mask

CS, DS, SS, SP, BASE, PSP = 0x1000, 0x1aa2, 0x8000, 0xfe06, 0xfdb6, 0x0ff0
REGS = (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX, UC_X86_REG_SI, UC_X86_REG_DI,
    UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS, UC_X86_REG_SP)
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def mask_after(mask, opcode, cl):
    while opcode[0] in (0x26, 0x2e, 0x36, 0x3e):
        opcode = opcode[1:]
    if opcode[0] in (0x01, 0x29):
        return mask | 0x8d5
    if opcode[0] == 0x09:
        return (mask | 0x8d5) & ~0x10
    if 0x40 <= opcode[0] <= 0x4f or opcode[0] == 0xff and (opcode[1] >> 3) & 7 == 0:
        return mask | 0x8d4
    if opcode[0] == 0xf7 and (opcode[1] >> 3) & 7 == 6:
        return mask & ~0x8d5
    return real48_mask(mask, opcode, cl)


def capture(executable, out):
    assert unicorn.__version__ == '2.1.4'
    out = out.resolve()
    assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
    original = executable.read_bytes()
    assert sha(original) == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    mz = struct.unpack_from('<14H', original)
    image = bytearray(original[0x770:])
    for index in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', original, mz[12] + 4 * index)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + CS) & 65535)
    def forbidden(*unused):
        raise RuntimeError('Unexpected hardware I/O')
    def dos(engine, number, unused):
        assert number == 0x21 and engine.reg_read(UC_X86_REG_AX) >> 8 == 0x2c
        sp = engine.reg_read(UC_X86_REG_SP)
        flags = engine.reg_read(UC_X86_REG_EFLAGS)
        # Declared DOS provider includes its control-stack/PSP ABI, not original kernel execution.
        engine.mem_write(SS * 16 + sp - 6, struct.pack('<3H', 0x791e, CS, flags & 65535))
        engine.mem_write(SS * 16 + sp - 8, b'\0\0')
        engine.mem_write(PSP * 16 + 0x2e, struct.pack('<I', (SS << 16) | ((sp - 24) & 65535)))
        engine.reg_write(UC_X86_REG_CX, 0)
        engine.reg_write(UC_X86_REG_DX, (5 << 8) | 49)
    def emulator():
        engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
        engine.mem_map(0, 1048576)
        engine.mem_write(CS * 16, bytes(image))
        engine.hook_add(unicorn.UC_HOOK_INTR, dos)
        engine.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, UC_X86_INS_IN)
        engine.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, UC_X86_INS_OUT)
        return engine
    observed, control = emulator(), emulator()
    contexts = {id(engine): engine.context_save() for engine in (observed, control)}
    def initialize(engine, index, start, pacing, timing, denominator=66, numerator=0):
        engine.context_restore(contexts[id(engine)])
        values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x9abc, CS, DS, 0xbeef, SS, SP)
        for register, value in zip(REGS, values):
            engine.reg_write(register, value)
        engine.reg_write(UC_X86_REG_IP, start)
        engine.reg_write(UC_X86_REG_EFLAGS, 0x202 | (0x400 if index % 3 == 0 else 0) | (0x8d5 if index % 2 else 0))
        engine.mem_write(DS * 16 + 0x78c2, pacing[:2])
        engine.mem_write(DS * 16 + 0x78ca, pacing[2:6])
        engine.mem_write(DS * 16 + 0x7f68, pacing[6:8])
        engine.mem_write(DS * 16 + 0x2074, timing[:2])
        engine.mem_write(DS * 16 + 0x79a4, timing[2:])
        engine.mem_write(DS * 16 + 0x78c6, struct.pack('<2H', denominator, numerator))
        engine.mem_write(DS * 16 + 0x79b5, b'\x5a')
        engine.mem_write(SS * 16 + BASE, bytes((index + i) & 255 for i in range(128)))
        engine.mem_write(0x400, b'\xf8')
        engine.mem_write(0x46c, struct.pack('<I', 100))
        engine.mem_write(PSP * 16 + 0x2e, b'\0' * 4)
    def registers(engine, address, mask):
        return struct.pack('<13H2I', *[engine.reg_read(r) for r in REGS], address - engine.reg_read(UC_X86_REG_CS) * 16,
            engine.reg_read(UC_X86_REG_EFLAGS), mask)
    def memory(engine):
        return bytes(engine.mem_read(SS * 16 + BASE, 128)) + bytes(engine.mem_read(DS * 16 + 0x78c6, 4)) + \
            bytes(engine.mem_read(DS * 16 + 0x79b5, 1)) + bytes(engine.mem_read(DS * 16 + 0x2074, 2)) + \
            bytes(engine.mem_read(DS * 16 + 0x79a4, 9)) + bytes(engine.mem_read(DS * 16 + 0x78c2, 2)) + \
            bytes(engine.mem_read(DS * 16 + 0x78ca, 4)) + bytes(engine.mem_read(DS * 16 + 0x7f68, 2)) + \
            bytes(engine.mem_read(0x400, 1)) + bytes(engine.mem_read(PSP * 16 + 0x2e, 4)) + bytes(engine.mem_read(0x46c, 4))
    cases = [
        ('skip_zero', 0, 0, 0, 544, 0, 0, 0, 66, 0),
        ('skip_one', 28, 0, 1, 1, 0, 0, 0, 66, 0),
        ('skip_two', 30, 0, 2, 2, 0, 0, 0, 66, 0),
        ('skip_natural16', 0, 2, 16, 544, 0, 0, 0, 66, 0),
        ('skip_maximum', 65534, 0, 65535, 1, 0, 0, 0, 66, 0),
        ('calibration_wrap', 0, 0, 1, 0, 0, 0, 0, 66, 0),
        ('slow_natural', 29, 2, 16, 544, 0, 0, 0, 66, 0),
        ('slow_saturate', 29, 2, 1, 1, 0, 4, 23, 66, 0),
        ('fast_119', 29, 2, 1, 2, 0, 4, 30, 148, 120),
        ('deadband120', 29, 2, 0, 1, 0, 4, 29, 66, 0),
        ('deadband125', 29, 2, 0, 1, 0, 4, 24, 66, 0),
        ('fast_wrap', 29, 2, 65535, 1, 0, 5, 49, 66, 0),
        ('counter_wrap', 65535, 0, 0, 1, 0, 0, 0, 148, 120),
        ('negative_elapsed', 29, 2, 2, 1, 0, 6, 0, 66, 0),
        ('real48_error', 29, 0, 0, 1, 0, 0, 0, 0, 1),
    ]
    output = bytearray(b'LZPWAIT1' + struct.pack('<I', len(cases)))
    summaries = []
    snapshots, dispatch, mask = [], 0, 0xffffffff
    def decoded(engine, address, size, unused):
        nonlocal dispatch, mask
        if dispatch in (0,1,2,4,7,8,9,10,11,12,20,30,100,1000,10000) or dispatch % 5000 == 0:
            snapshots.append((dispatch, registers(engine,address,mask) + memory(engine)))
        opcode = bytes(engine.mem_read(address,size))
        mask = mask_after(mask,opcode,engine.reg_read(UC_X86_REG_CX)&255)
        dispatch += 1
    observed.hook_add(unicorn.UC_HOOK_CODE, decoded)
    out.mkdir()
    (out/'producer.py').write_bytes(Path(__file__).read_bytes())
    for index, (name,counter,step,delay,calibration,old_minute,old_second,old_hundredth,denominator,numerator) in enumerate(cases):
        pacing = struct.pack('<4H',counter,step,delay,calibration)
        timing = struct.pack('<H',0xbeef) + bytes((old_minute,0xa5,0x5a,0xa5,old_second,old_hundredth,59,58,99))
        initialize(observed,index,0x7903,pacing,timing,denominator,numerator)
        snapshots, dispatch, mask = [], 0, 0xffffffff
        due = ((counter+1)&65535)%30 == 0
        terminal = (CS+0x920)*16+0xe2 if due and denominator==0 else CS*16+0x79e8
        observed.emu_start(CS*16+0x7903,terminal,count=2000000)
        assert observed.reg_read(UC_X86_REG_CS)*16+observed.reg_read(UC_X86_REG_IP)==terminal and dispatch < 2000000
        endpoint = registers(observed,terminal,0xffffffff) + memory(observed)
        snapshots.append((dispatch,endpoint))
        initialize(control,index,0x7903,pacing,timing,denominator,numerator)
        control.emu_start(CS*16+0x7903,terminal,count=2000000)
        assert registers(control,terminal,0xffffffff)+memory(control)==endpoint
        output.extend(struct.pack('<2HBQI',denominator,numerator,terminal!=CS*16+0x79e8,dispatch,len(snapshots)))
        output.extend(pacing+timing)
        for position, data in snapshots:
            translated = position + (326 if due and position >= 10 else 0)
            output.extend(struct.pack('<2Q',position,translated)+data)
        summaries.append(dict(name=name,original_dispatches=dispatch,translated_dispatches=dispatch+(326 if due else 0),
            snapshots=len(snapshots),scripted_dos_calls=int(due)))
        print(json.dumps(summaries[-1]),flush=True)
    gate = bytearray(b'LZPGATE1'+struct.pack('<I',65536))
    for counter in range(65536):
        pacing = struct.pack('<4H',counter,0,0,1)
        initialize(control,counter,0x7903,pacing,bytes(11))
        due=((counter+1)&65535)%30==0
        terminal=CS*16+(0x7919 if due else 0x79df)
        control.emu_start(CS*16+0x7903,terminal,count=8 if due else 9)
        assert control.reg_read(UC_X86_REG_IP)==terminal-CS*16, (counter, due,
            control.reg_read(UC_X86_REG_CS), control.reg_read(UC_X86_REG_IP), terminal-CS*16)
        gate.extend(struct.pack('<HBB',counter,due,8 if due else 9)+registers(control,terminal,0xffffffff))
    control = emulator()
    contexts[id(control)] = control.context_save()
    feedback = bytearray(b'LZPFEED1'+struct.pack('<I',5*65536))
    profiles = [(0,0),(1,2),(16,2),(65535,2),(65535,65535)]
    for profile,(delay,step) in enumerate(profiles):
        for elapsed in range(65536):
            pacing=struct.pack('<4H',0,step,delay,1)
            timing=struct.pack('<H',elapsed)+bytes((17,0xa5,0x5a,0xa5,33,44,59,58,99))
            initialize(control,elapsed,0x799a,pacing,timing)
            control.emu_start(CS*16+0x799a,CS*16+0x79df,count=30)
            assert control.reg_read(UC_X86_REG_IP)==0x79df
            assert bytes(control.mem_read(SS*16+BASE,128))==bytes((elapsed+i)&255 for i in range(128))
            feedback.extend(struct.pack('<BH',profile,elapsed)+registers(control,CS*16+0x79df,0xffffffff)+
                bytes(control.mem_read(DS*16+0x2074,2))+bytes(control.mem_read(DS*16+0x79a4,9))+
                bytes(control.mem_read(DS*16+0x78cc,2)))
    for engine in (observed,control):
        assert bytes(engine.mem_read(CS*16,43552))==image[:43552]
    files=[]
    for name,raw in [('full.bin.gz',output),('gate.bin.gz',gate),('feedback.bin.gz',feedback)]:
        compressed=gzip.compress(raw,mtime=0)
        (out/name).write_bytes(compressed)
        files.append(dict(name=name,bytes=len(compressed),sha256=sha(compressed),projection_bytes=len(raw),projection_sha256=sha(raw)))
    record=dict(schema='lezac-controlled-full-pacing-v1',original_executable_sha256=sha(original),producer_sha256=sha(Path(__file__).read_bytes()),
        mask_provider_sha256=sha(Path(__file__).resolve().parents[1].joinpath('frame_display_probe/oracle.py').read_bytes()),
        unicorn=unicorn.__version__,cases=summaries,gate_inputs=65536,feedback_inputs=327680,files=files,
        original_game_and_crt_calls_stubbed=False,scripted_dos_service=True,scripted_dos_control_stack_and_psp=True,
        scripted_dos_time=[0,0,5,49],kernel_dispatches_supplied_by_cpp_profile=326,initial_bios_ticks=100,
        instruction_patches=0,code_bytes_unchanged=43552,read_hooks=False,observed_control_endpoints_identical=True,
        natural_gameplay_claim=False,whole_game_parity=False)
    (out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(full_cases=len(cases),gate_inputs=65536,feedback_inputs=327680,files=files)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    capture(args.exe,args.out)
