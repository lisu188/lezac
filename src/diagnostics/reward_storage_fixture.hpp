#pragma once

#include "diagnostics/transient_storage_fixture.hpp"

namespace lezac::diagnostics::reward_storage {

using transient_storage::byte;
using transient_storage::word;
using transient_storage::finish;

struct Header {
    uint32_t operations;
    std::array<uint8_t, 60 * 33> tiles{};
    std::array<uint16_t, 60 * 33> words{};
    std::array<gameplay::ActorSlots::Descriptor, 92> descriptors{};

    explicit Header(std::istream& input) {
        std::string magic(8, '\0');
        input.read(magic.data(), 8);
        if (magic != "LZRW0001") throw std::runtime_error("invalid reward request magic");
        const uint32_t low = word(input);
        operations = low | (static_cast<uint32_t>(word(input)) << 16);
        if (!operations || operations > 100000) throw std::runtime_error("invalid reward operation count");
        for (auto& value : tiles) value = byte(input);
        for (auto& value : words) value = word(input);
        transient_storage::readRows(input, descriptors);
    }

    gameplay::ActorSlots::Descriptor descriptor(uint16_t sprite) const {
        if (!sprite || sprite >= descriptors.size()) throw std::runtime_error("reward sprite outside descriptor bank");
        return descriptors[sprite];
    }
};

struct Seed {
    gameplay::ActorSlots::State storage;
    uint32_t rng;
    std::array<uint8_t, 2> pending{}, hits{}, alive{};

    explicit Seed(std::istream& input) : storage(transient_storage::readSeed(input)) {
        const uint32_t low = word(input);
        rng = low | (static_cast<uint32_t>(word(input)) << 16);
        for (auto& value : pending) value = byte(input);
        for (auto& value : hits) value = byte(input);
        for (auto& value : alive) value = byte(input);
        if (storage.visualCount != storage.count + 2 || storage.links[0][15] != 0 || storage.actors[0][1] != 1)
            throw std::runtime_error("unsupported reward fixture table shape");
        for (size_t player = 0; player < 2; ++player)
            if (pending[player] > 7 || alive[player] > 1) throw std::runtime_error("invalid reward player gates");
        std::array<bool, 33> seen{};
        for (size_t slot = 1; slot <= storage.count; ++slot) {
            const auto& raw = storage.actors[slot];
            if (raw[0] < 0x13 || raw[0] > 0x19 || raw[21] != 2 || raw[1] < 2 || raw[1] >= storage.visualCount || seen[raw[1]])
                throw std::runtime_error("unsupported reward fixture actor");
            seen[raw[1]] = true;
            for (const size_t at : {size_t{22}, size_t{29}}) {
                if (!raw[at] || !raw[at + 1] || !raw[at + 2] || raw[at] >= 92 || raw[at + 1] >= 92 || raw[at + 2] >= 92 ||
                    raw[at + 5] > 3 || (raw[at + 6] != 1 && raw[at + 6] != 255))
                    throw std::runtime_error("unsupported reward fixture animation");
            }
        }
    }
};

inline int16_t signedWord(const gameplay::ActorStorage::Visual& row, size_t offset) {
    return static_cast<int16_t>(row[offset] | (static_cast<uint16_t>(row[offset + 1]) << 8));
}

inline gameplay::BonusDrop decode(const gameplay::ActorSlots& slots, uint64_t order) {
    const auto& raw = slots.actor(order);
    const auto& row = slots.visual(order);
    gameplay::BonusDrop drop;
    drop.actorOrder = order;
    drop.type = static_cast<gameplay::BonusType>(raw[0] - 0x13);
    drop.timer = raw[2]; drop.hotspotY = raw[20];
    drop.x = signedWord(row, 0); drop.y = signedWord(row, 2);
    drop.vx8 = static_cast<int16_t>(raw[6] | (static_cast<uint16_t>(raw[7]) << 8));
    drop.vy8 = static_cast<int16_t>(raw[8] | (static_cast<uint16_t>(raw[9]) << 8));
    drop.fracX = raw[10]; drop.fracY = raw[12];
    drop.animation = slots.activeAnimation(order);
    return drop;
}

inline void writeHeader(std::ostream& output, uint32_t operations) {
    output.write("LZRO0001", 8);
    transient_storage::write(output, operations, 4);
}

inline void writeState(std::ostream& output, const gameplay::ActorSlots::State& state, uint32_t rng,
        const std::array<uint8_t, 2>& pending, const std::array<uint8_t, 2>& hits, const std::array<uint8_t, 2>& alive) {
    transient_storage::writeState(output, state);
    transient_storage::write(output, rng, 4);
    for (const auto& values : {pending, hits, alive}) for (const auto value : values) output.put(static_cast<char>(value));
}

} // namespace lezac::diagnostics::reward_storage
