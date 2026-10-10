#include "gameplay/collapse_seed.hpp"
#include "gameplay/map_plane_memory.hpp"

#include <iostream>
#include <stdexcept>
#include <vector>

static void require(bool condition) {
    if (!condition) throw std::runtime_error("physical collapse seed differs");
}

int main() {
    try {
        for (bool shared : {false, true}) {
            lezac::gameplay::MapPlaneMemory memory;
            if (shared) memory.beginLevel({}, {}, 1980);
            std::vector<uint8_t> tiles(1980);
            std::vector<uint16_t> words(1980);
            auto read = [&](uint16_t cell) {
                require(cell < 32768);
                return memory.readWord(cell, tiles, words);
            };
            auto write = [&](uint16_t cell, uint16_t word) {
                require(cell < 32768);
                memory.writeWord(cell, word, tiles, words);
            };
            for (uint16_t seed : {uint16_t{2013}, uint16_t{32748}}) {
                write(seed, 0x12);
                const auto result = lezac::gameplay::seedCollapseWordGroupPhysical(60, seed, read, write);
                require(result.cells == std::vector<size_t>{seed});
                require(result.firstOffsetBytes == static_cast<uint16_t>(2u * seed));
                require(result.lastOffsetBytes == result.firstOffsetBytes && read(seed) == 0x8012);
                require(lezac::gameplay::seedCollapseWordGroupPhysical(60, seed, read, write).cells.empty());
                write(seed, 0);
            }
            write(32748, 0x12);
            const auto wrapped = lezac::gameplay::seedCollapseWordGroupPhysical(60, 65516, read, write);
            require(wrapped.cells == std::vector<size_t>{32748});
            write(32748, 0);
            write(1979, 0x12);
            write(1980, 0x12);
            const auto crossing = lezac::gameplay::seedCollapseWordGroupPhysical(60, 1979, read, write);
            require(crossing.cells == std::vector<size_t>({1979, 1980}));
            require(read(1979) == 0x8012 && read(1980) == 0x8012);
            require(lezac::gameplay::seedCollapseWordGroupPhysical(0, 2013, read, write).cells.empty());
        }
        std::vector<uint16_t> logical(1980);
        require(lezac::gameplay::seedCollapseWordGroup(logical, 60, 2013).cells.empty());
        std::cout << "physical_collapse_seed=ok layouts=2 wrapped=1 crossing=1 logical_adapter=1\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
