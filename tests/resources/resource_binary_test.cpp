#include "resources/binary.hpp"

#include <array>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>


namespace {

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

template <typename Action>
void requireRejected(Action action, const char* message) {
    bool rejected = false;
    try {
        action();
    } catch (const std::runtime_error&) {
        rejected = true;
    }
    require(rejected, message);
}

void checkBounds() {
    using namespace lezac::resources;
    const auto max = std::numeric_limits<std::size_t>::max();
    for (std::size_t length = 0; length <= 12; ++length) {
        std::vector<uint8_t> data(length);
        for (std::size_t i = 0; i < length; ++i) {
            data[i] = static_cast<uint8_t>(0x80 + i);
        }
        const std::array<std::size_t, 12> offsets{
            0, 1, 2, 3, length, length + 1,
            max, max - 1, max - 2, max - 3, max - 4, max - 7};
        for (const auto start : offsets) {
            const auto remaining = start <= length ? length - start : 0;
            if (remaining >= 2) {
                const auto expected = static_cast<uint16_t>(
                    static_cast<uint32_t>(data[start]) +
                    static_cast<uint32_t>(data[start + 1]) * 256u);
                require(le16(data, start) == expected, "le16 boundary value");
                std::size_t off = start;
                require(getU16(data, off) == expected && off == start + 2,
                        "getU16 boundary cursor");
            } else {
                requireRejected([&] { le16(data, start); }, "le16 accepted invalid offset");
                std::size_t off = start;
                requireRejected([&] { getU16(data, off); }, "getU16 accepted invalid offset");
                require(off == start, "getU16 advanced failed cursor");
            }
            if (remaining >= 4) {
                uint64_t expected = 0;
                uint64_t multiplier = 1;
                for (std::size_t i = 0; i < 4; ++i) {
                    expected += data[start + i] * multiplier;
                    multiplier *= 256;
                }
                require(le32(data, start) == expected, "le32 boundary value");
            } else {
                requireRejected([&] { le32(data, start); }, "le32 accepted invalid offset");
            }
            std::size_t off = start;
            if (remaining != 0) {
                require(getU8(data, off) == data[start] && off == start + 1,
                        "getU8 boundary cursor");
            } else {
                requireRejected([&] { getU8(data, off); }, "getU8 accepted invalid offset");
                require(off == start, "getU8 advanced failed cursor");
            }
            const std::array<std::size_t, 8> sizes{0, 1, 2, 4, length, length + 1, max, max - 1};
            for (const auto size : sizes) {
                off = start;
                if (start <= length && size <= remaining) {
                    const auto result = getBytes(data, off, size);
                    require(result.size() == size && off == start + size,
                            "getBytes boundary cursor");
                    for (std::size_t i = 0; i < size; ++i) {
                        require(result[i] == data[start + i], "getBytes boundary content");
                    }
                } else {
                    requireRejected([&] { getBytes(data, off, size); },
                                    "getBytes accepted invalid block");
                    require(off == start, "getBytes advanced failed cursor");
                }
            }
        }
    }
    const std::array<uint8_t, 4> record{0x78, 0x56, 0x34, 0x12};
    for (const auto off : std::array<std::size_t, 5>{3, 4, 5, max - 1, max}) {
        requireRejected([&] { recLe16(record, off); }, "recLe16 accepted invalid offset");
    }
    requireRejected([&] { recLe16(std::array<uint8_t, 0>{}, 0); },
                    "recLe16 accepted empty record");
    requireRejected([&] { recLe16(std::array<uint8_t, 1>{0xff}, 0); },
                    "recLe16 accepted short record");
    require(recLe16(record, 0) == 0x5678 && recLe16(record, 2) == 0x1234,
            "recLe16 exact boundaries");
    for (const auto start : std::array<std::size_t, 4>{1, 2, max - 1, max}) {
        std::size_t off = start;
        requireRejected([&] { getFixedRecords<3>({0}, off); },
                        "getFixedRecords accepted missing count");
        require(off == start, "getFixedRecords advanced missing-count cursor");
    }
    std::size_t off = 0;
    requireRejected([&] { getFixedRecords<3>({}, off); },
                    "getFixedRecords accepted empty input");
    require(off == 0, "getFixedRecords advanced empty-input cursor");
}

void checkEndianValues() {
    using namespace lezac::resources;
    std::vector<uint8_t> bytes{0xaa, 0, 0, 0xbb};
    for (uint32_t value = 0; value <= 0xffffu; ++value) {
        bytes[1] = static_cast<uint8_t>(value);
        bytes[2] = static_cast<uint8_t>(value / 256u);
        const std::array<uint8_t, 4> record{bytes[0], bytes[1], bytes[2], bytes[3]};
        require(le16(bytes, 1) == value && recLe16(record, 1) == value,
                "u16 exhaustive endian mismatch");
        std::size_t off = 1;
        require(getU16(bytes, off) == value && off == 3, "u16 exhaustive cursor mismatch");
    }
    for (unsigned shift = 0; shift < 32; shift += 8) {
        for (uint32_t byte = 0; byte < 256; ++byte) {
            const uint32_t expected = (0x12345678u & ~(0xffu << shift)) | (byte << shift);
            for (std::size_t i = 0; i < bytes.size(); ++i) {
                bytes[i] = static_cast<uint8_t>(expected >> (8 * i));
            }
            require(le32(bytes, 0) == expected, "u32 endian mismatch");
        }
    }
    require(le32({0xff, 0xff, 0xff, 0xff}, 0) == 0xffffffffu, "u32 maximum value");
}

void checkRecordCounts() {
    using namespace lezac::resources;
    for (unsigned count = 0; count <= 255; ++count) {
        std::vector<uint8_t> data{0xaa, 0x55, static_cast<uint8_t>(count)};
        for (unsigned i = 0; i < count * 3; ++i) data.push_back(static_cast<uint8_t>(i));
        const auto end = data.size();
        data.push_back(0xfe);
        data.push_back(0xef);
        std::size_t off = 2;
        const auto records = getFixedRecords<3>(data, off);
        require(records.size() == count && off == end, "fixed record count or cursor");
        for (std::size_t i = 0; i < records.size(); ++i) {
            for (std::size_t j = 0; j < 3; ++j) {
                require(records[i][j] == static_cast<uint8_t>(i * 3 + j),
                        "fixed record content");
            }
        }
        if (count != 0) {
            data.resize(end - 1);
            off = 2;
            requireRejected([&] { getFixedRecords<3>(data, off); },
                            "fixed records accepted truncated payload");
            require(off == 2, "fixed records advanced truncated-payload cursor");
        }
        off = 0;
        const auto empty = getFixedRecords<0>({static_cast<uint8_t>(count)}, off);
        require(empty.size() == count && off == 1, "zero-width record compatibility");
    }
}

}

