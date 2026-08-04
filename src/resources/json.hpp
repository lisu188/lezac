#pragma once

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace lezac::resources {

std::array<uint8_t, 4> extractU8Array4(const std::string& json, const std::string& key);
std::vector<std::string> extractStringArray(const std::string& json, const std::string& key);
std::vector<std::string> extractObjectArray(const std::string& json, const std::string& key);
int extractInt(const std::string& json, const std::string& key, int fallback = 0);
std::string extractString(const std::string& json, const std::string& key,
                          const std::string& fallback = "");

}
