#pragma once

#include "resources/types.hpp"

#include <string>

namespace lezac::resources {

IndexedImage loadBackground(const std::string& path, Palette& paletteOut);
IndexedImage loadRawBackground(const std::string& path, Palette& paletteOut);

}
