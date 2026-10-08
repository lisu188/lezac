#include "gameplay/actor_storage.hpp"

#include <cstdio>
#include <iostream>
#include <stdexcept>
#include <string>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

namespace {
uint8_t byte() {
    const int value = std::cin.get();
    if (value == std::char_traits<char>::eof()) throw std::runtime_error("truncated actor storage request");
    return static_cast<uint8_t>(value);
}

uint16_t word() {
    const uint16_t low = byte();
    return static_cast<uint16_t>(low | (static_cast<uint16_t>(byte()) << 8));
}

int16_t signedWord() {
    const uint16_t value = word();
    return static_cast<int16_t>(value >= 0x8000 ? static_cast<int>(value) - 0x10000 : value);
}

void put(uint8_t value) { std::cout.put(static_cast<char>(value)); }
void putWord(uint16_t value) { put(static_cast<uint8_t>(value)); put(static_cast<uint8_t>(value >> 8)); }

using Storage = lezac::gameplay::ActorStorage;

Storage::State readState() {
    Storage::State state;
    for (auto& row : state.actors) for (auto& value : row) value = byte();
    for (auto& row : state.visuals) for (auto& value : row) value = byte();
    for (auto& row : state.links) for (auto& value : row) value = byte();
    state.count = byte();
    state.visualCount = byte();
    if (byte() != state.links[0][15]) throw std::runtime_error("inconsistent boss-link count");
    state.success = word();
    return state;
}

void writeState(const Storage::State& state) {
    for (const auto& row : state.actors) for (auto value : row) put(value);
    for (const auto& row : state.visuals) for (auto value : row) put(value);
    for (const auto& row : state.links) for (auto value : row) put(value);
    put(state.count);
    put(state.visualCount);
    put(state.links[0][15]);
    putWord(state.success);
}

void apiContract() {
    Storage storage;
    storage.resetForLevel({2, 14, 0x34, 0x12});
    storage.actor(0)[5] = 0xa5;
    storage.visual(1)[0] = 0x5a;
    const auto before = storage.state();
    int rejected = 0;
    auto rejects = [&](auto action) {
        bool threw = false;
        try { action(); } catch (const std::exception&) { threw = true; }
        if (!threw) throw std::runtime_error("invalid storage access was accepted");
        ++rejected;
    };
    rejects([&] { storage.actor(1); });
    rejects([&] { storage.visual(2); });
    rejects([&] { storage.retire(0); });
    auto invalid = before;
    invalid.count = 31;
    rejects([&] { storage.restore(invalid); });
    invalid = before;
    invalid.visualCount = 3;
    rejects([&] { storage.restore(invalid); });
    invalid = before;
    invalid.links[0][15] = 8;
    rejects([&] { storage.restore(invalid); });
    invalid = before;
    invalid.actors[0][1] = 2;
    rejects([&] { storage.restore(invalid); });
    const auto& after = storage.state();
    if (after.actors != before.actors || after.visuals != before.visuals || after.links != before.links ||
        after.count != before.count || after.visualCount != before.visualCount || after.success != before.success) {
        throw std::runtime_error("rejected storage access mutated state");
    }
    const size_t slot = storage.append({12, 100, 2, 31, -32768, 2048, -1, -2}, {2, 14, 0x34, 0x12});
    const auto tail = storage.actor(slot);
    if (slot != 1 || !storage.retire(slot) || storage.retire(slot) ||
        storage.state().actors[1] != tail || storage.actor(0)[5] != 0xa5 || storage.visual(1)[0] != 0x5a) {
        throw std::runtime_error("mutable storage writeback or retired tail changed");
    }
    std::cout << "actor_storage_api=ok rejected=" << rejected
              << " mutable_writebacks=2 stable_tail=1 compiled_core=1 production_app=0\n";
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--api-contract") {
            apiContract();
            return 0;
        }
        if (argc != 1) throw std::runtime_error("unexpected actor storage probe arguments");
#ifdef _WIN32
        if (_setmode(_fileno(stdin), _O_BINARY) == -1 || _setmode(_fileno(stdout), _O_BINARY) == -1) {
            throw std::runtime_error("cannot select binary actor storage pipes");
        }
#endif
        std::string magic;
        for (int i = 0; i < 8; ++i) magic.push_back(static_cast<char>(byte()));
        if (magic != "LZAS0001") throw std::runtime_error("invalid actor storage protocol");
        const uint32_t low = word();
        const uint32_t count = low | (static_cast<uint32_t>(word()) << 16);
        if (!count || count > 20000) throw std::runtime_error("invalid actor storage operation count");
        std::array<Storage::Descriptor, 92> descriptors;
        for (auto& row : descriptors) for (auto& value : row) value = byte();
        std::cout << "LZAR0001";
        putWord(static_cast<uint16_t>(count));
        putWord(static_cast<uint16_t>(count >> 16));
        Storage storage;
        uint32_t operations = 0, commands = 0;
        bool seeded = false;
        while (std::cin.peek() != std::char_traits<char>::eof()) {
            if (++commands > 40000) throw std::runtime_error("too many actor storage commands");
            const auto operation = byte();
            if (operation == 'S') {
                storage.restore(readState());
                seeded = true;
                continue;
            }
            if (!seeded || operations == count) throw std::runtime_error("unexpected actor storage operation");
            if (operation == 'C') {
                const uint16_t behavior = word(), timer = word(), kind = word(), sprite = word();
                const int16_t vy = signedWord(), vx = signedWord(), y = signedWord(), x = signedWord();
                if (behavior > 255 || timer > 255 || kind > 255 || sprite >= descriptors.size()) {
                    throw std::runtime_error("invalid actor construction input");
                }
                storage.append({static_cast<uint8_t>(kind), static_cast<uint8_t>(timer),
                    static_cast<uint8_t>(behavior), sprite, vx, vy, x, y}, descriptors[sprite]);
            } else if (operation == 'R') {
                storage.retire(word());
            } else if (operation == 'L') {
                storage.resetForLevel(descriptors[1]);
            } else {
                throw std::runtime_error("unknown actor storage operation");
            }
            writeState(storage.state());
            ++operations;
        }
        std::cout.flush();
        if (operations != count || !std::cout) throw std::runtime_error("incomplete actor storage comparison");
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
