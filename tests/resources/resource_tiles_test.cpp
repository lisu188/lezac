#include "resources/tiles.hpp"

#include <cstdio>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

void writeJsonTile(std::ostream& out, int base) {
    out << "{\"rows_hex\":[";
    for (int row = 0; row < 8; ++row) {
        if (row) out << ',';
        out << '"';
        for (int col = 0; col < 8; ++col) {
            if (col) out << ' ';
            out << std::hex << std::setw(2) << std::setfill('0')
                << (base + row * 8 + col) << std::dec;
        }
        out << '"';
    }
    out << "]}";
}

void writeBinary(const std::string& path, const std::vector<uint8_t>& bytes) {
    std::ofstream out(path, std::ios::binary);
    out.write(reinterpret_cast<const char*>(bytes.data()),
              static_cast<std::streamsize>(bytes.size()));
}

bool throwsRaw(const std::string& path, const std::vector<uint8_t>& bytes) {
    writeBinary(path, bytes);
    bool threw = false;
    try {
        lezac::resources::loadRawTiles(path);
    } catch (const std::runtime_error&) {
        threw = true;
    }
    std::remove(path.c_str());
    return threw;
}

}

int main() {
    const std::string jsonPath = "resource_tiles_test.json";
    {
        std::ofstream out(jsonPath);
        out << "{\"tile_count\":2,\"tiles\":[";
        writeJsonTile(out, 0);
        out << ',';
        writeJsonTile(out, 64);
        out << "]}";
    }
    const auto jsonBank = lezac::resources::loadTiles(jsonPath);
    std::remove(jsonPath.c_str());
    if (jsonBank.count != 2 || jsonBank.pixels.size() != 128 ||
        jsonBank.tile(-1) != nullptr || jsonBank.tile(2) != nullptr ||
        jsonBank.tile(0) == nullptr || jsonBank.tile(1) == nullptr ||
        jsonBank.tile(0)[0] != 0 || jsonBank.tile(0)[63] != 63 ||
        jsonBank.tile(1)[0] != 64 || jsonBank.tile(1)[63] != 127) return 1;

    const std::string badJsonPath = "resource_tiles_bad.json";
    {
        std::ofstream out(badJsonPath);
        out << "{\"tile_count\":2,\"tiles\":[";
        writeJsonTile(out, 0);
        out << "]}";
    }
    bool badJson = false;
    try {
        lezac::resources::loadTiles(badJsonPath);
    } catch (const std::runtime_error&) {
        badJson = true;
    }
    std::remove(badJsonPath.c_str());
    if (!badJson) return 2;

    std::vector<uint8_t> raw{0, 2};
    for (int i = 0; i < 128; ++i) raw.push_back(static_cast<uint8_t>(i));
    const std::string rawPath = "resource_tiles_test.raw";
    writeBinary(rawPath, raw);
    const auto rawBank = lezac::resources::loadRawTiles(rawPath);
    std::remove(rawPath.c_str());
    if (rawBank.count != 2 || rawBank.pixels.size() != 128 ||
        rawBank.tile(0)[0] != 0 || rawBank.tile(1)[0] != 64 ||
        rawBank.tile(1)[63] != 127) return 3;

    if (!throwsRaw("resource_tiles_header.raw", {0})) return 4;
    if (!throwsRaw("resource_tiles_zero.raw", {0, 0})) return 5;

    std::vector<uint8_t> shortRaw{0, 1};
    shortRaw.resize(2 + 63, 0xaa);
    if (!throwsRaw("resource_tiles_payload.raw", shortRaw)) return 6;

    std::cout << "resource_tiles=ok json=2 raw=2 tile_lookup=1 guards=4\n";
    return 0;
}
