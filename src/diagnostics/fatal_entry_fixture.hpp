#pragma once

#include "diagnostics/corpse_storage_fixture.hpp"
#include "gameplay/monster_spawners.hpp"

namespace lezac::diagnostics::fatal_entry {

using corpse_storage::byte;
using corpse_storage::word;
using corpse_storage::finish;
using corpse_storage::signedWord;

struct Header : reward_storage::Header {
    explicit Header(std::istream& input) : reward_storage::Header(input, "LZFE0001") {}
};

struct Seed {
    gameplay::ActorSlots::State storage;
    uint32_t rng;
    std::array<uint8_t, 2> pending{}, hits{}, alive{};
    uint8_t roll, requestPriority;
    uint16_t requestCursor;
    sound::SoundLatch latch;
    gameplay::MonsterSpawnerStorage::State spawners{};
    int8_t damage;

    Seed(std::istream& input, uint8_t target) : storage(transient_storage::readSeed(input)) {
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
        if (active > 1) throw std::runtime_error("invalid fatal-entry sound flag");
        latch.active = active != 0;
        transient_storage::readRows(input, spawners);
        damage = static_cast<int8_t>(byte(input));
        if (!target || target > storage.count || storage.visualCount != storage.count + 2 ||
            storage.links[0][15] || storage.actors[0][1] != 1)
            throw std::runtime_error("unsupported fatal-entry fixture table shape");
        for (size_t player = 0; player < 2; ++player)
            if (pending[player] > 7 || alive[player] != 0)
                throw std::runtime_error("unsupported fatal-entry player gates");
        std::array<bool, 33> seen{};
        for (size_t slot = 1; slot <= storage.count; ++slot) {
            const auto& raw = storage.actors[slot];
            const bool generic = raw[0] >= 1 && raw[0] <= 8 && (raw[21] == 3 || raw[21] == 4);
            if ((slot == target ? !generic : raw[0] != 0x0b || raw[21] != 5) ||
                raw[1] < 2 || raw[1] >= storage.visualCount || seen[raw[1]] || (generic && raw[37] >= 9))
                throw std::runtime_error("unsupported fatal-entry fixture actor");
            seen[raw[1]] = true;
            for (const size_t at : {size_t{22}, size_t{29}})
                if (!raw[at] || !raw[at + 1] || !raw[at + 2] || raw[at] >= 92 || raw[at + 1] >= 92 || raw[at + 2] >= 92 ||
                    raw[at + 5] > 3 || (raw[at + 6] != 1 && raw[at + 6] != 255))
                    throw std::runtime_error("unsupported fatal-entry fixture animation");
        }
    }
};

inline gameplay::ActiveMonster decode(const gameplay::ActorSlots& slots, uint64_t order) {
    auto monster = corpse_storage::decode(slots, order);
    const auto& raw = slots.actor(order);
    const auto wordAt = [&](size_t at) { return static_cast<uint16_t>(raw[at] | (uint16_t(raw[at + 1]) << 8)); };
    monster.hp = raw[36] + 1;
    monster.ai0 = wordAt(14); monster.ai1 = wordAt(16); monster.ai2 = wordAt(18);
    monster.animationSetLeft = raw[3]; monster.animationSetRight = raw[4];
    monster.hasSpawner = raw[37] != 0;
    monster.spawnerIndex = monster.hasSpawner ? raw[37] - 1 : 0;
    monster.deathRewardPending = false;
    return monster;
}

inline void writeHeader(std::ostream& output, uint32_t operations) {
    output.write("LZFO0001", 8);
    transient_storage::write(output, operations, 4);
}

inline void writeState(std::ostream& output, const gameplay::ActorSlots::State& state, uint32_t rng,
        const std::array<uint8_t, 2>& pending, const std::array<uint8_t, 2>& hits, const std::array<uint8_t, 2>& alive,
        uint8_t roll, const sound::SoundEngine& sound, const gameplay::MonsterSpawnerStorage& spawners, int8_t damage) {
    corpse_storage::writeState(output, state, rng, pending, hits, alive, roll, sound);
    for (const auto& row : spawners.state())
        output.write(reinterpret_cast<const char*>(row.data()), row.size());
    output.put(static_cast<char>(damage));
}

} // namespace lezac::diagnostics::fatal_entry
