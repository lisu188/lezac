#include "gameplay/damage_lane_bytes.hpp"

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
struct Memory {
    std::array<uint8_t, 65536> bytes{};
    uint8_t read(uint16_t address) const { return bytes[address]; }
    void write(uint16_t address, uint8_t value) { bytes[address] = value; }
};

void require(bool condition) {
    if (!condition) throw std::runtime_error("damage lane unit check failed");
}

void take(char* bytes, size_t count) {
    if (!std::cin.read(bytes, static_cast<std::streamsize>(count)))
        throw std::runtime_error("truncated damage lane stream");
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
    take(reinterpret_cast<char*>(header.data()), header.size());
    if (std::string(header.begin(), header.begin() + 8) != "LZLI0001" ||
        word32(header, 12) != 65540 || word32(header, 8) == 0 || word32(header, 8) > 4096)
        throw std::runtime_error("invalid damage lane stream header");
    auto output = header;
    const std::string magic = "LZLO0001";
    std::copy(magic.begin(), magic.end(), output.begin());
    output[12] = 0; output[13] = 0; output[14] = 1; output[15] = 0;
    std::cout.write(reinterpret_cast<const char*>(output.data()), output.size());
    for (uint32_t index = 0; index < word32(header, 8); ++index) {
        std::array<uint8_t, 4> parameters{};
        Memory memory;
        take(reinterpret_cast<char*>(parameters.data()), parameters.size());
        take(reinterpret_cast<char*>(memory.bytes.data()), memory.bytes.size());
        if (parameters[0] > 3) throw std::runtime_error("invalid damage lane operation");
        if (parameters[0] < 2) {
            lezac::gameplay::lookupDamageLaneBytes(memory, parameters[0] != 0);
        } else {
            const uint16_t caller = static_cast<uint16_t>(parameters[2] | (parameters[3] << 8));
            lezac::gameplay::blendDamageLaneBytes(memory, caller, parameters[1], (parameters[0] & 1) != 0,
                [](uint16_t) -> lezac::gameplay::DamageLaneSeed {
                    throw std::runtime_error("flagged fixture unexpectedly requested seeding");
                });
        }
        std::cout.write(reinterpret_cast<const char*>(memory.bytes.data()), memory.bytes.size());
    }
    if (std::cin.peek() != std::char_traits<char>::eof())
        throw std::runtime_error("trailing damage lane input");
    if (!std::cout) throw std::runtime_error("cannot write damage lane output");
}

void unit() {
    using namespace lezac::gameplay;
    Memory memory;
    writeDamageLaneWord(memory, 65535, 0x1234);
    require(damageLaneWord(memory, 65535) == 0x1234 && memory.read(0) == 0x12);
    require(damageLaneWriteAddress(0x3e21, false) == 0x0a06);
    require(damageLaneWriteAddress(0x3e21, true) == 0x0a07);
    for (bool reverse : {false, true}) {
        for (DamageLaneSeed seeded : {DamageLaneSeed::Failed, DamageLaneSeed::Collapse, DamageLaneSeed::Debris}) {
            Memory state;
            writeDamageLaneWord(state, 0x2078, 1);
            writeDamageLaneWord(state, 0x2074, 0xab12);
            writeDamageLaneWord(state, 0x655e, 1);
            writeDamageLaneWord(state, 0x659a, 244);
            state.write(0x661e, 100);
            state.write(0xf100, 207);
            unsigned calls = 0;
            blendDamageLaneBytes(state, 0xf100, 1, reverse, [&](uint16_t cell) {
                require(cell == 122);
                ++calls;
                writeDamageLaneWord(state, 0x207e, 200);
                writeDamageLaneWord(state, 0x2080, 1);
                state.write(0x662e, 2);
                return seeded;
            });
            require(calls == 1 && state.read(0x661e) == 100 && damageLaneWord(state, 0x2074) == 0xab12);
            const uint8_t expected = seeded == DamageLaneSeed::Failed ? 207 :
                seeded == DamageLaneSeed::Collapse ? 240 : 232;
            require(state.read(0xf100) == expected);
            if (seeded != DamageLaneSeed::Failed) {
                const uint16_t tag = damageLaneWord(state, 0x65d6);
                require(tag == (seeded == DamageLaneSeed::Collapse ? 1 : 20200));
                require(state.read(damageLaneWriteAddress(tag, reverse)) == expected);
            }
        }
    }
    Memory zero;
    bool rejected = false;
    try {
        blendDamageLaneBytes(zero, 0, 0, false, [](uint16_t) { return DamageLaneSeed::Failed; });
    } catch (const std::domain_error&) { rejected = true; }
    require(rejected);
    std::cout << "damage_lane_bytes_unit=ok wrap=1 seeder_branches=6 stale_seed_phase=1 division_by_zero=1\n";
}
}

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--stream") stream();
        else if (argc == 1) unit();
        else throw std::runtime_error("invalid damage lane test arguments");
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
