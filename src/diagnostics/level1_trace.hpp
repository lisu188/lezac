#pragma once

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <initializer_list>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace lezac::diagnostics::level1 {

struct Event {
    uint32_t tick = 0;
    std::string action;
    std::string key;
};

struct Route {
    uint32_t seed = 0;
    uint32_t ticks = 0;
    uint32_t stepUs = 0;
    std::vector<Event> events;
};

inline uint32_t decimal(const std::string& value, uint32_t maximum) {
    if (value.empty() || value.size() > 10 || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::runtime_error("level1 route: invalid unsigned integer");
    const auto result = std::stoull(value);
    if (result > maximum) throw std::runtime_error("level1 route: integer out of range");
    return static_cast<uint32_t>(result);
}

inline Route readRoute(const std::string& path) {
    if (std::filesystem::file_size(path) > 2 * 1024 * 1024)
        throw std::runtime_error("level1 route: file exceeds 2 MiB");
    std::ifstream input(path);
    if (!input) throw std::runtime_error("level1 route: cannot open input");
    const std::set<std::string> allowed{"1", "2", "return", "escape", "l", "s", "e", "r", "p",
        "z", "x", "m", "n", "c", "left", "right", "up", "down", "insert"};
    Route route;
    std::set<std::string> fields, held;
    bool header = false, complete = false;
    std::string line;
    while (std::getline(input, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;
        if (complete) throw std::runtime_error("level1 route: data after end");
        if (!header) {
            if (line != "LEZAC_LEVEL1_ROUTE_V1") throw std::runtime_error("level1 route: invalid header");
            header = true;
            continue;
        }
        std::istringstream row(line);
        std::vector<std::string> tokens;
        for (std::string token; row >> token;) tokens.push_back(token);
        if (tokens.empty()) throw std::runtime_error("level1 route: whitespace-only record");
        const auto& tag = tokens[0];
        if (tag == "end" && tokens.size() == 1 && fields.size() == 3) {
            complete = true;
        } else if (tag == "event" && tokens.size() == 4 && fields.size() == 3) {
            Event event{decimal(tokens[1], route.ticks - 1), tokens[2], tokens[3]};
            if (allowed.count(event.key) == 0 || route.events.size() >= 100000 ||
                (!route.events.empty() && event.tick < route.events.back().tick))
                throw std::runtime_error("level1 route: invalid key or event order");
            if (event.action == "down") {
                if (!held.insert(event.key).second) throw std::runtime_error("level1 route: duplicate key down");
            } else if (event.action == "up") {
                if (held.erase(event.key) != 1) throw std::runtime_error("level1 route: key up without down");
            } else if (event.action == "repeat") {
                if (held.count(event.key) == 0) throw std::runtime_error("level1 route: repeat without down");
            } else throw std::runtime_error("level1 route: invalid event action");
            route.events.push_back(std::move(event));
        } else if (tokens.size() == 2 && route.events.empty() &&
                   (tag == "seed" || tag == "ticks" || tag == "step_us")) {
            if (!fields.insert(tag).second) throw std::runtime_error("level1 route: duplicate setting");
            if (tag == "seed") route.seed = decimal(tokens[1], UINT32_MAX);
            if (tag == "ticks") route.ticks = decimal(tokens[1], 20000);
            if (tag == "step_us") route.stepUs = decimal(tokens[1], 1000000);
            if ((tag == "ticks" && route.ticks == 0) || (tag == "step_us" && route.stepUs < 1000))
                throw std::runtime_error("level1 route: zero ticks or unsupported step");
        } else throw std::runtime_error("level1 route: unexpected record");
    }
    if (!input.eof() || !complete || route.events.empty()) throw std::runtime_error("level1 route: incomplete input");
    return route;
}

inline std::string quote(const std::string& value) {
    std::ostringstream out;
    out << '"';
    for (const unsigned char c : value) {
        if (c == '"' || c == '\\') out << '\\' << c;
        else if (c < 32) out << "\\u00" << std::hex << std::setw(2) << std::setfill('0') << int(c) << std::dec;
        else out << c;
    }
    return out.str() + '"';
}

using Fields = std::map<std::string, std::string>;

inline std::string object(const Fields& fields) {
    std::string result = "{";
    for (const auto& field : fields) {
        if (result.size() != 1) result += ',';
        result += quote(field.first) + ':' + field.second;
    }
    return result + '}';
}

inline std::string array(const std::vector<std::string>& values) {
    std::string result = "[";
    for (const auto& value : values) {
        if (result.size() != 1) result += ',';
        result += value;
    }
    return result + ']';
}

inline std::string numbers(std::initializer_list<int64_t> values) {
    std::vector<std::string> fields;
    for (auto value : values) fields.push_back(std::to_string(value));
    return array(fields);
}

inline std::string hexBytes(const std::vector<uint8_t>& bytes) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string result;
    result.reserve(bytes.size() * 2);
    for (auto value : bytes) {
        result += digits[value >> 4];
        result += digits[value & 15];
    }
    return result;
}

inline std::string fingerprint(const std::vector<uint8_t>& bytes) {
    uint64_t value = UINT64_C(14695981039346656037);
    for (auto byte : bytes) value = (value ^ byte) * UINT64_C(1099511628211);
    std::ostringstream out;
    out << std::hex << std::setw(16) << std::setfill('0') << value;
    return out.str();
}

inline std::string frameName(uint32_t tick) {
    std::ostringstream out;
    out << "frame_" << std::setw(6) << std::setfill('0') << tick << ".ppm";
    return out.str();
}

}
