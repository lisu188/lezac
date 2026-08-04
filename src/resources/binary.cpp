#include "resources/binary.hpp"

namespace lezac::resources {

uint16_t le16(const std::vector<uint8_t>& data, std::size_t off) {
    if (off + 2 > data.size()) {
        throw std::runtime_error("unexpected EOF while reading u16");
    }
    return static_cast<uint16_t>(data[off] | (data[off + 1] << 8));
}

uint32_t le32(const std::vector<uint8_t>& data, std::size_t off) {
    if (off + 4 > data.size()) {
        throw std::runtime_error("unexpected EOF while reading u32");
    }
    return static_cast<uint32_t>(data[off] | (data[off + 1] << 8) |
                                 (data[off + 2] << 16) | (data[off + 3] << 24));
}

uint8_t getU8(const std::vector<uint8_t>& data, std::size_t& off) {
    if (off >= data.size()) {
        throw std::runtime_error("unexpected EOF while reading u8");
    }
    return data[off++];
}

uint16_t getU16(const std::vector<uint8_t>& data, std::size_t& off) {
    uint16_t value = le16(data, off);
    off += 2;
    return value;
}

std::vector<uint8_t> getBytes(const std::vector<uint8_t>& data, std::size_t& off,
                              std::size_t size) {
    if (off + size > data.size()) {
        throw std::runtime_error("truncated byte block");
    }
    std::vector<uint8_t> out(data.begin() + static_cast<long>(off),
                             data.begin() + static_cast<long>(off + size));
    off += size;
    return out;
}

}
