#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace lezac::gameplay {

// Map accesses use segment-relative 16-bit offsets, not logical map bounds.
// This retains map heap bytes; it does not emulate other Pascal allocations.
class MapPlaneMemory {
public:
    bool hasLevelAllocation() const { return allocated_; }

    void beginLevel(const std::vector<uint8_t>& oldTiles,
                    const std::vector<uint16_t>& oldWords, size_t newCellCount) {
        if (newCellCount == 0 || newCellCount > 16384) {
            throw std::runtime_error("unsupported map allocation size");
        }
        if (allocated_) {
            std::copy(oldTiles.begin(), oldTiles.end(), bytes_.begin() + objectBase);
            for (size_t i = 0; i < oldWords.size(); ++i) {
                bytes_[wordBase_ + 2 * i] = static_cast<uint8_t>(oldWords[i]);
                bytes_[wordBase_ + 2 * i + 1] = static_cast<uint8_t>(oldWords[i] >> 8);
            }
            // FreeMem writes size metadata before retracting the heap top.
            freeMetadata(roundedAllocation(cellCount_), roundedAllocation(2 * cellCount_));
            freeMetadata(0, roundedAllocation(cellCount_));
        }
        cellCount_ = newCellCount;
        wordBase_ = ((8 + roundedAllocation(newCellCount) + 15) & ~size_t(15)) - 8;
        allocated_ = true;
    }

    void restoreSeparatedPlanesForFixture(const std::vector<uint8_t>& planes = {}) {
        if (!planes.empty() && planes.size() != 2 * segmentBytes) {
            throw std::runtime_error("invalid seeded map planes");
        }
        bytes_.fill(0);
        wordBase_ = objectBase + segmentBytes;
        allocated_ = false;
        if (!planes.empty()) seedPlanesForFixture(planes);
    }

    void seedPlanesForFixture(const std::vector<uint8_t>& planes) {
        if (planes.size() != 2 * segmentBytes) {
            throw std::runtime_error("invalid seeded map planes");
        }
        std::copy(planes.begin(), planes.begin() + segmentBytes, bytes_.begin() + objectBase);
        std::copy(planes.begin() + segmentBytes, planes.end(), bytes_.begin() + wordBase_);
    }

    uint8_t readObject(int cell, const std::vector<uint8_t>& tiles,
                       const std::vector<uint16_t>& words) const {
        return readByte(objectBase + static_cast<uint16_t>(cell), tiles, words);
    }

    void writeObject(int cell, uint8_t value, std::vector<uint8_t>& tiles,
                     std::vector<uint16_t>& words) {
        writeByte(objectBase + static_cast<uint16_t>(cell), value, tiles, words);
    }

    uint16_t readWord(int cell, const std::vector<uint8_t>& tiles,
                      const std::vector<uint16_t>& words) const {
        const size_t address = wordBase_ + static_cast<uint16_t>(static_cast<uint16_t>(cell) * 2u);
        return static_cast<uint16_t>(readByte(address, tiles, words) |
                                     (static_cast<uint16_t>(readByte(address + 1, tiles, words)) << 8));
    }

    void writeWord(int cell, uint16_t value, std::vector<uint8_t>& tiles,
                   std::vector<uint16_t>& words) {
        const size_t address = wordBase_ + static_cast<uint16_t>(static_cast<uint16_t>(cell) * 2u);
        writeByte(address, static_cast<uint8_t>(value), tiles, words);
        writeByte(address + 1, static_cast<uint8_t>(value >> 8), tiles, words);
    }

    void retainObjectDecoderTail(const std::vector<uint8_t>& tail,
                                 std::vector<uint8_t>& tiles, std::vector<uint16_t>& words) {
        if (tail.size() > 16) throw std::runtime_error("invalid object decoder tail");
        for (size_t i = 0; i < tail.size(); ++i) {
            writeByte(objectBase + static_cast<uint16_t>(tiles.size() + i), tail[i], tiles, words);
        }
    }

    void retainWordDecoderTail(const std::vector<uint8_t>& tail,
                               std::vector<uint8_t>& tiles, std::vector<uint16_t>& words) {
        if (tail.size() > 16) throw std::runtime_error("invalid word decoder tail");
        for (size_t i = 0; i < tail.size(); ++i) {
            writeByte(wordBase_ + static_cast<uint16_t>(2 * words.size() + i), tail[i], tiles, words);
        }
    }

private:
    static constexpr size_t segmentBytes = 65536;
    static constexpr size_t objectBase = 8;
    std::array<uint8_t, 2 * segmentBytes + objectBase> bytes_{};
    size_t wordBase_ = objectBase + segmentBytes;
    size_t cellCount_ = 0;
    bool allocated_ = false;

    static size_t roundedAllocation(size_t payload) {
        return (payload + 23) & ~size_t(7);
    }

    void freeMetadata(size_t rawBase, size_t size) {
        bytes_[rawBase + 4] = static_cast<uint8_t>(size & 15);
        bytes_[rawBase + 5] = 0;
        bytes_[rawBase + 6] = static_cast<uint8_t>(size >> 4);
        bytes_[rawBase + 7] = static_cast<uint8_t>(size >> 12);
    }

    uint8_t readByte(size_t address, const std::vector<uint8_t>& tiles,
                     const std::vector<uint16_t>& words) const {
        if (address >= objectBase && address - objectBase < tiles.size()) {
            return tiles[address - objectBase];
        }
        if (address >= wordBase_ && address - wordBase_ < 2 * words.size()) {
            const size_t offset = address - wordBase_;
            return static_cast<uint8_t>(words[offset / 2] >> (8 * (offset % 2)));
        }
        return bytes_[address];
    }

    void writeByte(size_t address, uint8_t value, std::vector<uint8_t>& tiles,
                   std::vector<uint16_t>& words) {
        if (address >= objectBase && address - objectBase < tiles.size()) {
            tiles[address - objectBase] = value;
        } else if (address >= wordBase_ && address - wordBase_ < 2 * words.size()) {
            const size_t offset = address - wordBase_;
            const unsigned shift = static_cast<unsigned>(8 * (offset % 2));
            const uint16_t mask = static_cast<uint16_t>(0xffu << shift);
            words[offset / 2] = static_cast<uint16_t>((words[offset / 2] & ~mask) |
                                                    (static_cast<uint16_t>(value) << shift));
        } else {
            bytes_[address] = value;
        }
    }
};

}  // namespace lezac::gameplay
