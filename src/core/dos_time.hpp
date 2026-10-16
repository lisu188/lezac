#pragma once

#include "core/startup_timing.hpp"

#include <cstdint>
#include <functional>
#include <stdexcept>

namespace lezac::core {

struct DosTimeFields {
    uint8_t hour = 0, minute = 0, second = 0, hundredth = 0;
    constexpr DosClockSample gameClockSample() const { return {minute, second, hundredth}; }
    bool operator==(const DosTimeFields&) const = default;
};

// Pinned 64-bit DOSBox 0.74-3 profile, including its 32-bit multiply before widening.
constexpr DosTimeFields dosTimeFromBiosTicks(uint32_t biosTicks) {
    const auto scaled = static_cast<uint32_t>(biosTicks * uint32_t{5});
    const uint64_t hundredths = uint64_t{scaled} * 65536u / 59659u;
    const uint64_t seconds = hundredths / 100u;
    return {static_cast<uint8_t>(seconds / 3600u),
            static_cast<uint8_t>((seconds % 3600u) / 60u),
            static_cast<uint8_t>(seconds % 60u), static_cast<uint8_t>(hundredths % 100u)};
}

struct DosGetTimeRegisters {
    uint16_t ax = 0, bx = 0, cx = 0, dx = 0, si = 0, di = 0, bp = 0;
    uint16_t cs = 0, ds = 0, es = 0, ss = 0, sp = 0, ip = 0;
    uint32_t flags = 0x0202;
    bool operator==(const DosGetTimeRegisters&) const = default;
};

struct DosGetTimeBus {
    std::function<uint32_t()> readBiosTicks;
    std::function<uint16_t(uint16_t, uint16_t)> readWord;
    std::function<void(uint16_t, uint16_t, uint16_t)> writeWord;
    std::function<void(uint16_t, uint16_t, uint32_t)> writeDword;
};

struct DosGetTimeSnapshot {
    DosGetTimeRegisters registers{};
    uint16_t callbackSegment = 0, callbackBase = 0, pspSegment = 0;
    uint32_t idToggleMask = 0;
    uint32_t definedFlags = 0x0700;
    uint64_t dispatchedInstructions = 0;
    bool returned = false;
    bool operator==(const DosGetTimeSnapshot&) const = default;
};

// Entry is CB_INT21's FE38 callback instruction, after its STI. No IRQ scheduler is implied.
class DosGetTimeOperation {
public:
    DosGetTimeOperation(DosGetTimeRegisters registers, uint16_t callbackBase,
                        uint16_t pspSegment, uint32_t idToggleMask)
        : state_{registers, registers.cs, callbackBase, pspSegment, idToggleMask} {
        if (callbackBase > 0xfff0 || registers.ip != callbackBase + 1u || (registers.ax >> 8) != 0x2c ||
                (idToggleMask != 0 && idToggleMask != 0x00200000))
            throw std::invalid_argument("DOS GetTime callback entry differs");
    }
    explicit DosGetTimeOperation(DosGetTimeSnapshot snapshot) : state_(snapshot) {}

    const DosGetTimeSnapshot& snapshot() const noexcept { return state_; }
    bool returned() const noexcept { return state_.returned; }

    uint64_t advance(uint64_t budget, const DosGetTimeBus& bus) {
        uint64_t consumed = 0;
        while (consumed < budget && !state_.returned) {
            advanceOne(bus);
            ++state_.dispatchedInstructions;
            ++consumed;
        }
        return consumed;
    }

private:
    void advanceOne(const DosGetTimeBus& bus) {
        auto& r = state_.registers;
        if (r.cs != state_.callbackSegment)
            throw std::domain_error("DOS GetTime left the recovered callback segment");
        const uint16_t offset = static_cast<uint16_t>(r.ip - state_.callbackBase);
        switch (offset) {
        case 1: {
            const uint32_t stack = (uint32_t{r.ss} << 16) | static_cast<uint16_t>(r.sp - 18u);
            bus.writeDword(state_.pspSegment, 0x002e, stack);
            const auto fields = dosTimeFromBiosTicks(bus.readBiosTicks());
            r.cx = static_cast<uint16_t>((uint16_t{fields.hour} << 8) | fields.minute);
            r.dx = static_cast<uint16_t>((uint16_t{fields.second} << 8) | fields.hundredth);
            r.ip = static_cast<uint16_t>(state_.callbackBase + 7u);
            break;
        }
        case 7: {
            const uint16_t nextSp = static_cast<uint16_t>(r.sp - 2u);
            bus.writeWord(r.ss, nextSp, r.cx);
            r.sp = nextSp;
            ++r.ip;
            break;
        }
        case 8:
            r.cx = 0x0140;
            r.ip = static_cast<uint16_t>(state_.callbackBase + 11u);
            break;
        case 11:
            r.cx = static_cast<uint16_t>(r.cx - 1u);
            if (r.cx == 0) r.ip = static_cast<uint16_t>(state_.callbackBase + 13u);
            break;
        case 13:
            r.cx = bus.readWord(r.ss, r.sp);
            r.sp = static_cast<uint16_t>(r.sp + 2u);
            ++r.ip;
            break;
        case 14: {
            const uint16_t ip = bus.readWord(r.ss, r.sp);
            const uint16_t cs = bus.readWord(r.ss, static_cast<uint16_t>(r.sp + 2u));
            const uint16_t flags = bus.readWord(r.ss, static_cast<uint16_t>(r.sp + 4u));
            r.sp = static_cast<uint16_t>(r.sp + 6u);
            r.ip = ip;
            r.cs = cs;
            const uint32_t mask = 0x7fd5u | state_.idToggleMask;
            r.flags = (r.flags & ~mask) | (uint32_t{flags} & mask) | 2u;
            state_.definedFlags |= mask | 2u;
            state_.returned = true;
            break;
        }
        default: throw std::domain_error("DOS GetTime reached an unrecovered instruction");
        }
    }

    DosGetTimeSnapshot state_;
};

}
