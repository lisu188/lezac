#pragma once

#include "gameplay/damage_lane_bytes.hpp"
#include "gameplay/fracture_records.hpp"
#include "gameplay/retained_record_queue.hpp"

#include <array>
#include <cstddef>
#include <cstdint>

namespace lezac::gameplay {

inline uint8_t laneWordByte(uint16_t word, size_t offset) {
    return static_cast<uint8_t>(word >> (8 * offset));
}

inline uint16_t replaceLaneWordByte(uint16_t word, size_t offset, uint8_t byte) {
    const unsigned shift = static_cast<unsigned>(8 * offset);
    return static_cast<uint16_t>((word & ~(0xffu << shift)) | (static_cast<unsigned>(byte) << shift));
}

inline uint8_t debrisLaneByte(const DebrisRecord& record, size_t offset) {
    if (offset < 2) return laneWordByte(static_cast<uint16_t>(record.tileIndex), offset);
    if (offset < 4) return laneWordByte(record.flaggedWord, offset - 2);
    switch (offset) {
    case 4: return static_cast<uint8_t>(record.velocityX);
    case 5: return static_cast<uint8_t>(record.velocityY);
    case 6: return static_cast<uint8_t>(record.subX);
    case 7: return static_cast<uint8_t>(record.subY);
    case 8: return record.restTicks;
    case 9: return record.lookup;
    default: return record.aux;
    }
}

inline void writeDebrisLaneByte(DebrisRecord& record, size_t offset, uint8_t byte) {
    if (offset < 2) {
        record.tileIndex = replaceLaneWordByte(static_cast<uint16_t>(record.tileIndex), offset, byte);
    } else if (offset < 4) record.flaggedWord = replaceLaneWordByte(record.flaggedWord, offset - 2, byte);
    else switch (offset) {
    case 4: record.velocityX = static_cast<int8_t>(damageLaneSignedByte(byte)); break;
    case 5: record.velocityY = static_cast<int8_t>(damageLaneSignedByte(byte)); break;
    case 6: record.subX = static_cast<int8_t>(damageLaneSignedByte(byte)); break;
    case 7: record.subY = static_cast<int8_t>(damageLaneSignedByte(byte)); break;
    case 8: record.restTicks = byte; break;
    case 9: record.lookup = byte; break;
    default: record.aux = byte; break;
    }
}

inline uint8_t collapseLaneByte(const CollapseRecord& record, size_t offset) {
    if (offset < 2) return laneWordByte(record.startOffsetBytes, offset);
    if (offset < 4) return laneWordByte(record.endOffsetBytes, offset - 2);
    if (offset < 6) return laneWordByte(record.flaggedWord, offset - 4);
    switch (offset) {
    case 6: return record.forwardPhase;
    case 7: return record.reversePhase;
    case 8: return static_cast<uint8_t>(record.subX);
    case 9: return static_cast<uint8_t>(record.subY);
    case 10: case 11: return laneWordByte(record.argMagnitude, offset - 10);
    case 12: return record.flags;
    case 13: return record.restTicks;
    default: return record.affectedBytes;
    }
}

inline void writeCollapseLaneByte(CollapseRecord& record, size_t offset, uint8_t byte) {
    if (offset < 2) record.startOffsetBytes = replaceLaneWordByte(record.startOffsetBytes, offset, byte);
    else if (offset < 4) record.endOffsetBytes = replaceLaneWordByte(record.endOffsetBytes, offset - 2, byte);
    else if (offset < 6) {
        record.flaggedWord = replaceLaneWordByte(record.flaggedWord, offset - 4, byte);
        record.word = static_cast<uint16_t>(record.flaggedWord & 0x7fff);
    } else switch (offset) {
    case 6: record.forwardPhase = byte; break;
    case 7: record.reversePhase = byte; break;
    case 8: record.subX = static_cast<int8_t>(damageLaneSignedByte(byte)); break;
    case 9: record.subY = static_cast<int8_t>(damageLaneSignedByte(byte)); break;
    case 10: case 11: record.argMagnitude = replaceLaneWordByte(record.argMagnitude, offset - 10, byte); break;
    case 12: record.flags = byte; break;
    case 13: record.restTicks = byte; break;
    default: record.affectedBytes = byte; break;
    }
}

inline uint8_t flameLaneByte(const FlameRecord& record, size_t offset) {
    if (offset < 2) return laneWordByte(record.cell, offset);
    if (offset < 4) return laneWordByte(record.retainedWord, offset - 2);
    switch (offset) {
    case 4: return static_cast<uint8_t>(record.vx);
    case 5: return static_cast<uint8_t>(record.vy);
    case 6: return static_cast<uint8_t>(record.subX);
    case 7: return static_cast<uint8_t>(record.subY);
    case 8: return record.timer;
    case 9: return record.glyph;
    default: return record.variant;
    }
}

inline void writeFlameLaneByte(FlameRecord& record, size_t offset, uint8_t byte) {
    if (offset < 2) record.cell = replaceLaneWordByte(record.cell, offset, byte);
    else if (offset < 4) record.retainedWord = replaceLaneWordByte(record.retainedWord, offset - 2, byte);
    else switch (offset) {
    case 4: record.vx = static_cast<int8_t>(damageLaneSignedByte(byte)); break;
    case 5: record.vy = static_cast<int8_t>(damageLaneSignedByte(byte)); break;
    case 6: record.subX = static_cast<int8_t>(damageLaneSignedByte(byte)); break;
    case 7: record.subY = static_cast<int8_t>(damageLaneSignedByte(byte)); break;
    case 8: record.timer = byte; break;
    case 9: record.glyph = byte; break;
    default: record.variant = byte; break;
    }
}

// Known DS owners are live references, not snapshots. Other addresses remain
// byte-addressed and can be consumed by later lookups or wrapped weight reads.
// This is not yet a model of every DOS global/actor/asset alias.
template <typename Sound>
class DamageLaneMemory {
    std::array<uint8_t, 65536>& bytes_;
    RetainedRecordQueue<DebrisRecord>& debris_;
    RetainedRecordQueue<CollapseRecord>& collapse_;
    RetainedRecordQueue<FlameRecord>& flames_;
    Sound& sound_;
    uint8_t& seeded_;
    std::array<int*, 4> lanes_;

public:
    DamageLaneMemory(std::array<uint8_t, 65536>& bytes, RetainedRecordQueue<DebrisRecord>& debris,
        RetainedRecordQueue<CollapseRecord>& collapse, RetainedRecordQueue<FlameRecord>& flames,
        Sound& sound, uint8_t& seeded, std::array<int*, 4> lanes = {})
        : bytes_(bytes), debris_(debris), collapse_(collapse), flames_(flames), sound_(sound),
          seeded_(seeded), lanes_(lanes) {
        const size_t retained = flames_.retainedSize();
        for (size_t index = retained; index < 199; ++index) {
            auto& record = flames_.retainedSlot(index);
            record.glyph = 0;
            record.mass = 0;
        }
        for (size_t index = 0; index < lanes_.size(); ++index)
            if (lanes_[index]) bytes_[0x78d2 + index] = static_cast<uint8_t>(*lanes_[index]);
    }

