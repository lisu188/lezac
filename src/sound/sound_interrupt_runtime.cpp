#include "sound/sound_engine.hpp"
#include "core/timer_irq.hpp"

#include <array>
#include <stdexcept>

namespace lezac::sound {

SoundInterruptAction SoundEngine::advanceSoundInterruptWorkOrdered() {
    constexpr uint16_t data = 0x1aa2, bank = 0x3000, stackSegment = 0x8000, stackBase = 0xfdb0;
    std::array<uint8_t, 112> stack{};
    const auto putStack = [&](uint16_t offset, uint16_t value) {
        const auto at = static_cast<unsigned>(offset - stackBase);
        stack.at(at) = static_cast<uint8_t>(value);
        stack.at(at + 1) = static_cast<uint8_t>(value >> 8);
    };
    putStack(0xfe00, 0x0100); putStack(0xfe02, 0x9000); putStack(0xfe04, 0x0202);

    const auto readByte = [&](uint16_t segment, uint16_t offset) -> uint8_t {
        if (segment == stackSegment) return stack.at(static_cast<unsigned>(offset - stackBase));
        if (segment == bank) {
            if (offset >= sounds_.payload.size())
                throw std::runtime_error("sound interrupt reads outside the recovered bank extent");
            return sounds_.payload[offset];
        }
        if (segment == data) {
            switch (offset) {
            case 0x78c0: return static_cast<uint8_t>(soundLatch_.latchedOffset);
            case 0x78c1: return static_cast<uint8_t>(soundLatch_.latchedOffset >> 8);
            case 0x79a0: return soundInterrupt_.accumulator;
            case 0x79a1: return soundInterrupt_.gateTick;
            case 0x79a2: return soundInterrupt_.periodTicks;
            case 0x79c0: case 0x79c1: case 0x79c2: return 0;
            case 0x79c3: return 0x30;
            case 0x79c4: return soundLatch_.active ? 1 : 0;
            }
        }
        throw std::domain_error("sound IRQ read left its owned memory");
    };
    const auto writeByte = [&](uint16_t segment, uint16_t offset, uint8_t value) {
        if (segment == stackSegment) {
            stack.at(static_cast<unsigned>(offset - stackBase)) = value;
            return;
        }
        if (segment == data) {
            switch (offset) {
            case 0x78c0: soundLatch_.latchedOffset = static_cast<uint16_t>((soundLatch_.latchedOffset & 0xff00u) | value); return;
            case 0x78c1: soundLatch_.latchedOffset = static_cast<uint16_t>((soundLatch_.latchedOffset & 0x00ffu) | (uint16_t{value} << 8)); return;
            case 0x79a0: soundInterrupt_.accumulator = value; return;
            case 0x79a1: soundInterrupt_.gateTick = value; return;
            case 0x79a2: soundInterrupt_.periodTicks = value; return;
            case 0x79c4: soundLatch_.active = value != 0; return;
            }
        }
        throw std::domain_error("sound IRQ write left its owned memory");
    };
    uint8_t port61 = speaker_.enabled ? 3 : 0;
    core::TimerIrqBus bus{
        readByte,
        [&](uint16_t segment, uint16_t offset) {
            return static_cast<uint16_t>(readByte(segment, offset) |
                (uint16_t{readByte(segment, static_cast<uint16_t>(offset + 1u))} << 8));
        },
        [](uint16_t, uint16_t) -> uint32_t { throw std::domain_error("unexpected BIOS read in sound IRQ"); },
        writeByte,
        [&](uint16_t segment, uint16_t offset, uint16_t value) {
            writeByte(segment, offset, static_cast<uint8_t>(value));
            writeByte(segment, static_cast<uint16_t>(offset + 1u), static_cast<uint8_t>(value >> 8));
        },
        [](uint16_t, uint16_t, uint32_t) { throw std::domain_error("unexpected BIOS write in sound IRQ"); },
        [&](uint16_t port) {
            if (port != 0x61) throw std::domain_error("unexpected sound IRQ input port");
            ++soundInterruptWork_.portReads;
            return port61;
        },
        [&](uint16_t port, uint8_t value) {
            if (port != 0x61 && port != 0x42 && port != 0x43)
                throw std::domain_error("unexpected sound IRQ output port");
            ++soundInterruptWork_.portWrites;
            if (port == 0x61) port61 = value;
        }
    };
    core::TimerIrqRegisters registers;
    registers.cs = 0x1000; registers.ip = 0x0fbe; registers.ss = stackSegment; registers.sp = 0xfe00;
    registers.flags = 0x0002;
    core::TimerIrqOperation operation(registers, 0x1000, 0, false);
    SoundInterruptAction action;
    while (!operation.returned()) {
        const auto& r = operation.snapshot().registers;
        // Keep the existing unsupported-bank failure boundary; allocator bytes are not owned here.
        if (r.cs == 0x1000 && r.ip == 0x1014 &&
            (soundLatch_.latchedOffset >= sounds_.stepCount ||
             static_cast<size_t>(soundLatch_.latchedOffset) * kSoundStepSize + 3 >= sounds_.payload.size()))
            throw std::runtime_error("sound interrupt reads outside the recovered bank extent");
        if (r.cs == 0x184a && r.ip == 0x02cf) action = {r.bx, true, action.silence};
        if (r.cs == 0x184a && r.ip == 0x02f6) action.silence = true;
        if (operation.snapshot().dispatchedInstructions >= 256)
            throw std::domain_error("sound IRQ exceeded recovered work boundary");
        operation.advance(1, bus);
        ++soundInterruptWork_.dispatchedInstructions;
    }
    ++soundInterruptWork_.callbacks;
    return action;
}

} // namespace lezac::sound
