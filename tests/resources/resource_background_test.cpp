#include "resources/background.hpp"

#include <cstdio>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

void writeJson(const std::string& path, int paletteEntries, bool fullPixels) {
    std::ofstream out(path);
    out << "{\"palette\":[";
    for (int i = 0; i < paletteEntries; ++i) {
        if (i) out << ',';
        out << "{\"rgb8\":[" << i << ',' << ((i + 1) & 255) << ','
            << ((i + 2) & 255) << "]}";
    }
    out << "],\"width\":2,\"height\":2,\"pixel_rows_hex\":[\"01 02\"";
    if (fullPixels) out << ",\"03 04\"";
    out << "]}";
}

void writeBinary(const std::string& path, const std::vector<uint8_t>& bytes) {
    std::ofstream out(path, std::ios::binary);
    out.write(reinterpret_cast<const char*>(bytes.data()),
              static_cast<std::streamsize>(bytes.size()));
}

}

int main() {
    const std::string jsonPath = "resource_background_test.json";
    writeJson(jsonPath, 256, true);
    lezac::resources::Palette jsonPalette{};
    const auto jsonImage = lezac::resources::loadBackground(jsonPath, jsonPalette);
    std::remove(jsonPath.c_str());
    if (jsonImage.width != 2 || jsonImage.height != 2 ||
        jsonImage.pixels != std::vector<uint8_t>({1, 2, 3, 4}) ||
        jsonPalette[0].r != 0 || jsonPalette[0].g != 1 || jsonPalette[0].b != 2 ||
        jsonPalette[255].r != 255 || jsonPalette[255].g != 0 || jsonPalette[255].b != 1) return 1;

    const std::string paletteBadPath = "resource_background_palette_bad.json";
    writeJson(paletteBadPath, 255, true);
    bool paletteBad = false;
    try {
        lezac::resources::Palette palette{};
        lezac::resources::loadBackground(paletteBadPath, palette);
    } catch (const std::runtime_error&) {
        paletteBad = true;
    }
    std::remove(paletteBadPath.c_str());
    if (!paletteBad) return 2;

    const std::string pixelsBadPath = "resource_background_pixels_bad.json";
    writeJson(pixelsBadPath, 256, false);
    bool pixelsBad = false;
    try {
        lezac::resources::Palette palette{};
        lezac::resources::loadBackground(pixelsBadPath, palette);
    } catch (const std::runtime_error&) {
        pixelsBad = true;
    }
    std::remove(pixelsBadPath.c_str());
    if (!pixelsBad) return 3;

    std::vector<uint8_t> raw(770, 0);
    raw[0] = 0;
    raw[1] = 32;
    raw[2] = 63;
    constexpr int groups = 2000;
    constexpr int rleLength = groups * 3;
    raw[768] = static_cast<uint8_t>(rleLength & 0xff);
    raw[769] = static_cast<uint8_t>((rleLength >> 8) & 0xff);
    raw.reserve(770 + rleLength);
    for (int i = 0; i < groups; ++i) {
        raw.push_back(0xff);
        raw.push_back(0x12);
        raw.push_back(0x34);
    }

    const std::string rawPath = "resource_background_test.raw";
    writeBinary(rawPath, raw);
    lezac::resources::Palette rawPalette{};
    const auto rawImage = lezac::resources::loadRawBackground(rawPath, rawPalette);
    std::remove(rawPath.c_str());
    if (rawImage.width != 320 || rawImage.height != 200 || rawImage.pixels.size() != 64000 ||
        rawImage.pixels[0] != 0x12 || rawImage.pixels[15] != 0x12 ||
        rawImage.pixels[16] != 0x34 || rawImage.pixels[31] != 0x34 ||
        rawImage.pixels.back() != 0x34 ||
        rawPalette[0].r != 0 || rawPalette[0].g != 130 || rawPalette[0].b != 255) return 4;

    const std::string rawSmallPath = "resource_background_small.raw";
    writeBinary(rawSmallPath, std::vector<uint8_t>(769, 0));
    bool rawSmall = false;
    try {
        lezac::resources::Palette palette{};
        lezac::resources::loadRawBackground(rawSmallPath, palette);
    } catch (const std::runtime_error&) {
        rawSmall = true;
    }
    std::remove(rawSmallPath.c_str());
    if (!rawSmall) return 5;

    std::vector<uint8_t> shortRle(773, 0);
    shortRle[768] = 3;
    shortRle[770] = 0x00;
    shortRle[771] = 0x01;
    shortRle[772] = 0x02;
    const std::string shortRlePath = "resource_background_short_rle.raw";
    writeBinary(shortRlePath, shortRle);
    bool shortDecode = false;
    try {
        lezac::resources::Palette palette{};
        lezac::resources::loadRawBackground(shortRlePath, palette);
    } catch (const std::runtime_error&) {
        shortDecode = true;
    }
    std::remove(shortRlePath.c_str());
    if (!shortDecode) return 6;

    std::cout << "resource_background=ok json=4 raw=64000 palette=256 guards=4\n";
    return 0;
}