    ~DamageLaneMemory() {
        for (size_t index = 0; index < lanes_.size(); ++index)
            if (lanes_[index]) bytes_[0x78d2 + index] = static_cast<uint8_t>(*lanes_[index]);
    }

    uint8_t read(uint16_t address) {
        if (address >= 0x2074 && address < 0x2076) return laneWordByte(sound_.requestCursor(), address - 0x2074);
        if (address >= 0x2076 && address < 0x2078) return laneWordByte(static_cast<uint16_t>(flames_.size()), address - 0x2076);
        if (address >= 0x207e && address < 0x2080) return laneWordByte(static_cast<uint16_t>(debris_.size() + 199), address - 0x207e);
        if (address >= 0x2080 && address < 0x2082) return laneWordByte(static_cast<uint16_t>(collapse_.size()), address - 0x2080);
        if (address >= 0x209e && address < 0x292b) {
            const size_t offset = address - 0x209e;
            return flameLaneByte(flames_.retainedSlot(offset / 11), offset % 11);
        }
        if (address >= 0x292b && address < 0x6569) {
            const size_t offset = address - 0x292b;
            return debrisLaneByte(debris_.retainedSlot(offset / 11), offset % 11);
        }
        if (address >= 0x6620 && address < 0x74d5) {
            const size_t offset = address - 0x6620;
            return collapseLaneByte(collapse_.retainedSlot(offset / 15), offset % 15);
        }
        if (address >= 0x78d2 && address < 0x78d6 && lanes_[address - 0x78d2])
            return static_cast<uint8_t>(*lanes_[address - 0x78d2]);
        if (address >= 0x78d6 && address < 0x799d) return flames_.retainedSlot(address - 0x78d6).mass;
        if (address == 0x79c8) return seeded_;
        return bytes_[address];
    }

    void write(uint16_t address, uint8_t byte) {
        if (address >= 0x2074 && address < 0x2076) {
            sound_.writeSharedCursor(replaceLaneWordByte(sound_.requestCursor(), address - 0x2074, byte));
        } else if (address >= 0x2076 && address < 0x2078) {
            flames_.setLiveSize(replaceLaneWordByte(static_cast<uint16_t>(flames_.size()), address - 0x2076, byte));
        } else if (address >= 0x207e && address < 0x2080) {
            const uint16_t bound = replaceLaneWordByte(static_cast<uint16_t>(debris_.size() + 199), address - 0x207e, byte);
            debris_.setLiveSize(static_cast<uint16_t>(bound - 199));
        } else if (address >= 0x2080 && address < 0x2082) {
            collapse_.setLiveSize(replaceLaneWordByte(static_cast<uint16_t>(collapse_.size()), address - 0x2080, byte));
        } else if (address >= 0x209e && address < 0x292b) {
            const size_t offset = address - 0x209e;
            writeFlameLaneByte(flames_.retainedSlot(offset / 11), offset % 11, byte);
        } else if (address >= 0x292b && address < 0x6569) {
            const size_t offset = address - 0x292b;
            writeDebrisLaneByte(debris_.retainedSlot(offset / 11), offset % 11, byte);
        } else if (address >= 0x6620 && address < 0x74d5) {
            const size_t offset = address - 0x6620;
            writeCollapseLaneByte(collapse_.retainedSlot(offset / 15), offset % 15, byte);
        } else if (address >= 0x78d2 && address < 0x78d6 && lanes_[address - 0x78d2]) {
            *lanes_[address - 0x78d2] = damageLaneSignedByte(byte);
            bytes_[address] = byte;
        } else if (address >= 0x78d6 && address < 0x799d) flames_.retainedSlot(address - 0x78d6).mass = byte;
        else if (address == 0x79c8) seeded_ = byte;
        else bytes_[address] = byte;
    }
};

}  // namespace lezac::gameplay
