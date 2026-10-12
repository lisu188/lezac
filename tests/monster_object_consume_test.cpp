#include "gameplay/monster_damage.hpp"

#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("expected original fixture path");
        std::ifstream input(argv[1], std::ios::binary);
        if (!input) throw std::runtime_error("cannot open consumption fixture");
        const std::vector<uint8_t> raw{std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
        uint64_t hash = UINT64_C(14695981039346656037);
        for (uint8_t value : raw) hash = (hash ^ value) * UINT64_C(1099511628211);
        if (raw.size() != 115212 || hash != UINT64_C(0xd1cd7f6df842b8a9) ||
            std::string(raw.begin(), raw.begin() + 8) != "LZOC0001" ||
            raw[8] != 0 || raw[9] != 25 || raw[10] != 0 || raw[11] != 0)
            throw std::runtime_error("consumption fixture identity differs");
        const auto word = [&](size_t at) { return static_cast<uint16_t>(raw.at(at) | (uint16_t(raw.at(at + 1)) << 8)); };
        for (size_t index = 0; index < 6400; ++index) {
            const size_t at = 12 + index * 18;
            const auto result = lezac::gameplay::queryMonsterObjectConsumption(raw[at], word(at + 1), word(at + 3));
            const auto cursor = static_cast<uint16_t>(word(at + 5) + result.score);
            if (result.glyph != raw[at + 7] || result.word != word(at + 8) || word(at + 3) != word(at + 10) ||
                result.scratch != raw[at + 12] || result.sprite != word(at + 13) || cursor != word(at + 15) ||
                result.seedAbove != (raw[at + 17] != 0) || result.consumed != (raw[at] >= 0x67 && raw[at] <= 0x72))
                throw std::runtime_error("original consumption differs at case " + std::to_string(index));
        }
        std::cout << "monster_object_consume_original=ok cases=6400 glyphs=256 word_boundaries=5 above_boundaries=5 cursor_wrap=1\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