int main() {
    const std::vector<uint8_t> data{0x78, 0x56, 0x34, 0x12, 0xaa, 0xbb, 0xcc};
    if (lezac::resources::le16(data, 0) != 0x5678) return 1;
    if (lezac::resources::le32(data, 0) != 0x12345678u) return 2;

    bool truncated16 = false;
    bool truncated32 = false;
    bool truncated8 = false;
    try {
        lezac::resources::le16(std::vector<uint8_t>{0x01}, 0);
    } catch (const std::runtime_error&) {
        truncated16 = true;
    }
    try {
        lezac::resources::le32(std::vector<uint8_t>{0x01, 0x02, 0x03}, 0);
    } catch (const std::runtime_error&) {
        truncated32 = true;
    }
    try {
        std::size_t badOff = 0;
        lezac::resources::getU8(std::vector<uint8_t>{}, badOff);
    } catch (const std::runtime_error&) {
        truncated8 = true;
    }
    if (!truncated16 || !truncated32 || !truncated8) return 3;

    std::size_t off = 0;
    const std::vector<uint8_t> cursorData{0x7f, 0x34, 0x12, 0xde, 0xad};
    if (lezac::resources::getU8(cursorData, off) != 0x7f || off != 1) return 4;
    if (lezac::resources::getU16(cursorData, off) != 0x1234 || off != 3) return 5;
    if (lezac::resources::getBytes(cursorData, off, 2) !=
            std::vector<uint8_t>({0xde, 0xad}) ||
        off != 5) return 6;

    const std::array<uint8_t, 4> rec{{0x00, 0x34, 0x12, 0xff}};
    if (lezac::resources::recLe16(rec, 1) != 0x1234) return 7;

    std::size_t recordsOff = 0;
    const std::vector<uint8_t> recordsData{2, 1, 2, 3, 4, 5, 6};
    const auto records = lezac::resources::getFixedRecords<3>(recordsData, recordsOff);
    if (records.size() != 2 || recordsOff != recordsData.size() ||
        records[0] != std::array<uint8_t, 3>{{1, 2, 3}} ||
        records[1] != std::array<uint8_t, 3>{{4, 5, 6}}) return 8;

    bool truncatedRecords = false;
    bool truncatedBytes = false;
    try {
        std::size_t badOff = 0;
        lezac::resources::getFixedRecords<3>(std::vector<uint8_t>{2, 1, 2, 3}, badOff);
    } catch (const std::runtime_error&) {
        truncatedRecords = true;
    }
    try {
        std::size_t badOff = 0;
        lezac::resources::getBytes(std::vector<uint8_t>{1}, badOff, 2);
    } catch (const std::runtime_error&) {
        truncatedBytes = true;
    }
    if (!truncatedRecords || !truncatedBytes) return 9;

    try {
        checkBounds();
        checkEndianValues();
        checkRecordCounts();
    } catch (const std::exception& error) {
        std::cerr << "resource_binary: " << error.what() << '\n';
        return 10;
    }

    std::cout << "resource_binary=ok le16=1 le32=1 cursor=1 records=2 bytes=2 truncation=5\n";
    std::cout << "bounds=ok endian16=65536 endian32=1025 record_counts=256 cursor_rollback=ok\n";
    return 0;
}
