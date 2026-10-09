#include "gameplay/damage_lane_memory.hpp"
#include "gameplay/initial_damage_data.hpp"

#include <algorithm>
#include <array>
#include <iostream>
#include <stdexcept>
#include <string>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

namespace {
using namespace lezac::gameplay;

struct Cursor {
    uint16_t value = 0;
    uint16_t requestCursor() const { return value; }
    void writeSharedCursor(uint16_t next) { value = next; }
};

struct State {
    std::array<uint8_t, 65536> bytes{};
    RetainedRecordQueue<DebrisRecord> debris;
    RetainedRecordQueue<CollapseRecord> collapse;
    RetainedRecordQueue<FlameRecord> flames;
    Cursor sound;
    uint8_t seeded = 0;
    DamageLaneMemory<Cursor> memory{bytes, debris, collapse, flames, sound, seeded};
};

void require(bool condition) {
    if (!condition) throw std::runtime_error("shared damage memory unit check failed");
}

void take(uint8_t* bytes, size_t count) {
    if (!std::cin.read(reinterpret_cast<char*>(bytes), static_cast<std::streamsize>(count)))
        throw std::runtime_error("truncated shared damage stream");
}

uint32_t word32(const std::array<uint8_t, 16>& header, size_t at) {
    return static_cast<uint32_t>(header[at]) | (static_cast<uint32_t>(header[at + 1]) << 8) |
        (static_cast<uint32_t>(header[at + 2]) << 16) | (static_cast<uint32_t>(header[at + 3]) << 24);
}

void stream() {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    std::array<uint8_t, 16> header{};
    take(header.data(), header.size());
    const auto count = word32(header, 8);
    if (std::string(header.begin(), header.begin() + 8) != "LZLI0001" ||
        word32(header, 12) != 65540 || count == 0 || count > 4096)
        throw std::runtime_error("invalid shared damage header");
    auto output = header;
    const std::string magic = "LZLO0001";
    std::copy(magic.begin(), magic.end(), output.begin());
    output[12] = 0; output[13] = 0; output[14] = 1; output[15] = 0;
    std::cout.write(reinterpret_cast<const char*>(output.data()), output.size());
    for (uint32_t index = 0; index < count; ++index) {
        State state;
        std::array<uint8_t, 4> parameters{};
        std::array<uint8_t, 65536> incoming{};
        take(parameters.data(), parameters.size());
        take(incoming.data(), incoming.size());
        for (size_t address = 0; address < incoming.size(); ++address)
            state.memory.write(static_cast<uint16_t>(address), incoming[address]);
        // Input round-trip validates every forwarded field before executing.
        for (size_t address = 0; address < incoming.size(); ++address)
            require(state.memory.read(static_cast<uint16_t>(address)) == incoming[address]);
        if (parameters[0] > 3) throw std::runtime_error("invalid shared damage operation");
        if (parameters[0] < 2) lookupDamageLaneBytes(state.memory, parameters[0] != 0);
        else {
            const auto caller = static_cast<uint16_t>(parameters[2] | (parameters[3] << 8));
            blendDamageLaneBytes(state.memory, caller, parameters[1], (parameters[0] & 1) != 0,
                [](uint16_t) -> DamageLaneSeed { throw std::runtime_error("flagged fixture seeded"); });
        }
        for (size_t address = 0; address < incoming.size(); ++address)
            incoming[address] = state.memory.read(static_cast<uint16_t>(address));
        std::cout.write(reinterpret_cast<const char*>(incoming.data()), incoming.size());
    }
    if (std::cin.peek() != std::char_traits<char>::eof() || !std::cout)
        throw std::runtime_error("invalid shared damage stream end");
}

void unit() {
    State state;
    auto& memory = state.memory;
    const auto initial = initialDamageLaneData();
    require(initial[0xa06] == 0 && initial[0xa07] == 0 && initial[2] == 0x32);
    for (size_t address = 0x209e; address < 0x6569; ++address) {
        memory.write(static_cast<uint16_t>(address), static_cast<uint8_t>(address * 37));
        require(memory.read(static_cast<uint16_t>(address)) == static_cast<uint8_t>(address * 37));
    }
    for (size_t address = 0x6620; address < 0x74d5; ++address) {
        memory.write(static_cast<uint16_t>(address), static_cast<uint8_t>(address * 13));
        require(memory.read(static_cast<uint16_t>(address)) == static_cast<uint8_t>(address * 13));
    }
    require(state.debris.retainedSize() == 1402 && state.collapse.retainedSize() == 251);
    const auto pattern = [](size_t address, size_t multiplier) { return static_cast<uint8_t>(address * multiplier); };
    const auto patternedWord = [&](size_t address, size_t multiplier) {
        return static_cast<uint16_t>(pattern(address, multiplier) |
            (static_cast<uint16_t>(pattern(address + 1, multiplier)) << 8));
    };
    for (size_t index : {size_t{0}, size_t{1}, size_t{1400}, size_t{1401}}) {
        const auto& record = state.debris.retainedSlot(index);
        const size_t address = 0x292b + 11 * index;
        require(record.tileIndex == patternedWord(address, 37));
        require(record.flaggedWord == patternedWord(address + 2, 37));
        require(static_cast<uint8_t>(record.velocityX) == pattern(address + 4, 37));
        require(static_cast<uint8_t>(record.velocityY) == pattern(address + 5, 37));
        require(static_cast<uint8_t>(record.subX) == pattern(address + 6, 37));
        require(static_cast<uint8_t>(record.subY) == pattern(address + 7, 37));
        require(record.restTicks == pattern(address + 8, 37));
        require(record.lookup == pattern(address + 9, 37) && record.aux == pattern(address + 10, 37));
    }
    for (size_t index : {size_t{0}, size_t{1}, size_t{249}, size_t{250}}) {
        const auto& record = state.collapse.retainedSlot(index);
        const size_t address = 0x6620 + 15 * index;
        require(record.startOffsetBytes == patternedWord(address, 13));
        require(record.endOffsetBytes == patternedWord(address + 2, 13));
        require(record.flaggedWord == patternedWord(address + 4, 13));
        require(record.word == (record.flaggedWord & 0x7fff));
        require(record.forwardPhase == pattern(address + 6, 13) && record.reversePhase == pattern(address + 7, 13));
        require(static_cast<uint8_t>(record.subX) == pattern(address + 8, 13));
        require(static_cast<uint8_t>(record.subY) == pattern(address + 9, 13));
        require(record.argMagnitude == patternedWord(address + 10, 13));
        require(record.flags == pattern(address + 12, 13) && record.restTicks == pattern(address + 13, 13));
        require(record.affectedBytes == pattern(address + 14, 13));
    }
    for (size_t index : {size_t{0}, size_t{1}, size_t{197}, size_t{198}}) {
        const auto& record = state.flames.retainedSlot(index);
        const size_t address = 0x209e + 11 * index;
        require(record.cell == patternedWord(address, 37) && record.retainedWord == patternedWord(address + 2, 37));
        require(static_cast<uint8_t>(record.vx) == pattern(address + 4, 37));
        require(static_cast<uint8_t>(record.vy) == pattern(address + 5, 37));
        require(static_cast<uint8_t>(record.subX) == pattern(address + 6, 37));
        require(static_cast<uint8_t>(record.subY) == pattern(address + 7, 37));
        require(record.timer == pattern(address + 8, 37));
        require(record.glyph == pattern(address + 9, 37) && record.variant == pattern(address + 10, 37));
    }
    writeDamageLaneWord(memory, 0x2074, 0xab12);
    require(state.sound.value == 0xab12);
    state.sound.value = 0x1234;
    require(damageLaneWord(memory, 0x2074) == 0x1234);
    state.debris.clear(); state.collapse.clear();
    state.debris.push_back(DebrisRecord{});
    writeDamageLaneWord(memory, 0x2078, 1);
    writeDamageLaneWord(memory, 0x655e, 0xf001);
    memory.write(0x661e, 100);
    memory.write(0xf100, 207);
    auto noSeed = [](uint16_t) -> DamageLaneSeed { throw std::runtime_error("unexpected seed"); };
    blendDamageLaneBytes(memory, 0xf100, 1, true, noSeed);
    require(damageLaneWord(memory, 0x2074) == 0x3e21 && memory.read(0xa07) == 25);
    // The next missing collapse uses 0A07 as its unsigned weight byte.
    writeDamageLaneWord(memory, 0x655e, 0xb598);
    require(state.debris.retainedSlot(1401).tileIndex == 0xb598);
    memory.write(0xf100, 207);
    blendDamageLaneBytes(memory, 0xf100, 1, false, noSeed);
    require(memory.read(0xf100) == 94 && memory.read(0xa07) == 25);
    int vx = -1, subX = 2, vy = -3, subY = 4;
    {
        DamageLaneMemory bound(state.bytes, state.debris, state.collapse, state.flames,
            state.sound, state.seeded, std::array<int*, 4>{&vx, &subX, &vy, &subY});
        bound.write(0x78d4, 100);
        require(vy == 100);
        vx = -100;
        require(bound.read(0x78d2) == 156);
    }
    require(memory.read(0x78d2) == 156 && memory.read(0x78d4) == 100);
    const auto stale = state.debris.retainedSlot(1401).tileIndex;
    state.debris.clear();
    require(state.debris.retainedSlot(1401).tileIndex == stale);
    state.flames.push_back(FlameRecord{}); state.flames.push_back(FlameRecord{});
    state.flames[0].cell = 1; state.flames[1].cell = 2;
    require(state.flames.rbegin()->cell == 2 && state.flames.rbegin() + 2 == state.flames.rend());
    state.flames.setLiveSize(1);
    require(state.flames.size() == 1 && state.flames.retainedSlot(1).cell == 2);
    writeDamageLaneWord(memory, 0x2078, 0);
    const auto phase = blendDamageLaneValue(memory, 207, 1, false, noSeed);
    require(phase && *phase == 207);
    writeDamageLaneWord(memory, 0x2078, 1);
    writeDamageLaneWord(memory, 0x655e, 1);
    const auto failed = blendDamageLaneValue(memory, 207, 1, false,
        [](uint16_t) { return DamageLaneSeed::Failed; });
    require(!failed);
    std::cout << "damage_lane_memory_unit=ok typed_banks=3 shared_cursor=1 low_data_history=1 caller_alias=1 stack_value=1\n";
}
}

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--stream") stream();
        else if (argc == 1) unit();
        else throw std::runtime_error("invalid shared damage arguments");
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
