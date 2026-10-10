#pragma once

#include "gameplay/falling_fragment.hpp"
#include <cstdio>
#include <istream>
#include <ostream>
#include <stdexcept>
#include <string>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

namespace lezac::diagnostics {

struct JollyCloudProbeState {
    resources::Level level;
    std::vector<gameplay::DebrisRecord> records;
    uint8_t remaining = 0;
    uint16_t nextWord = 0;
    uint32_t seed = 0;
};

inline uint32_t readRainNumber(std::istream& input, unsigned bytes) {
    uint32_t value = 0;
    for (unsigned i = 0; i < bytes; ++i) {
        const int byte = input.get();
        if (byte == std::char_traits<char>::eof()) throw std::runtime_error("truncated rain request");
        value |= static_cast<uint32_t>(static_cast<uint8_t>(byte)) << (8 * i);
    }
    return value;
}

inline void writeRainNumber(std::ostream& output, uint32_t value, unsigned bytes) {
    for (unsigned i = 0; i < bytes; ++i) output.put(static_cast<char>(value >> (8 * i)));
}

template <typename Advance>
void runJollyCloudProbe(std::istream& input, std::ostream& output, Advance advance) {
#ifdef _WIN32
    if (_setmode(_fileno(stdin), _O_BINARY) == -1 || _setmode(_fileno(stdout), _O_BINARY) == -1)
        throw std::runtime_error("cannot select binary rain pipes");
#endif
    std::string magic(8, '\0');
    if (!input.read(magic.data(), 8) || magic != "LZJC0001") throw std::runtime_error("invalid rain header");
    const auto cases = readRainNumber(input, 2);
    if (cases == 0 || cases > 64) throw std::runtime_error("invalid rain case count");
    output.write("LZJO0001", 8);
    writeRainNumber(output, cases, 2);
    for (uint32_t index = 0; index < cases; ++index) {
        JollyCloudProbeState state;
        state.level.width = static_cast<int>(readRainNumber(input, 2));
        state.level.height = 4;
        state.remaining = static_cast<uint8_t>(readRainNumber(input, 1));
        state.level.objectiveTile = static_cast<uint8_t>(readRainNumber(input, 1));
        state.nextWord = static_cast<uint16_t>(readRainNumber(input, 2));
        const auto count = readRainNumber(input, 2);
        state.seed = readRainNumber(input, 4);
        if (state.level.width < 1 || state.level.width > 256 || count > 1401)
            throw std::runtime_error("invalid rain dimensions or debris count");
        const size_t cells = static_cast<size_t>(state.level.width) * 4;
        for (size_t cell = 0; cell < cells; ++cell) state.level.tiles.push_back(static_cast<uint8_t>(readRainNumber(input, 1)));
        for (size_t cell = 0; cell < cells; ++cell) state.level.wordLayer.push_back(static_cast<uint16_t>(readRainNumber(input, 2)));
        for (uint32_t slot = 0; slot < count; ++slot) {
            gameplay::DebrisRecord record;
            record.tileIndex = static_cast<int>(readRainNumber(input, 2));
            record.flaggedWord = static_cast<uint16_t>(readRainNumber(input, 2));
            record.velocityX = static_cast<int8_t>(readRainNumber(input, 1));
            record.velocityY = static_cast<int8_t>(readRainNumber(input, 1));
            record.subX = static_cast<int8_t>(readRainNumber(input, 1));
            record.subY = static_cast<int8_t>(readRainNumber(input, 1));
            record.restTicks = static_cast<uint8_t>(readRainNumber(input, 1));
            record.lookup = static_cast<uint8_t>(readRainNumber(input, 1));
            record.aux = static_cast<uint8_t>(readRainNumber(input, 1));
            state.records.push_back(record);
        }
        const unsigned steps = state.remaining + 2;
        advance(state, true);
        writeRainNumber(output, steps, 2);
        for (unsigned step = 0; step < steps; ++step) {
            advance(state, false);
            writeRainNumber(output, state.remaining, 1);
            writeRainNumber(output, state.seed, 4);
            writeRainNumber(output, state.nextWord, 2);
            writeRainNumber(output, static_cast<uint32_t>(state.records.size()), 2);
            for (auto byte : state.level.tiles) writeRainNumber(output, byte, 1);
            for (auto word : state.level.wordLayer) writeRainNumber(output, word, 2);
            for (const auto& record : state.records) {
                writeRainNumber(output, static_cast<uint16_t>(record.tileIndex), 2);
                writeRainNumber(output, record.flaggedWord, 2);
                for (auto byte : {static_cast<uint8_t>(record.velocityX), static_cast<uint8_t>(record.velocityY),
                                  static_cast<uint8_t>(record.subX), static_cast<uint8_t>(record.subY),
                                  record.restTicks, record.lookup, record.aux}) writeRainNumber(output, byte, 1);
            }
        }
    }
    if (input.peek() != std::char_traits<char>::eof()) throw std::runtime_error("trailing rain request bytes");
    if (!output) throw std::runtime_error("cannot write rain response");
}

}
