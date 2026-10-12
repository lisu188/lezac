#pragma once

#include "diagnostics/reward_storage_fixture.hpp"
#include "sound/sound_engine.hpp"

namespace lezac::diagnostics::corpse_storage {

using reward_storage::byte;
using reward_storage::word;
using reward_storage::finish;
using reward_storage::signedWord;

struct Header : reward_storage::Header {
    explicit Header(std::istream& input) : reward_storage::Header(input, "LZRC0001") {}
};

struct Seed {
    gameplay::ActorSlots::State storage;
    uint32_t rng;
    std::array<uint8_t, 2> pending{}, hits{}, alive{};
    uint8_t roll, requestPriority;
    uint16_t requestCursor;
    sound::SoundLatch latch;

    explicit Seed(std::istream& input) : storage(transient_storage::readSeed(input)) {
        const uint32_t low = word(input);
        rng = low | (static_cast<uint32_t>(word(input)) << 16);
        for (auto& value : pending) value = byte(input);
        for (auto& value : hits) value = byte(input);
        for (auto& value : alive) value = byte(input);
        roll = byte(input);
        requestCursor = word(input);
        requestPriority = byte(input);
        latch.currentSelector = byte(input);
        latch.latchedOffset = word(input);
        const uint8_t active = byte(input);
        if (active > 1) throw std::runtime_error("invalid corpse sound flag");
        latch.active = active != 0;
        if (!storage.count || storage.visualCount != storage.count + 2 || storage.links[0][15] || storage.actors[0][1] != 1)
            throw std::runtime_error("unsupported corpse fixture table shape");
        for (size_t player = 0; player < 2; ++player)
            if (pending[player] > 7 || alive[player] != 0) throw std::runtime_error("unsupported corpse player gates");
        std::array<bool, 33> seen{};
        size_t corpses = 0;
        for (size_t slot = 1; slot <= storage.count; ++slot) {
            const auto& raw = storage.actors[slot];
            corpses += raw[0] == 0x0c && raw[21] == 2;
            if (!((raw[0] == 0x0c && raw[21] == 2) || (raw[0] == 0x0b && raw[21] == 5)) ||
                raw[1] < 2 || raw[1] >= storage.visualCount || seen[raw[1]])
                throw std::runtime_error("unsupported corpse fixture actor");
            seen[raw[1]] = true;
            for (const size_t at : {size_t{22}, size_t{29}}) {
                if (!raw[at] || !raw[at + 1] || !raw[at + 2] || raw[at] >= 92 || raw[at + 1] >= 92 || raw[at + 2] >= 92 ||
                    raw[at + 5] > 3 || (raw[at + 6] != 1 && raw[at + 6] != 255))
                    throw std::runtime_error("unsupported corpse fixture animation");
            }
        }
        if (corpses != 1) throw std::runtime_error("corpse seed requires one corpse");
    }
};

inline gameplay::ActiveMonster decode(const gameplay::ActorSlots& slots, uint64_t order) {
    const auto& raw = slots.actor(order);
    const auto& row = slots.visual(order);
    gameplay::ActiveMonster corpse;
    corpse.actorOrder = order;
    corpse.kind = raw[0]; corpse.behavior = raw[21];
    corpse.hotspotY = static_cast<int8_t>(raw[20]);
    corpse.x = signedWord(row, 0);
    corpse.y = static_cast<int16_t>(signedWord(row, 2) - corpse.hotspotY);
    corpse.vx8 = static_cast<int16_t>(raw[6] | (static_cast<uint16_t>(raw[7]) << 8));
    corpse.vy8 = static_cast<int16_t>(raw[8] | (static_cast<uint16_t>(raw[9]) << 8));
    corpse.fracX = raw[10]; corpse.fracY = raw[12];
    corpse.stateTimer = 2 * raw[2];
    gameplay::setMonsterAnimation(corpse, slots.activeAnimation(order));
    corpse.animationBackup = slots.animationBackup(order);
    corpse.deathRewardPending = true;
    return corpse;
}

inline void writeHeader(std::ostream& output, uint32_t operations) {
    output.write("LZCO0001", 8);
    transient_storage::write(output, operations, 4);
}

inline void writeState(std::ostream& output, const gameplay::ActorSlots::State& state, uint32_t rng,
        const std::array<uint8_t, 2>& pending, const std::array<uint8_t, 2>& hits, const std::array<uint8_t, 2>& alive,
        uint8_t roll, const sound::SoundEngine& sound) {
    reward_storage::writeState(output, state, rng, pending, hits, alive);
    output.put(static_cast<char>(roll));
    transient_storage::write(output, sound.requestCursor(), 2);
    output.put(static_cast<char>(sound.requestSelector()));
    const auto latch = sound.latch();
    output.put(static_cast<char>(latch.currentSelector));
    transient_storage::write(output, latch.latchedOffset, 2);
    output.put(static_cast<char>(latch.active));
}

} // namespace lezac::diagnostics::corpse_storage
