#include "resources/palette.hpp"

#include "resources/io.hpp"

#include <regex>
#include <stdexcept>

namespace lezac::resources {
namespace {

uint8_t vga6To8(uint8_t v) {
    return static_cast<uint8_t>((v << 2) | (v >> 4));
}

}

Palette loadPalette(const std::vector<uint8_t>& data, std::size_t off) {
    if (off + 768 > data.size()) {
        throw std::runtime_error("palette data is truncated");
    }
    Palette palette{};
    for (int i = 0; i < 256; ++i) {
        palette[i] = {vga6To8(data[off + i * 3]),
                      vga6To8(data[off + i * 3 + 1]),
                      vga6To8(data[off + i * 3 + 2])};
    }
    return palette;
}

Palette loadPaletteFile(const std::string& path) {
    auto json = readTextFile(path);
    std::regex rgbRe("\"rgb8\"\\s*:\\s*\\[\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\]");
    auto begin = std::sregex_iterator(json.begin(), json.end(), rgbRe);
    auto end = std::sregex_iterator();
    Palette palette{};
    int i = 0;
    for (auto it = begin; it != end && i < 256; ++it, ++i) {
        palette[i] = {
            static_cast<uint8_t>(std::stoi((*it)[1].str())),
            static_cast<uint8_t>(std::stoi((*it)[2].str())),
            static_cast<uint8_t>(std::stoi((*it)[3].str())),
        };
    }
    if (i != 256) {
        throw std::runtime_error(path + " does not contain 256 rgb8 palette entries");
    }
    return palette;
}

}
