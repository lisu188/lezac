#include "gameplay/collapse_seed.hpp"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

#if defined(LEZAC_FOUR_NEIGHBOR_MUTANT) || defined(LEZAC_EIGHT_NEIGHBOR_MUTANT)
static lezac::gameplay::CollapseSeedGeometry floodMutant(std::vector<uint16_t>& words,
                                                        int width, size_t seed) {
    lezac::gameplay::CollapseSeedGeometry result;
    const uint16_t key = words[seed];
    std::vector<size_t> pending{seed};
    int minX = width, minY = static_cast<int>(words.size() / width), maxX = 0, maxY = 0;
    while (!pending.empty()) {
        const size_t cell = pending.back();
        pending.pop_back();
        if (words[cell] != key) continue;
        words[cell] = static_cast<uint16_t>(key | 0x8000);
        result.cells.push_back(cell);
        const int x = static_cast<int>(cell % width), y = static_cast<int>(cell / width);
        minX = std::min(minX, x); minY = std::min(minY, y);
        maxX = std::max(maxX, x); maxY = std::max(maxY, y);
        for (int dy = -1; dy <= 1; ++dy) {
            for (int dx = -1; dx <= 1; ++dx) {
                if (dx == 0 && dy == 0) continue;
#if defined(LEZAC_FOUR_NEIGHBOR_MUTANT)
                if (dx != 0 && dy != 0) continue;
#endif
                const int nx = x + dx, ny = y + dy;
                if (nx >= 0 && nx < width && ny >= 0 && static_cast<size_t>(ny * width + nx) < words.size()) {
                    pending.push_back(static_cast<size_t>(ny * width + nx));
                }
            }
        }
    }
    result.firstOffsetBytes = static_cast<uint16_t>(2 * (minY * width + minX));
    result.lastOffsetBytes = static_cast<uint16_t>(2 * (maxY * width + maxX));
    return result;
}
#endif

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("expected input and output paths");
        std::ifstream input(argv[1], std::ios::binary);
        std::ofstream output(argv[2], std::ios::binary);
        if (!input || !output) throw std::runtime_error("cannot open geometry probe files");
        auto readByte = [&]() -> uint8_t {
            const int value = input.get();
            if (value == std::char_traits<char>::eof()) throw std::runtime_error("truncated geometry input");
            return static_cast<uint8_t>(value);
        };
        auto readWord = [&]() -> uint16_t {
            const uint16_t low = readByte();
            return static_cast<uint16_t>(low | (static_cast<uint16_t>(readByte()) << 8));
        };
        auto writeByte = [&](uint8_t value) { output.put(static_cast<char>(value)); };
        auto writeWord = [&](uint16_t value) {
            writeByte(static_cast<uint8_t>(value));
            writeByte(static_cast<uint8_t>(value >> 8));
        };
        std::string magic;
        for (int i = 0; i < 8; ++i) magic.push_back(static_cast<char>(readByte()));
        if (magic != "LZSG0001") throw std::runtime_error("invalid geometry probe header");
        const uint32_t low = readWord();
        const uint32_t count = low | (static_cast<uint32_t>(readWord()) << 16);
        if (count == 0 || count > 10000) throw std::runtime_error("invalid geometry case count");
        for (uint32_t test = 0; test < count; ++test) {
            const int width = readWord();
            const size_t cells = readWord();
            const size_t seed = readWord();
            if (width == 0 || width > 300 || cells == 0 || cells > 32768 || seed >= cells) {
                throw std::runtime_error("invalid geometry dimensions");
            }
            std::vector<uint16_t> words(cells);
            for (auto& word : words) word = readWord();
#if defined(LEZAC_FOUR_NEIGHBOR_MUTANT) || defined(LEZAC_EIGHT_NEIGHBOR_MUTANT)
            const auto geometry = floodMutant(words, width, seed);
#else
            const auto geometry = lezac::gameplay::seedCollapseWordGroup(words, width, seed);
#endif
            writeWord(geometry.firstOffsetBytes);
            writeWord(geometry.lastOffsetBytes);
            writeWord(static_cast<uint16_t>(geometry.cells.size()));
            writeByte(static_cast<uint8_t>(2 * geometry.cells.size()));
            for (auto word : words) writeWord(word);
        }
        output.flush();
        if (input.peek() != std::char_traits<char>::eof() || !output) throw std::runtime_error("geometry I/O differs");
        std::cout << "collapse_seed_probe=ok cases=" << count << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
