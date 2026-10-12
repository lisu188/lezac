#include "diagnostics/transient_storage_fixture.hpp"
#include "gameplay/monster_damage.hpp"
#include "gameplay/monster_spawners.hpp"

#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace fixture = lezac::diagnostics::transient_storage;
using Bytes = std::array<uint8_t, 1864>;

Bytes readState(std::istream& input) {
    Bytes result{};
    input.read(reinterpret_cast<char*>(result.data()), result.size());
    if (!input) throw std::runtime_error("truncated fatal partial state");
    return result;
}

uint32_t header(std::istream& input, const std::string& expected) {
    std::string magic(8, '\0');
    input.read(magic.data(), 8);
    if (magic != expected) throw std::runtime_error("invalid fatal probe magic");
    const uint32_t low = fixture::word(input);
    const uint32_t count = low | (static_cast<uint32_t>(fixture::word(input)) << 16);
    if (!count || count > 4096) throw std::runtime_error("invalid fatal probe count");
    return count;
}

Bytes snapshot(const Bytes& unchanged, const lezac::gameplay::ActorSlots& slots,
               const lezac::gameplay::MonsterSpawnerStorage& spawners) {
    Bytes result = unchanged;
    std::ostringstream stream(std::ios::binary);
    fixture::writeState(stream, slots.state());
    const std::string actorState = stream.str();
    if (actorState.size() != 1575) throw std::runtime_error("fatal storage shape changed");
    std::copy(actorState.begin(), actorState.end(), result.begin());
    size_t offset = 1593;
    for (const auto& row : spawners.state()) for (uint8_t value : row) result[offset++] = value;
    return result;
}

void compare(const Bytes& actual, const Bytes& expected, uint32_t index, const char* phase) {
    for (size_t byte = 0; byte < actual.size(); ++byte) {
        if (actual[byte] != expected[byte]) {
            throw std::runtime_error(std::string(phase) + " case=" + std::to_string(index) +
                " byte=" + std::to_string(byte) + " actual=" + std::to_string(actual[byte]) +
                " expected=" + std::to_string(expected[byte]));
        }
    }
}

void partials(const std::string& path) {
    std::ifstream input(path, std::ios::binary);
    const uint32_t count = header(input, "LZFP0001");
    size_t fatal = 0;
    for (uint32_t index = 0; index < count; ++index) {
        const uint8_t target = fixture::byte(input), expectedFatal = fixture::byte(input);
        lezac::gameplay::ActorSlots::Descriptor descriptor{};
        for (auto& byte : descriptor) byte = fixture::byte(input);
        const Bytes before = readState(input), impact = readState(input), after = readState(input);
        std::istringstream state(std::string(reinterpret_cast<const char*>(before.data()), 1575), std::ios::binary);
        const auto storage = fixture::readSeed(state);
        if (target == 0 || target > storage.count || expectedFatal > 1) throw std::runtime_error("invalid fatal target");
        lezac::gameplay::ActorSlots slots;
        std::array<uint64_t, lezac::gameplay::ActorStorage::capacity + 1> orders{};
        for (size_t slot = 1; slot <= storage.count; ++slot) orders[slot] = slot;
        slots.restoreForFixture(storage, orders);
        lezac::gameplay::MonsterSpawnerStorage spawners;
        lezac::gameplay::MonsterSpawnerStorage::State spawnerState{};
        size_t offset = 1593;
        for (auto& row : spawnerState) for (auto& value : row) value = before[offset++];
        spawners.restoreForFixture(spawnerState);
        slots.applyMonsterImpact(target, descriptor);
        compare(snapshot(before, slots, spawners), impact, index, "impact");
        const bool died = slots.applyMonsterDamage(target, static_cast<int8_t>(before.back()));
        if (died != (expectedFatal != 0)) throw std::runtime_error("fatal branch differs");
        if (died) { spawners.release(slots.actor(target)[37]); ++fatal; }
        compare(snapshot(before, slots, spawners), after, index, "damage");
    }
    if (input.peek() != std::char_traits<char>::eof()) throw std::runtime_error("trailing fatal partial data");
    if (count != 960 || fatal != 768) throw std::runtime_error("fatal partial coverage changed");
    std::cout << "fatal_storage_partial_probe=ok impacts=960 fatal=768 nonfatal=192 compared_bytes=3578880 masks=0 full_app=0\n";
}

void scratch(const std::string& path) {
    std::ifstream input(path, std::ios::binary);
    const uint32_t count = header(input, "LZMQ0001");
    std::array<uint8_t, 1980> terrain{};
    for (auto& value : terrain) value = fixture::byte(input);
    for (uint32_t index = 0; index < count; ++index) {
        const int x = static_cast<int16_t>(fixture::word(input)), y = static_cast<int16_t>(fixture::word(input));
        const uint8_t patch = fixture::byte(input);
        const uint16_t expectedResult = fixture::word(input), expectedCursor = fixture::word(input);
        const int8_t expectedDelta = static_cast<int8_t>(fixture::byte(input));
        const auto damage = lezac::gameplay::queryMonsterTileDamage((x + 4) >> 3, y >> 3, 60,
            [&](int column, int row) -> uint8_t {
                if (column < 0 || column >= 60 || row < 0 || row >= 33) return 0;
                if ((column == 42 || column == 43) && (row == 12 || row == 13)) return patch;
                return terrain[static_cast<size_t>(row * 60 + column)];
            });
        lezac::gameplay::ActorSlots slots;
        slots.setSharedResult(damage.lastFlameCell);
        if (slots.state().success != expectedResult || damage.footprintCell != expectedCursor || damage.delta != expectedDelta)
            throw std::runtime_error("damage scratch differs case=" + std::to_string(index));
    }
    if (input.peek() != std::char_traits<char>::eof()) throw std::runtime_error("trailing damage scratch data");
    if (count != 1536) throw std::runtime_error("damage scratch coverage changed");
    std::cout << "monster_damage_scratch_probe=ok queries=1536 ds2072=1 ds2074=1 ds661e=1 full_app=0\n";
}

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("expected partial and scratch fixture paths");
        partials(argv[1]);
        scratch(argv[2]);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "fatal_storage_probe=failed " << error.what() << '\n';
        return 1;
    }
}
