#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace lezac::resources {

std::vector<uint8_t> readFile(const std::string& path);
std::string readTextFile(const std::string& path);
std::vector<uint8_t> parseHexByteList(const std::string& hexList);
std::vector<uint16_t> parseHexWordList(const std::string& hexList);

}
