#pragma once

#include <array>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace lezac::diagnostics {

struct SurvivorViewportStage {
    uint8_t remaining = 0;
    std::array<uint8_t, 2> states{}, reserves{};
    std::array<uint16_t, 7> geometry{};
    std::array<uint8_t, 16> visuals{};
    std::vector<uint8_t> pixels, backdrop;
};
struct SurvivorViewportProfile {
    uint8_t lost = 0, reserve = 0;
    uint16_t target = 0;
    std::array<SurvivorViewportStage, 10> stages;
};
struct SurvivorViewportFixture {
    std::vector<uint8_t> map, backdrop, descriptors;
    std::array<SurvivorViewportProfile, 8> profiles;
};

inline SurvivorViewportFixture readSurvivorViewportFixture(const std::string& path) {
    std::ifstream input(path, std::ios::binary);
    const auto require = [](bool valid, const char* reason) {
        if (!valid) throw std::runtime_error(reason);
    };
    require(input.good(), "Survivor viewport fixture missing");
    const auto number = [&](unsigned size) {
        uint32_t value = 0;
        for (unsigned index = 0; index < size; ++index) {
            const int byte = input.get();
            require(byte >= 0, "Survivor viewport fixture truncated");
            value |= static_cast<uint32_t>(byte) << (index * 8);
        }
        return value;
    };
    const auto take = [&](size_t size) {
        std::vector<uint8_t> bytes(size);
        input.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(size));
        require(input.good(), "Survivor viewport payload truncated");
        return bytes;
    };
    require(take(8) == std::vector<uint8_t>({'L','Z','S','U','R','V','0','1'}), "Survivor viewport version differs");
    require(number(4) == 8 && number(4) == 10 && number(2) == 60 && number(2) == 33,
            "Survivor viewport domain differs");
    SurvivorViewportFixture result;
    result.map = take(1980);
    result.backdrop = take(60000);
    result.descriptors = take(368);
    for (size_t index = 0; index < result.profiles.size(); ++index) {
        auto& profile = result.profiles[index];
        profile.lost = static_cast<uint8_t>(number(1));
        profile.reserve = static_cast<uint8_t>(number(1));
        profile.target = static_cast<uint16_t>(number(2));
        require(static_cast<size_t>(profile.lost) == (index < 6 ? index / 3 + 1 : index - 5) &&
                profile.reserve == (index < 6 ? 0 : 1) &&
                profile.target == (index < 6 ? std::array<uint16_t, 3>{{168, 240, 320}}[index % 3] : 168),
                "Survivor viewport profile differs");
        for (size_t phase = 0; phase < profile.stages.size(); ++phase) {
            auto& stage = profile.stages[phase];
            require(number(1) == phase, "Survivor viewport phase differs");
            stage.remaining = static_cast<uint8_t>(number(1));
            for (auto& value : stage.states) value = static_cast<uint8_t>(number(1));
            for (auto& value : stage.reserves) value = static_cast<uint8_t>(number(1));
            for (auto& value : stage.geometry) value = static_cast<uint16_t>(number(2));
            for (auto& value : stage.visuals) value = static_cast<uint8_t>(number(1));
            require(stage.remaining == (profile.reserve == 0 && phase >= 2 ? 1 : 2),
                    "Survivor viewport remaining-player count differs");
            stage.pixels = take(64000);
            if (phase == 8) stage.backdrop = take(60000);
        }
    }
    require(input.get() < 0, "Survivor viewport fixture has trailing bytes");
    return result;
}

inline uint16_t survivorVisualWord(const SurvivorViewportStage& stage, size_t player, size_t field) {
    const size_t at = player * 8 + field;
    return static_cast<uint16_t>(stage.visuals.at(at) | (uint16_t{stage.visuals.at(at + 1)} << 8));
}

inline uint8_t survivorSpriteIndex(const SurvivorViewportFixture& fixture,
                                  const SurvivorViewportStage& stage, size_t player) {
    for (size_t sprite = 0; sprite < 91; ++sprite) {
        bool matches = true;
        for (size_t field = 0; field < 4; ++field)
            matches &= fixture.descriptors[(sprite + 1) * 4 + field] == stage.visuals[player * 8 + 4 + field];
        if (matches) return static_cast<uint8_t>(sprite);
    }
    throw std::runtime_error("Survivor viewport visual descriptor differs");
}

}
