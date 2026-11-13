#pragma once

#include "core/bios_keyboard_tables.hpp"
#include "core/timer_irq.hpp"

namespace lezac::core {

enum class BiosKeyboardResult { Returned, NeedIdle };

// Pinned VGA/US, SDL>=1.2.14 lock semantics, no loaded DOS keyboard layout.
// Pause exposes the real CALLBACK_Idle handoff; nested execution belongs to the caller.
inline BiosKeyboardResult handleBiosKeyboardScan(uint8_t scan, const TimerIrqBus& bus) {
    const auto start = bus.readWord(0x40, 0x80), end = bus.readWord(0x40, 0x82);
    const auto head = bus.readWord(0x40, 0x1a), tail = bus.readWord(0x40, 0x1c);
    if (start != 0x1e || end != 0x3e || head < start || head >= end || tail < start || tail >= end ||
        (head & 1u) || (tail & 1u))
        throw std::domain_error("BIOS IRQ1 ring differs from the pinned VGA profile");
    auto flags1 = bus.readByte(0x40, 0x17), flags2 = bus.readByte(0x40, 0x18);
    auto flags3 = bus.readByte(0x40, 0x96), leds = bus.readByte(0x40, 0x97);
    const auto add = [&](uint16_t key) {
        if (!key || (bus.readByte(0x40, 0x18) & 8u)) return;
        const auto currentTail = bus.readWord(0x40, 0x1c);
        auto next = static_cast<uint16_t>(currentTail + 2u);
        if (next >= end) next = start;
        if (next == bus.readWord(0x40, 0x1a)) return;
        bus.writeWord(0x40, currentTail, key);
        bus.writeWord(0x40, 0x1c, next);
    };
    switch (scan) {
    case 0xfa: break;
    case 0xe1: flags3 |= 1; break;
    case 0xe0: flags3 |= 2; break;
    case 0x1d:
        if (!(flags3 & 1u)) {flags1 |= 4; if (flags3 & 2u) flags3 |= 4; else flags2 |= 1;}
        break;
    case 0x9d:
        if (!(flags3 & 1u)) {
            if (flags3 & 2u) flags3 &= 0xfb; else flags2 &= 0xfe;
            if (!(flags3 & 4u) && !(flags2 & 1u)) flags1 &= 0xfb;
        }
        break;
    case 0x2a: flags1 |= 2; break;
    case 0xaa: flags1 &= 0xfd; break;
    case 0x36: flags1 |= 1; break;
    case 0xb6: flags1 &= 0xfe; break;
    case 0x38:
        flags1 |= 8; if (flags3 & 2u) flags3 |= 8; else flags2 |= 2;
        break;
    case 0xb8:
        if (flags3 & 2u) flags3 &= 0xf7; else flags2 &= 0xfd;
        if (!(flags3 & 8u) && !(flags2 & 2u)) {
            flags1 &= 0xf7;
            const auto token = bus.readByte(0x40, 0x19);
            if (token) {add(token); bus.writeByte(0x40, 0x19, 0);}
        }
        break;
    case 0x3a: flags2 |= 0x40; break;
    case 0xba: flags1 ^= 0x40; flags2 &= 0xbf; leds ^= 4; break;
    case 0x45:
        if (flags3 & 1u) {
            flags3 &= 0xfe;
            bus.writeByte(0x40, 0x96, flags3);
            if (!(flags2 & 1u) && !(flags2 & 8u)) {
                bus.writeByte(0x40, 0x18, static_cast<uint8_t>(flags2 | 8u));
                bus.outByte(0x20, 0x20);
                return BiosKeyboardResult::NeedIdle;
            }
        } else flags2 |= 0x20;
        break;
    case 0xc5:
        if (flags3 & 1u) flags3 &= 0xfe;
        else {flags1 ^= 0x20; flags2 &= 0xdf; leds ^= 2;}
        break;
    case 0x46: flags2 |= 0x10; break;
    case 0xc6: flags1 ^= 0x10; flags2 &= 0xef; leds ^= 1; break;
    case 0xd2:
        if (flags3 & 2u) {flags1 ^= 0x80; flags2 &= 0x7f;}
        break;
    case 0x47: case 0x48: case 0x49: case 0x4b: case 0x4c: case 0x4d:
    case 0x4f: case 0x50: case 0x51: case 0x52: case 0x53: {
        const auto& entry = detail::biosScanAscii[scan];
        if (flags3 & 2u) {
            if (scan == 0x52) flags2 |= 0x80;
            if (flags1 & 8u) add(static_cast<uint16_t>(entry[0] + 0x5000u));
            else if (flags1 & 4u) add(static_cast<uint16_t>((entry[2] & 0xff00u) | 0xe0u));
            else add(static_cast<uint16_t>((entry[(flags1 & 0x23u) ? 1u : 0u] & 0xff00u) | 0xe0u));
        } else if (flags1 & 8u) {
            bus.writeByte(0x40, 0x19, static_cast<uint8_t>(bus.readByte(0x40, 0x19) * 10u + (entry[3] & 255u)));
        } else if (flags1 & 4u) add(entry[2]);
        else add(entry[(flags1 & 0x23u) ? 1u : 0u]);
        break;
    }
    default:
        if (!(scan & 0x80u) && scan < detail::biosScanAscii.size()) {
            const auto& entry = detail::biosScanAscii[scan];
            auto key = entry[(flags1 & 8u) ? 3u : (flags1 & 4u) ? 2u : (flags1 & 3u) ? 1u : 0u];
            const auto ascii = key & 255u;
            if (flags1 & 0x40u) {
                if ((flags1 & 3u) && ascii > 0x40 && ascii < 0x5b) key = entry[0];
                else if (!(flags1 & 3u) && ascii > 0x60 && ascii < 0x7b) key = entry[1];
            }
            if (flags3 & 2u) {
                if (scan == 0x1c) key = flags1 & 8u ? 0xa600 : static_cast<uint16_t>((key & 255u) | 0xe000u);
                else if (scan == 0x35) key = flags1 & 8u ? 0xa400 : flags1 & 4u ? 0x9500 : 0xe02f;
            }
            add(key);
        }
        break;
    }
    if (scan != 0xe0) flags3 &= 0xfd;
    bus.writeByte(0x40, 0x17, flags1);
    if (!(scan & 0x80u)) flags2 &= 0xf7;
    bus.writeByte(0x40, 0x18, flags2);
    bus.writeByte(0x40, 0x96, flags3);
    bus.writeByte(0x40, 0x97, leds);
    return BiosKeyboardResult::Returned;
}

}
