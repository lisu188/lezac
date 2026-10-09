#pragma once

#include <cstdint>
#include <stdexcept>

namespace lezac::gameplay {

enum class DamageLaneSeed { Failed, Collapse, Debris };

// Memory exposes byte reads/writes in the original 16-bit DS address space.
template <typename Memory>
uint16_t damageLaneWord(Memory& memory, uint16_t address) {
    return static_cast<uint16_t>(memory.read(address) |
        (static_cast<uint16_t>(memory.read(static_cast<uint16_t>(address + 1))) << 8));
}

template <typename Memory>
void writeDamageLaneWord(Memory& memory, uint16_t address, uint16_t value) {
    memory.write(address, static_cast<uint8_t>(value));
    memory.write(static_cast<uint16_t>(address + 1), static_cast<uint8_t>(value >> 8));
}

// 1000:3A7E / 3B18: newest-first lookup; a miss preserves cursor and phase.
template <typename Memory>
void lookupDamageLaneBytes(Memory& memory, bool reverse) {
    const uint16_t word = damageLaneWord(memory, 0x2074);
    if ((word & 0x8000) == 0) {
        memory.write(0x661e, 0);
        return;
    }
    const bool debris = (word & 0x7fff) >= 0x4000;
    const uint16_t stride = debris ? 11 : 15;
    const uint16_t bound = damageLaneWord(memory, debris ? 0x207e : 0x2080);
    const uint16_t last = static_cast<uint16_t>(bound - 1);
    if (last == (debris ? 198 : 65535)) return;
    uint16_t offset = static_cast<uint16_t>(last * stride + (debris ? 2 : 4));
    uint16_t remaining = static_cast<uint16_t>(bound - (debris ? 199 : 0));
    do {
        const uint16_t address = static_cast<uint16_t>((debris ? 0x209e : 0x6620) + offset);
        if (damageLaneWord(memory, address) == word) {
            memory.write(0x661e, memory.read(static_cast<uint16_t>(address + 2 + reverse)));
            writeDamageLaneWord(memory, 0x2074, static_cast<uint16_t>(offset / stride + 1));
            return;
        }
        offset = static_cast<uint16_t>(offset - stride);
    } while (--remaining != 0);
}

inline uint16_t damageLaneWriteAddress(uint16_t tag, bool reverse) {
    return tag < 0x4e20
        ? static_cast<uint16_t>(0x6617 + reverse + 15u * tag)
        : static_cast<uint16_t>(0x2097 + reverse + 11u * (tag - 0x4e20));
}

inline int damageLaneSignedByte(uint8_t byte) {
    return byte < 128 ? byte : static_cast<int>(byte) - 256;
}

// 1000:3BB2 / 3D46. Seeding must update the same memory view before returning.
template <typename Memory, typename Seed>
void blendDamageLaneBytes(Memory& memory, uint16_t caller, uint8_t ownWeight,
                          bool reverse, Seed&& seed) {
    uint16_t weight = ownWeight;
    uint32_t sum = static_cast<uint32_t>(damageLaneSignedByte(memory.read(caller)) * ownWeight);
    const uint16_t contacts = damageLaneWord(memory, 0x2078);
    for (uint32_t index = 1; index <= contacts; ++index) {
        const uint16_t word = damageLaneWord(memory, static_cast<uint16_t>(0x655c + 2 * index));
        uint16_t tag;
        uint8_t contribution;
        if ((word & 0x8000) == 0) {
            const auto result = seed(static_cast<uint16_t>(damageLaneWord(memory,
                static_cast<uint16_t>(0x6598 + 2 * index)) / 2));
            if (result == DamageLaneSeed::Failed) return;
            if (result == DamageLaneSeed::Debris) {
                tag = static_cast<uint16_t>(damageLaneWord(memory, 0x207e) + 0x4e20);
                writeDamageLaneWord(memory, static_cast<uint16_t>(0x65d4 + 2 * index), tag);
                contribution = 1;
            } else {
                tag = damageLaneWord(memory, 0x2080);
                writeDamageLaneWord(memory, static_cast<uint16_t>(0x65d4 + 2 * index), tag);
                contribution = memory.read(static_cast<uint16_t>(0x661f + 15u * damageLaneWord(memory, 0x2080)));
            }
        } else {
            writeDamageLaneWord(memory, 0x2074, word);
            lookupDamageLaneBytes(memory, reverse);
            tag = damageLaneWord(memory, 0x2074);
            if ((word & 0x7fff) >= 0x4000) {
                tag = static_cast<uint16_t>(tag + 0x4e20);
                writeDamageLaneWord(memory, 0x2074, tag);
                contribution = 1;
            } else {
                contribution = memory.read(static_cast<uint16_t>(0x661f + 15u * tag));
            }
            writeDamageLaneWord(memory, static_cast<uint16_t>(0x65d4 + 2 * index), tag);
            sum += static_cast<uint32_t>(damageLaneSignedByte(memory.read(0x661e)) * contribution);
        }
        weight = static_cast<uint16_t>(weight + contribution);
    }
    if (weight == 0) throw std::domain_error("original damage lane division by zero");
    const int64_t signedSum = sum < 0x80000000u ? static_cast<int64_t>(sum)
        : static_cast<int64_t>(sum) - 0x100000000LL;
    const uint8_t phase = static_cast<uint8_t>(signedSum / weight);
    const uint16_t targets = damageLaneWord(memory, 0x2078);
    for (uint32_t index = 1; index <= targets; ++index) {
        const uint16_t tag = damageLaneWord(memory, static_cast<uint16_t>(0x65d4 + 2 * index));
        memory.write(damageLaneWriteAddress(tag, reverse), phase);
    }
    memory.write(caller, phase);
}

}  // namespace lezac::gameplay
