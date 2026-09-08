#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace lezac::resources {

uint16_t le16(const std::vector<uint8_t>& data, std::size_t off);
uint32_t le32(const std::vector<uint8_t>& data, std::size_t off);

template <std::size_t N>
uint16_t recLe16(const std::array<uint8_t, N>& rec, std::size_t off) {
    if (off > N || N - off < 2) {
        throw std::runtime_error("unexpected EOF while reading record u16");
    }
    return static_cast<uint16_t>(rec[off] | (rec[off + 1] << 8));
}

uint8_t getU8(const std::vector<uint8_t>& data, std::size_t& off);
uint16_t getU16(const std::vector<uint8_t>& data, std::size_t& off);

template <std::size_t N>
std::vector<std::array<uint8_t, N>> getFixedRecords(const std::vector<uint8_t>& data,
                                                     std::size_t& off) {
    std::size_t cursor = off;
    uint8_t count = getU8(data, cursor);
    if (count != 0 && N > (data.size() - cursor) / count) {
        throw std::runtime_error("truncated fixed record block");
    }
    std::vector<std::array<uint8_t, N>> out;
    out.reserve(count);
    for (uint8_t i = 0; i < count; ++i) {
        std::array<uint8_t, N> rec{};
        std::copy_n(data.begin() +
                        static_cast<std::vector<uint8_t>::difference_type>(cursor),
                    N, rec.begin());
        cursor += N;
        out.push_back(rec);
    }
    off = cursor;
    return out;
}

std::vector<uint8_t> getBytes(const std::vector<uint8_t>& data, std::size_t& off,
                              std::size_t size);

}
