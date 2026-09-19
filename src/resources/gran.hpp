#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace lezac::resources {

inline constexpr size_t kGranRecordSize = 57;

struct GranRecord {
    std::vector<uint8_t> bytes;
};

struct GranBank {
    size_t recordSize = kGranRecordSize;
    std::vector<GranRecord> records;
};

GranBank loadGran(const std::string& path);
GranBank loadRawGran(const std::string& path);

}
