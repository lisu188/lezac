#pragma once

#include "resources/types.hpp"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace lezac::resources {

Palette loadPalette(const std::vector<uint8_t>& data, std::size_t off);
Palette loadPaletteFile(const std::string& path);

}
