#include "gameplay/falling_fragment.hpp"
#include "gameplay/map_plane_memory.hpp"
#include "gameplay/retained_record_queue.hpp"
#include <iostream>
#include <stdexcept>
#include <type_traits>

namespace {
using Record = lezac::gameplay::DebrisRecord;
using Retained = lezac::gameplay::RetainedRecordQueue<Record>;

void require(bool condition) {
    if (!condition) throw std::runtime_error("physical falling fragment contract failed");
}

Record salt(size_t index) {
    Record record;
    record.tileIndex = static_cast<int>(index + 71);
    record.flaggedWord = static_cast<uint16_t>(index + 0x2345);
    record.velocityX = -3; record.velocityY = 7;
    record.subX = 9; record.subY = -11;
    record.restTicks = 23; record.lookup = 41; record.aux = 137;
    return record;
}

bool same(const Record& left, const Record& right) {
    return left.tileIndex == right.tileIndex && left.flaggedWord == right.flaggedWord &&
        left.velocityX == right.velocityX && left.velocityY == right.velocityY &&
        left.subX == right.subX && left.subY == right.subY && left.restTicks == right.restTicks &&
        left.lookup == right.lookup && left.aux == right.aux;
}

template <typename Queue>
unsigned check() {
    unsigned cases = 0;
    for (const uint16_t cell : {uint16_t{65516}, uint16_t{65535}}) {
        for (const uint16_t word : {uint16_t{0}, uint16_t{0x3fff}, uint16_t{0x4000},
                                   uint16_t{0x7fff}, uint16_t{0x8000}, uint16_t{0xffff}}) {
            for (const size_t count : {size_t{0}, size_t{1400}, size_t{1401}, size_t{1402}}) {
                lezac::resources::Level level;
                level.width = 60; level.height = 33;
                level.tiles.resize(1980); level.wordLayer.resize(1980);
                lezac::gameplay::MapPlaneMemory memory;
                memory.restoreSeparatedPlanesForFixture();
                const uint16_t alias = cell & 0x7fff;
                memory.writeObject(cell, 39, level.tiles, level.wordLayer);
                memory.writeObject(alias, 97, level.tiles, level.wordLayer);
                memory.writeWord(alias, word, level.tiles, level.wordLayer);
                Queue records;
                for (size_t index = 0; index < count; ++index) records.push_back(salt(index));
                const auto candidate = salt(655);
                if constexpr (std::is_same_v<Queue, Retained>) records.retainedSlot(count) = candidate;
                unsigned reads = 0, objects = 0, writes = 0;
                const bool expected = word >= 0x4000 && (word & 0x8000) == 0 && 199 + count < 1600;
                const bool result = lezac::gameplay::seedFallingFragmentPhysical(records, cell, 0x81, 0x7f,
                    [&](size_t address) {
                        require(address == cell); ++reads;
                        return memory.readWord(static_cast<int>(address), level.tiles, level.wordLayer);
                    },
                    [&](size_t address) {
                        require(address == cell); ++objects;
                        return memory.readObject(static_cast<int>(address), level.tiles, level.wordLayer);
                    },
                    [&](size_t address, uint16_t value) {
                        require(address == cell); ++writes;
                        memory.writeWord(static_cast<int>(address), value, level.tiles, level.wordLayer);
                    });
                require(result == expected && reads == 1 && objects == expected && writes == expected);
                require(records.size() == count + expected);
                require(memory.readObject(cell, level.tiles, level.wordLayer) == 39);
                require(memory.readObject(alias, level.tiles, level.wordLayer) == 97);
                const auto flagged = expected ? static_cast<uint16_t>(word | 0x8000) : word;
                require(memory.readWord(cell, level.tiles, level.wordLayer) == flagged);
                require(memory.readWord(alias, level.tiles, level.wordLayer) == flagged);
                for (size_t index = 0; index < count; ++index) require(same(records[index], salt(index)));
                if (expected) {
                    Record inserted;
                    inserted.tileIndex = cell; inserted.flaggedWord = flagged;
                    inserted.velocityX = -127; inserted.velocityY = 127; inserted.lookup = 39;
                    require(same(records.back(), inserted));
                } else if constexpr (std::is_same_v<Queue, Retained>) {
                    require(same(records.retainedSlot(count), candidate));
                }
                ++cases;
            }
        }
    }
    return cases;
}
}

int main() {
    require(check<std::vector<Record>>() == 48 && check<Retained>() == 48);
    lezac::resources::Level level;
    level.tiles.resize(65537, 17); level.wordLayer.resize(65537, 0x4101);
    std::vector<Record> records;
    require(lezac::gameplay::seedFallingFragment(level, records, 65536, 0, 0));
    require(records.back().tileIndex == 65536 && records.back().lookup == 17);
    std::cout << "falling_fragment_physical=ok queues=2 cases=96 raw_cell_preserved=1 word_alias_only=1 "
                 "capacity_boundary=1 retained_candidate=1 logical_size_t_preserved=1\n";
}
