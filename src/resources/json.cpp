#include "resources/json.hpp"

#include <regex>

namespace lezac::resources {

std::array<uint8_t, 4> extractU8Array4(const std::string& json, const std::string& key) {
    std::array<uint8_t, 4> out{};
    std::regex re("\"" + key + "\"\\s*:\\s*\\[([^\\]]*)\\]");
    std::smatch m;
    if (!std::regex_search(json, m, re)) return out;
    std::regex intRe("(\\d+)");
    int i = 0;
    std::string body = m[1].str();
    for (auto it = std::sregex_iterator(body.begin(), body.end(), intRe);
         it != std::sregex_iterator() && i < 4; ++it, ++i) {
        out[static_cast<std::size_t>(i)] = static_cast<uint8_t>(std::stoi((*it)[1].str()));
    }
    return out;
}

std::vector<std::string> extractStringArray(const std::string& json, const std::string& key) {
    std::vector<std::string> rows;
    std::string needle = "\"" + key + "\"";
    size_t keyPos = json.find(needle);
    if (keyPos == std::string::npos) return rows;
    size_t open = json.find('[', keyPos);
    if (open == std::string::npos) return rows;
    size_t depth = 1;
    for (size_t i = open + 1; i < json.size() && depth > 0; ++i) {
        char ch = json[i];
        if (ch == '[') {
            ++depth;
        } else if (ch == ']') {
            --depth;
        } else if (ch == '"') {
            size_t end = json.find('"', i + 1);
            if (end == std::string::npos) break;
            rows.push_back(json.substr(i + 1, end - i - 1));
            i = end;
        }
    }
    return rows;
}

std::vector<std::string> extractObjectArray(const std::string& json, const std::string& key) {
    std::vector<std::string> objects;
    std::string needle = "\"" + key + "\"";
    size_t keyPos = json.find(needle);
    if (keyPos == std::string::npos) return objects;
    size_t open = json.find('[', keyPos);
    if (open == std::string::npos) return objects;
    size_t depth = 1;
    for (size_t i = open + 1; i < json.size() && depth > 0; ++i) {
        if (json[i] == '[') {
            ++depth;
        } else if (json[i] == ']') {
            --depth;
        } else if (depth == 1 && json[i] == '{') {
            size_t objStart = i;
            size_t objDepth = 1;
            for (++i; i < json.size() && objDepth > 0; ++i) {
                if (json[i] == '{') ++objDepth;
                else if (json[i] == '}') --objDepth;
            }
            if (objDepth == 0) {
                objects.push_back(json.substr(objStart, i - objStart));
            }
            --i;
        }
    }
    return objects;
}

int extractInt(const std::string& json, const std::string& key, int fallback) {
    std::regex re("\"" + key + "\"\\s*:\\s*(-?\\d+)");
    std::smatch m;
    if (std::regex_search(json, m, re)) {
        return std::stoi(m[1].str());
    }
    return fallback;
}

std::string extractString(const std::string& json, const std::string& key,
                          const std::string& fallback) {
    std::regex re("\"" + key + "\"\\s*:\\s*\"([^\"]*)\"");
    std::smatch m;
    if (std::regex_search(json, m, re)) {
        return m[1].str();
    }
    return fallback;
}

}
