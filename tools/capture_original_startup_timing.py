"""Execute original startup calibration with optional Unicorn 2.1.4.

The complete original CRT calls execute unchanged. DOS GetTime is a scripted
service and CRT calibration/COM1 data are declared fixture inputs, not live boot.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
CS, DS, SS = 0x1000, 0x1aa2, 0x8000
CODE, DATA = CS * 16, DS * 16

def capture(root, out):
    import unicorn
    from unicorn.x86_const import (UC_X86_INS_IN, UC_X86_INS_OUT, UC_X86_REG_AX,
        UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_DX, UC_X86_REG_CX,
        UC_X86_REG_EFLAGS, UC_X86_REG_IP, UC_X86_REG_SP, UC_X86_REG_SS)

    if unicorn.__version__ != '2.1.4':
        raise ValueError('Unicorn 2.1.4 is required for this original oracle')
    raw = (root / 'LEZAC.EXE').read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXE_SHA:
        raise ValueError('Original executable differs')
    header = struct.unpack_from('<14H', raw)
    if header[3] != 468 or header[4] * 16 != 0x770:
        raise ValueError('Original relocation header differs')
    image = bytearray(raw[0x770:])
    for index in range(header[3]):
        offset, segment = struct.unpack_from('<HH', raw, header[12] + index * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + CS) & 65535)
    initial = bytearray(1024 * 1024)
    initial[CODE:CODE + len(image)] = image
    baseline = bytes(initial)

    def emulator():
        cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
        cpu.mem_map(0, 1024 * 1024)
        cpu.mem_write(0, baseline)
        return cpu

    def registers(cpu, bp, sp, ax=0):
        for register, value in ((UC_X86_REG_CS, CS), (UC_X86_REG_DS, DS),
            (UC_X86_REG_SS, SS), (UC_X86_REG_BP, bp), (UC_X86_REG_SP, sp),
            (UC_X86_REG_AX, ax), (UC_X86_REG_EFLAGS, 0x202)):
            cpu.reg_write(register, value)

    def forbidden(*unused):
        raise RuntimeError('Unexpected original interrupt or hardware port I/O')

    def words(cpu):
        return [struct.unpack('<H', bytes(cpu.mem_read(DATA + offset, 2)))[0]
                for offset in (0x78ce, 0x78d0, 0x78ca)]

    cpu = emulator()
    context = cpu.context_save()
    writes = set()

    def write(cpu, access, address, size, value, user):
        if address < CODE + 43552 and address + size > CODE:
            raise RuntimeError('Original code modification is forbidden')
        writes.add((address, size))

    cpu.hook_add(unicorn.UC_HOOK_INTR, forbidden)
    cpu.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, UC_X86_INS_IN)
    cpu.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, UC_X86_INS_OUT)
    cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
    full = bytearray()
    gate = bytearray(8192)
    accepted_words = bytearray()
    for elapsed in range(65536):
        for address, size in writes:
            cpu.mem_write(address, baseline[address:address + size])
        writes.clear()
        cpu.context_restore(context)
        registers(cpu, 0xf000, 0xefe0, elapsed)
        cpu.mem_write(0x8f000, struct.pack('<3H', 0xbeef, 0xff00, 0))
        expected_end = 0xff00 if 1 <= elapsed < 300 else 0x2495
        cpu.emu_start(CODE + 0x24f8, CODE + expected_end, count=100000)
        if (cpu.reg_read(UC_X86_REG_CS), cpu.reg_read(UC_X86_REG_IP)) != (CS, expected_end):
            raise ValueError(f'Original elapsed gate did not terminate: {elapsed}')
        accepted = cpu.reg_read(UC_X86_REG_IP) == 0xff00
        result = words(cpu)
        full.extend(struct.pack('<4H', accepted, *result))
        if accepted:
            if cpu.reg_read(UC_X86_REG_BP) != 0xbeef or cpu.reg_read(UC_X86_REG_SP) != 0xf006:
                raise ValueError('Original arithmetic return stack differs')
            gate[elapsed // 8] |= 1 << (elapsed % 8)
            accepted_words.extend(struct.pack('<3H', *result))
    if bytes(cpu.mem_read(CODE, 43552)) != image[:43552] or len(accepted_words) != 299 * 6:
        raise ValueError('Original code or accepted domain differs')
    for name, data in [('full-records.bin', full), ('gate-bits.bin', gate), ('accepted-words.bin', accepted_words)]:
        (out / name).write_bytes(data)

    scripts = [
        ('captured99', [(22, 43, 41), (22, 44, 40)]),
        ('captured98', [(23, 56, 41), (23, 57, 39)]),
        ('zero_retry', [(1, 2, 3), (1, 2, 3), (22, 43, 41), (22, 44, 40)]),
        ('hour_retry', [(59, 59, 98), (0, 0, 97), (23, 56, 41), (23, 57, 39)]),
        ('upper_retry', [(1, 2, 3), (1, 5, 3), (22, 43, 41), (22, 44, 40)]),
        ('tie128', [(1, 2, 0), (1, 3, 28)]),
        ('maximum299', [(1, 2, 0), (1, 4, 99)]),
        ('negative_retry', [(1, 2, 0), (1, 1, 0), (22, 43, 41), (22, 44, 40)]),
        ('word_wrap_accepted', [(0, 0, 0), (10, 55, 37)]),
        ('word_wrap_zero_retry', [(0, 0, 0), (10, 55, 36), (22, 43, 41), (22, 44, 40)]),
    ]
    cases = []
    for name, samples in scripts:
        cpu = emulator()
        registers(cpu, 0xbeef, 0xfe00)
        cpu.mem_write(DATA + 0x7f68, struct.pack('<H', 544))
        cpu.mem_write(0x400, b'\xf8')
        cpu.mem_write(0x8fe00, struct.pack('<2H', 0xff00, 0))
        events = []
        sample_index = 0

        def interrupt(cpu, number, user):
            nonlocal sample_index
            if number != 0x21 or cpu.reg_read(UC_X86_REG_AX) >> 8 != 0x2c or sample_index >= len(samples):
                raise RuntimeError('Unexpected original DOS service')
            minute, second, hundredth = samples[sample_index]
            sample_index += 1
            cpu.reg_write(UC_X86_REG_CX, minute)
            cpu.reg_write(UC_X86_REG_DX, second * 256 + hundredth)
            events.append(dict(kind='dos_time', minute=minute, second=second, hundredth=hundredth))

        def delay_enter(cpu, address, size, user):
            stack = cpu.reg_read(UC_X86_REG_SS) * 16 + cpu.reg_read(UC_X86_REG_SP)
            argument = struct.unpack('<H', bytes(cpu.mem_read(stack + 4, 2)))[0]
            events.append(dict(kind='crt_delay', argument=argument))

        cpu.hook_add(unicorn.UC_HOOK_INTR, interrupt)
        cpu.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, UC_X86_INS_IN)
        cpu.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, UC_X86_INS_OUT)
        delay_at = (CS + 0x84a) * 16 + 0x29c
        cpu.hook_add(unicorn.UC_HOOK_CODE, delay_enter, None, delay_at, delay_at)
        cpu.emu_start(CODE + 0x247f, CODE + 0xff00, count=100000000)
        if (cpu.reg_read(UC_X86_REG_CS), cpu.reg_read(UC_X86_REG_IP), cpu.reg_read(UC_X86_REG_BP),
            cpu.reg_read(UC_X86_REG_SP)) != (CS, 0xff00, 0xbeef, 0xfe04):
            raise ValueError('Original complete function did not return')
        if sample_index != len(samples) or bytes(cpu.mem_read(CODE, 43552)) != image[:43552]:
            raise ValueError('Original complete function used different input or modified code')
        result = words(cpu)
        cases.append(dict(name=name, samples=[dict(minute=m, second=s, hundredth=h) for m, s, h in samples],
            events=events, character_delay=result[0], auxiliary_delay=result[1], minimum_word=result[2]))
        (out / 'complete-functions.json').write_text(json.dumps(cases, indent=2) + '\n')
        print(json.dumps(dict(name=name, timing_words=result, service_events=len(events))), flush=True)

    sha = lambda data: hashlib.sha256(data).hexdigest()
    manifest = dict(schema=1, original_executable_sha256=EXE_SHA, unicorn=unicorn.__version__,
        producer_sha256=sha(Path(__file__).read_bytes()), relocated_image_sha256=sha(image),
        code_bytes_verified=43552, entry_ip=0x247f, arithmetic_entry_ip=0x24f8, retry_ip=0x2495,
        function_end_exclusive=0x2585, function_sha256=sha(image[0x247f:0x2585]),
        complete_function_executed=True, original_calls_stubbed=False, instruction_patches=0,
        scripted_dos_time_service=True, crt_calibration_word_seeded=544, com1_base_byte_seeded=248,
        natural_startup_claim=False, frame_timing_claim=False, whole_game_parity=False,
        elapsed_inputs=65536, accepted_inputs=299, full_records_sha256=sha(full),
        gate_bits_sha256=sha(gate), accepted_words_sha256=sha(accepted_words), cases=cases)
    for name, data in [('full-records.bin', full), ('gate-bits.bin', gate),
                       ('accepted-words.bin', accepted_words),
                       ('manifest.json', (json.dumps(manifest, indent=2) + '\n').encode())]:
        (out / name).write_bytes(data)
    if sum(path.stat().st_size for path in out.iterdir()) >= 1024 * 1024:
        raise ValueError('Original oracle exceeded its output reserve')
    return manifest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir()
    try:
        result = capture(args.root, args.out)
    except BaseException as error:
        (args.out / 'failure.json').write_text(json.dumps(dict(error=repr(error),
            original_executable_sha256=EXE_SHA, natural_startup_claim=False), indent=2) + '\n')
        raise
    print(json.dumps(dict(original_startup_capture='ok', elapsed_inputs=result['elapsed_inputs'],
        accepted_inputs=result['accepted_inputs'], complete_functions=len(result['cases']),
        original_calls_stubbed=False, natural_startup_claim=False)), flush=True)

if __name__ == '__main__':
    main()
