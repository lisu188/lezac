#pragma once

#include "resources/types.hpp"

#include <string>

namespace lezac::resources {

TileBank loadTiles(const std::string& path);
TileBank loadRawTiles(const std::string& path);

}
