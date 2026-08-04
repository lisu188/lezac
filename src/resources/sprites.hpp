#pragma once

#include "resources/types.hpp"

#include <string>

namespace lezac::resources {

SpriteBank loadSprites(const std::string& path);
SpriteBank loadRawSprites(const std::string& path);

}
