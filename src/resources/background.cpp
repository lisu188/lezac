#include "resources/background.hpp"

#include "core/constants.hpp"
#include "resources/io.hpp"
#include "resources/json.hpp"
#include "resources/palette.hpp"

#include <algorithm>
#include <cstddef>
#include <regex>
#include <stdexcept>

namespace lezac::resources {

IndexedImage loadBackground(const std::string& path, Palette& paletteOut) {
    auto json = readTextFile(path);
    std::regex rgbRe("\"rgb8\"\\s*:\\s*\\[\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\]");
    auto begin = std::sregex_iterator(json.begin(), json.end(), rgbRe);
    auto end = std::sregex_iterator();
    int pi = 0;
    for (auto it = begin; it != end && pi < 256; ++it, ++pi) {
        paletteOut[pi] = {
            static_cast<uint8_t>(std::stoi((*it)[1].str())),
            static_cast<uint8_t>(std::stoi((*it)[2].str())),
            static_cast<uint8_t>(std::stoi((*it)[3].str())),
        };
    }
    if (pi != 256) throw std::runtime_error(path + " palette section is incomplete");

    IndexedImage image;
    image.width = extractInt(json, "width", lezac::core::kBackgroundW);
    image.height = extractInt(json, "height", lezac::core::kBackgroundH);
    image.pixels.reserve(lezac::core::kBackgroundW * lezac::core::kBackgroundH);
    for (const auto& row : extractStringArray(json, "pixel_rows_hex")) {
        auto bytes = parseHexByteList(row);
        image.pixels.insert(image.pixels.end(), bytes.begin(), bytes.end());
    }
    if (image.pixels.size() != static_cast<std::size_t>(image.width) * image.height) {
        throw std::runtime_error(path + " decoded to " + std::to_string(image.pixels.size()) +
                                 " bytes, expected " +
                                 std::to_string(static_cast<std::size_t>(image.width) * image.height));
    }
    return image;
}

IndexedImage loadRawBackground(const std::string& path, Palette& paletteOut) {
    auto data = readFile(path);
    if (data.size() < 770) {
        throw std::runtime_error(path + " is too small for a palette and header");
    }
    paletteOut = loadPalette(data, 0);

    // Recovered from the original ZBG display routine (Ghidra 1000:030b, decoder
    // 1000:82d0). After the 768-byte VGA palette, a 2-byte little-endian length
    // header gives the RLE payload size; the payload is a nibble-paired RLE that
    // decodes to exactly one 320x200 mode-13h screen. Each 3-byte group
    // (b0, b1, b2) emits (b0>>4)+1 copies of b1 followed by (b0&0x0f)+1 copies
    // of b2.
    const std::size_t rleLength = static_cast<std::size_t>(data[768]) |
                                  (static_cast<std::size_t>(data[769]) << 8);
    const std::size_t rleEnd = std::min(data.size(), 770 + rleLength);
    const std::size_t targetPixels =
        static_cast<std::size_t>(lezac::core::kBackgroundW) * lezac::core::kBackgroundH;

    IndexedImage image;
    image.width = lezac::core::kBackgroundW;
    image.height = lezac::core::kBackgroundH;
    image.pixels.reserve(targetPixels);
    std::size_t off = 770;
    while (off + 3 <= rleEnd && image.pixels.size() < targetPixels) {
        const uint8_t b0 = data[off];
        const uint8_t value1 = data[off + 1];
        const uint8_t value2 = data[off + 2];
        off += 3;
        image.pixels.insert(image.pixels.end(),
                            static_cast<std::size_t>((b0 >> 4) & 0x0f) + 1, value1);
        image.pixels.insert(image.pixels.end(),
                            static_cast<std::size_t>(b0 & 0x0f) + 1, value2);
    }
    if (image.pixels.size() > targetPixels) {
        image.pixels.resize(targetPixels);
    }
    if (image.pixels.size() != targetPixels) {
        throw std::runtime_error(path + " raw RLE decoded to " +
                                 std::to_string(image.pixels.size()) +
                                 " bytes, expected " + std::to_string(targetPixels));
    }
    return image;
}

}
