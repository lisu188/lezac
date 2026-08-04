#include "resources/binary.hpp"

#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>

int main() {
    const std::vector<uint8_t> data{0x78, 0x56, 0x34, 0x12, 0xaa, 0xbb, 0xcc};
    if (lezac::resources::le16(data, 0) != 0x5678) return 1;
    if (lezac::resources::le32(data, 0) != 0x12345678u) return 2;

    bool truncated16 = false;
    bool truncated32 = false;
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
    if (!truncated16 || !truncated32) return 3;

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

    std::cout << "resource_binary=ok le16=1 le32=1 cursor=1 records=2 bytes=2 truncation=4\n";
    return 0;
}
