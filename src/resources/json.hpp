#pragma once

#include <string>
#include <vector>

namespace lezac::resources {

std::vector<std::string> extractStringArray(const std::string& json, const std::string& key);
std::vector<std::string> extractObjectArray(const std::string& json, const std::string& key);
int extractInt(const std::string& json, const std::string& key, int fallback = 0);
std::string extractString(const std::string& json, const std::string& key,
                          const std::string& fallback = "");

}
