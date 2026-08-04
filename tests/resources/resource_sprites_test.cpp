#include "resources/sprites.hpp"

#include <cstdio>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

void writeBinary(const std::string& path, const std::vector<uint8_t>& bytes) {
    std::ofstream out(path, std::ios::binary);
    out.write(reinterpret_cast<const char*>(bytes.data()),
              static_cast<std::streamsize>(bytes.size()));
}

bool throwsRaw(const std::string& path, const std::vector<uint8_t>& bytes) {
    writeBinary(path, bytes);
    bool threw = false;
    try {
        lezac::resources::loadRawSprites(path);
    } catch (const std::runtime_error&) {
        threw = true;
    }
    std::remove(path.c_str());
    return threw;
}

}

int main() {
    const std::string jsonPath = "resource_sprites_test.json";
    {
        std::ofstream out(jsonPath);
        out << R"({"sprites":[{"width":2,"height":2,"rows_hex":["01 02","03 04"]},{"width":1,"height":1,"rows_hex":["ff"]}]})";
    }
    const auto jsonBank = lezac::resources::loadSprites(jsonPath);
    std::remove(jsonPath.c_str());
    if (jsonBank.sprites.size() != 2 || jsonBank.sprites[0].width != 2 ||
        jsonBank.sprites[0].height != 2 ||
        jsonBank.sprites[0].pixels != std::vector<uint8_t>({1, 2, 3, 4}) ||
        jsonBank.sprites[1].pixels != std::vector<uint8_t>({0xff})) return 1;

    const std::string badJsonPath = "resource_sprites_bad.json";
    {
        std::ofstream out(badJsonPath);
        out << R"({"sprites":[{"width":2,"height":2,"rows_hex":["01 02"]}]})";
    }
    bool badJson = false;
    try {
        lezac::resources::loadSprites(badJsonPath);
    } catch (const std::runtime_error&) {
        badJson = true;
    }
    std::remove(badJsonPath.c_str());
    if (!badJson) return 2;

    const std::string rawPath = "resource_sprites_test.raw";
    writeBinary(rawPath, {2, 2, 2, 1, 2, 3, 4, 1, 1, 0xff});
    const auto rawBank = lezac::resources::loadRawSprites(rawPath);
    std::remove(rawPath.c_str());
    if (rawBank.sprites.size() != 2 || rawBank.sprites[0].width != 2 ||
        rawBank.sprites[0].height != 2 ||
        rawBank.sprites[0].pixels != std::vector<uint8_t>({1, 2, 3, 4}) ||
        rawBank.sprites[1].pixels != std::vector<uint8_t>({0xff})) return 3;

    if (!throwsRaw("resource_sprites_empty.raw", {})) return 4;
    if (!throwsRaw("resource_sprites_header.raw", {1, 2})) return 5;
    if (!throwsRaw("resource_sprites_pixels.raw", {1, 2, 2, 1, 2, 3})) return 6;
    if (!throwsRaw("resource_sprites_trailing.raw", {1, 1, 1, 7, 8})) return 7;

    std::cout << "resource_sprites=ok json=2 raw=2 guards=5\n";
    return 0;
}
