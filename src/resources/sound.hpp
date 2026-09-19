#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace lezac::resources {

inline constexpr size_t kSoundStepSize = 6;

struct SoundEffectRecord {
    std::vector<uint8_t> bytes;
};

struct SoundBank {
    uint16_t recordSize = 0;
    std::vector<SoundEffectRecord> records;
    std::vector<uint8_t> payload;
    size_t stepCount = 0;
};

SoundBank loadSon(const std::string& path);
SoundBank loadRawSon(const std::string& path);

}
