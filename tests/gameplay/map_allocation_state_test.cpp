#include "gameplay/map_plane_memory.hpp"

#include <iostream>
#include <vector>

int main() {
    lezac::gameplay::MapPlaneMemory memory;
    if (memory.hasLevelAllocation()) return 1;
    std::vector<uint8_t> tiles;
    std::vector<uint16_t> words;
    memory.beginLevel(tiles, words, 1980);
    if (!memory.hasLevelAllocation()) return 2;
    memory.beginLevel(tiles, words, 5300);
    if (!memory.hasLevelAllocation()) return 3;
    memory.restoreSeparatedPlanesForFixture();
    if (memory.hasLevelAllocation()) return 4;
    std::cout << "map_allocation_state=ok initial_unallocated=1 play_allocated=1 fixture_separated=1\n";
    return 0;
}
