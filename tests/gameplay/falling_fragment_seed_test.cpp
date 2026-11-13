#include "gameplay/falling_fragment.hpp"
#include "gameplay/retained_record_queue.hpp"

#include <iostream>
#include <stdexcept>
#include <type_traits>

namespace {
using Record = lezac::gameplay::DebrisRecord;
using Retained = lezac::gameplay::RetainedRecordQueue<Record>;

void require(bool condition) {
    if (!condition) throw std::runtime_error("falling fragment seed contract failed");
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
           left.subX == right.subX && left.subY == right.subY &&
           left.restTicks == right.restTicks && left.lookup == right.lookup && left.aux == right.aux;
}

template <typename Queue>
unsigned check() {
    unsigned cases = 0;
    for (const uint16_t word : {uint16_t{0}, uint16_t{0x3fff}, uint16_t{0x4000},
                               uint16_t{0x7fff}, uint16_t{0x8000}, uint16_t{0xffff}}) {
        for (const size_t count : {size_t{0}, size_t{1400}, size_t{1401}, size_t{1402}}) {
            lezac::resources::Level level;
            level.width = 1; level.height = 1;
            level.tiles = {77}; level.wordLayer = {word};
            Queue records;
            for (size_t index = 0; index < count; ++index) records.push_back(salt(index));
            const auto candidate = salt(655);
            if constexpr (std::is_same_v<Queue, Retained>) records.retainedSlot(count) = candidate;
            const bool expected = word >= 0x4000 && (word & 0x8000) == 0 && 199 + count < 1600;
            const uint8_t result = static_cast<uint8_t>(
                lezac::gameplay::seedFallingFragment(level, records, 0, 0x81, 0x7f));
            require(result == static_cast<uint8_t>(expected));
            require(level.tiles[0] == 77 && records.size() == count + expected);
            require(level.wordLayer[0] == (expected ? static_cast<uint16_t>(word | 0x8000) : word));
            for (size_t index = 0; index < count; ++index) require(same(records[index], salt(index)));
            if (expected) {
                Record inserted;
                inserted.tileIndex = 0; inserted.flaggedWord = static_cast<uint16_t>(word | 0x8000);
                inserted.velocityX = -127; inserted.velocityY = 127; inserted.lookup = 77;
                require(same(records.back(), inserted));
                if constexpr (std::is_same_v<Queue, Retained>) require(same(records.retainedSlot(count), inserted));
            } else if constexpr (std::is_same_v<Queue, Retained>) {
                require(same(records.retainedSlot(count), candidate));
            }
            ++cases;
        }
    }
    return cases;
}
}

int main() {
    const auto vectorCases = check<std::vector<Record>>();
    const auto retainedCases = check<Retained>();
    require(vectorCases == 24 && retainedCases == 24);
    std::cout << "falling_fragment_seed=ok queues=2 cases=" << vectorCases + retainedCases
              << " retained_candidate=1 capacity_boundary=1 flagged_rejection=1\n";
}
