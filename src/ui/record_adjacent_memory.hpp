#pragma once

#include "resources/records.hpp"
#include <cstddef>
#include <cstdint>
#include <optional>

namespace lezac::ui {

struct OriginalFarPointer {
    uint16_t offset = 0;
    uint16_t segment = 0;
    bool operator==(const OriginalFarPointer&) const = default;
};

// DOS rank eight overlaps DS:1b5f..1b6b, including saved interrupt handlers.
// Retaining those bytes does not emulate interrupt dispatch or its frozen frame.
class RecordAdjacentMemory {
public:
    using Bytes = resources::RecordWireBytes;
    static constexpr uint16_t beginOffset = 0x1b5f;

    bool initialized() const { return initialized_; }
    std::optional<Bytes> snapshot() const {
        if (!initialized_) return std::nullopt;
        return bytes_;
    }
    std::optional<OriginalFarPointer> keyboardHandler() const { return pointerAt(1); }
    std::optional<OriginalFarPointer> timerHandler() const { return pointerAt(5); }

    void retainRankEight(const resources::Record& record) {
        bytes_ = resources::encodedRecordBytes(record);
        initialized_ = true;
    }
    void seedForFixture(const Bytes& bytes) {
        bytes_ = bytes;
        initialized_ = true;
    }

private:
    Bytes bytes_{};
    bool initialized_ = false;

    uint16_t wordAt(size_t offset) const {
        return static_cast<uint16_t>(bytes_[offset] | (static_cast<uint16_t>(bytes_[offset + 1]) << 8));
    }
    std::optional<OriginalFarPointer> pointerAt(size_t offset) const {
        if (!initialized_) return std::nullopt;
        return OriginalFarPointer{wordAt(offset), wordAt(offset + 2)};
    }
};

}  // namespace lezac::ui
