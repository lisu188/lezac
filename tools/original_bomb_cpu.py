"""Bounded unmodified-original actor execution for recovery analysis."""
from collections import Counter
import hashlib
from pathlib import Path
import struct
import sys
import unicorn
from unicorn.x86_const import (
    UC_X86_INS_IN, UC_X86_INS_OUT, UC_X86_REG_BP, UC_X86_REG_CS,
    UC_X86_REG_DS, UC_X86_REG_EFLAGS, UC_X86_REG_IP, UC_X86_REG_SP, UC_X86_REG_SS,
)

EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
LEVELS_SHA = 'd8b553871014108515d6af05b0853de8ccc22e4d3e44d63533ba1167fdc8c7b2'
DESCRIPTOR_SHA = '8604621c87c91e23bbe02f66cedfb312fd95b2c5a5cc429b0eca37872345f55e'


def sha(value):
    return hashlib.sha256(value).hexdigest()


class BombCPU:
    DATA = 0x1aa20

    def __init__(self, root):
        if sys.flags.optimize:
            raise RuntimeError('optimized Python is not supported by original bomb analysis')
        self.root = Path(root)
        self.raw = (self.root / 'LEZAC.EXE').read_bytes()
        assert sha(self.raw) == EXE_SHA and unicorn.__version__ == '2.1.4'
        assert sha((self.root / 'LIVELS.SCH').read_bytes()) == LEVELS_SHA
        native = (self.root / 'tests/fixtures/fracture_actor_original.txt').read_bytes()
        assert sha(native) == DESCRIPTOR_SHA
        self.descriptors = bytes.fromhex(next(line.split('=', 1)[1] for line in native.decode().splitlines()
                                              if line.startswith('sprites descriptors=')))
        assert len(self.descriptors) == 368
        header = struct.unpack_from('<14H', self.raw)
        assert header[3] == 468 and header[4] * 16 == 0x770
        image = bytearray(self.raw[0x770:])
        for index in range(header[3]):
            offset, segment = struct.unpack_from('<HH', self.raw, header[12] + 4 * index)
            address = segment * 16 + offset
            struct.pack_into('<H', image, address,
                             (struct.unpack_from('<H', image, address)[0] + 0x1000) & 65535)
        self.cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
        self.cpu.mem_map(0, 1024**2)
        self.cpu.mem_write(0x10000, bytes(image))
        self.initial_memory = bytes(self.cpu.mem_read(0, 1024**2))
        self.initial_context = self.cpu.context_save()
        self.boundaries = {}
        self.entries = Counter()
        self.instructions = 0
        self.slot = 1
        self.cpu.hook_add(unicorn.UC_HOOK_INTR, self.unexpected)
        self.cpu.hook_add(unicorn.UC_HOOK_INSN, self.unexpected, None, 1, 0, UC_X86_INS_IN)
        self.cpu.hook_add(unicorn.UC_HOOK_INSN, self.unexpected, None, 1, 0, UC_X86_INS_OUT)
        self.cpu.hook_add(unicorn.UC_HOOK_CODE, self.observe)

    @staticmethod
    def unexpected(*unused):
        raise RuntimeError('original interrupt or hardware I/O is forbidden')

    def observe(self, cpu, address, size, user):
        self.instructions += 1
        if address in (0x12f9f, 0x106ab, 0x16053, 0x14155, 0x1370e, 0x1165a):
            self.entries[hex(address)] += 1
        if address in (0x16c5e, 0x16c7e, 0x175b4, 0x175cb):
            self.boundaries[hex(address)] = self.actor_and_visual()

    def actor_and_visual(self):
        actor = bytes(self.cpu.mem_read(self.DATA + 0x1bae + self.slot * 38, 38))
        visual = bytes(self.cpu.mem_read(self.DATA + 0xc21e + actor[1] * 8, 8))
        return actor, visual

    def registers(self, bp, sp):
        for register, value in ((UC_X86_REG_CS, 0x1000), (UC_X86_REG_DS, 0x1aa2),
                                (UC_X86_REG_SS, 0x8000), (UC_X86_REG_BP, bp),
                                (UC_X86_REG_SP, sp), (UC_X86_REG_EFLAGS, 0x202)):
            self.cpu.reg_write(register, value)

    def assert_return(self, ip, bp, sp):
        actual = tuple(self.cpu.reg_read(reg) for reg in (
            UC_X86_REG_CS, UC_X86_REG_IP, UC_X86_REG_BP, UC_X86_REG_SP))
        assert actual == (0x1000, ip, bp, sp), actual

    def reset(self, level, weapon, x, y, vx, vy, visual_cursor=2, slot=1, stale=None):
        cpu, data = self.cpu, self.DATA
        cpu.context_restore(self.initial_context)
        cpu.mem_write(0, self.initial_memory)
        self.slot = slot
        self.boundaries.clear()
        self.entries.clear()
        self.instructions = 0
        cpu.mem_write(data + 0x1bae, bytes(31 * 38))
        if stale is not None:
            assert len(stale) == 38
            cpu.mem_write(data + 0x1bae + slot * 38, stale)
        cpu.mem_write(data + 0xc21e, bytes(33 * 8))
        cpu.mem_write(data + 0xc322, self.descriptors)
        cpu.mem_write(data + 0xc496, bytes((visual_cursor,)))
        cpu.mem_write(data + 0x208d, bytes((slot - 1,)))
        cpu.mem_write(data + 0x2072, b'\xff\xff')
        cpu.mem_write(data + 0x79a3, bytes((200 if weapon == 4 else weapon * 10 + 10,)))
        cpu.mem_write(data + 0x1b73, bytes((weapon,)))
        cpu.mem_write(data + 0x1b67 + weapon, b'\x05')
        cpu.mem_write(data + 0x79e6, bytes(2))
        cpu.mem_write(data + 0x2076, struct.pack('<6H', 0, 0, 0, 0, 199, 0))
        cpu.mem_write(data + 0x1afe, struct.pack('<I', 0x12345678))
        cpu.mem_write(0x40000, bytes(65536))
        cpu.mem_write(0x50000, bytes(65536))
        cpu.mem_write(0x40000, bytes(level['tiles']))
        cpu.mem_write(0x50000, struct.pack('<' + 'H' * len(level['words']), *level['words']))
        cpu.mem_write(data + 0xc1e0, struct.pack('<HH', 0, 0x4000))
        cpu.mem_write(data + 0xc1fe, struct.pack('<H', 0x4000))
        cpu.mem_write(data + 0xc204, struct.pack('<HH', level['width'], level['height']))
        cpu.mem_write(data + 0x206e, struct.pack('<H', 0x5000))
        cpu.mem_write(data + 0x6612, struct.pack('<HH', 0, 0x5000))
        cpu.mem_write(data + 0x78c4, struct.pack('<H', 0x4000))
        self.registers(0xff00, 0xfe00)
        cpu.emu_start(0x1293d, 0x12949, count=4)
        assert cpu.reg_read(UC_X86_REG_IP) == 0x2949
        for offset, value in ((-0x2c, x), (-0x2e, y), (-0x0c, vx), (-0x0e, vy)):
            cpu.mem_write(0x8ff00 + offset, struct.pack('<H', value & 65535))
        cpu.mem_write(0x8ff00 - 0x12, bytes((weapon,)))
        cpu.mem_write(0x8ff00 - 0x1d, b'\x00')
        cpu.emu_start(0x16c25, 0x16cb3, count=10000)
        self.assert_return(0x6cb3, 0xff00, 0xfe00)
        assert bytes(cpu.mem_read(data + 0x208d, 1)) == bytes((slot,))
        assert bytes(cpu.mem_read(data + 0xc496, 1)) == bytes((visual_cursor + 1,))
        assert '0x16c5e' in self.boundaries and '0x16c7e' in self.boundaries
        return self.boundaries['0x16c5e']

    def update(self, tick):
        self.boundaries.clear()
        self.instructions = 0
        self.cpu.mem_write(self.DATA + 0x78c2, struct.pack('<H', tick & 65535))
        self.registers(0xf000, 0xff00)
        self.cpu.mem_write(0x8ff00, struct.pack('<3H', 0xff00, 0x1bae + self.slot * 38, 0x1aa2))
        self.cpu.emu_start(0x16053, 0x1ff00, count=1000000)
        self.assert_return(0xff00, 0xf000, 0xff06)
        assert '0x175b4' in self.boundaries, (tick, self.boundaries)
        return self.boundaries['0x175b4']
