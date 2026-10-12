#include "gameplay/actor_models.hpp"

#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

static uint8_t byte(std::istream& input) {
    const int value = input.get();
    if (value == std::char_traits<char>::eof()) throw std::runtime_error("truncated animation input");
    return static_cast<uint8_t>(value);
}

static lezac::gameplay::ActorAnimation animation(std::istream& input) {
    std::array<uint8_t, 7> values{};
    for (auto& value : values) value = byte(input);
    return {values[0], values[1], values[2], values[3], values[4], values[5], static_cast<int8_t>(values[6])};
}

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("expected input and output paths");
        std::ifstream input(argv[1], std::ios::binary);
        std::ofstream output(argv[2], std::ios::binary);
        if (!input || !output) throw std::runtime_error("cannot open probe files");
        std::string magic(8, '\0');
        input.read(magic.data(), 8);
        if (magic != "LZRP0001") throw std::runtime_error("invalid probe magic");
        uint32_t count = 0;
        for (unsigned shift = 0; shift < 32; shift += 8) count |= static_cast<uint32_t>(byte(input)) << shift;
        if (!count || count > 20000) throw std::runtime_error("invalid probe count");
        output.write("LZRA0001", 8);
        for (unsigned shift = 0; shift < 32; shift += 8) output.put(static_cast<char>(count >> shift));
        for (uint32_t index = 0; index < count; ++index) {
            auto active = animation(input);
            const auto backup = animation(input);
            const bool advanced = active.advance(backup);
            for (const auto value : active.packed()) output.put(static_cast<char>(value));
            output.put(static_cast<char>(advanced));
        }
        if (input.peek() != std::char_traits<char>::eof()) throw std::runtime_error("trailing probe bytes");
        output.flush();
        if (!output) throw std::runtime_error("probe output failed");
        std::cout << "reward_animation_helper=ok cases=" << count << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
