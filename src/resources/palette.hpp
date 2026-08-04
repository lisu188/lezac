#pragma once

#include "resources/types.hpp"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace lezac::resources {

uint8_t vga6To8(uint8_t v) noexcept;
Palette loadPalette(const std::vector<uint8_t>& data, std::size_t off);
Palette loadPaletteFile(const std::string& path);

}
