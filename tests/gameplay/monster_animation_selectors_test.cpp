#include "gameplay/actor_models.hpp"

#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <vector>

namespace {

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

std::vector<uint8_t> readPinned(const std::filesystem::path& path, uint64_t expected) {
    std::ifstream stream(path, std::ios::binary);
    require(stream.is_open(), "fixture open failed");
    std::vector<uint8_t> bytes{std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
    require(!stream.bad(), "fixture read failed");
    uint64_t fingerprint = 14695981039346656037ull;
    for (uint8_t value : bytes) fingerprint = (fingerprint ^ value) * 1099511628211ull;
    require(fingerprint == expected, "fixture fingerprint mismatch");
    return bytes;
}

} // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2, "expected repository path");
        const std::filesystem::path root(argv[1]);
        const auto original = readPinned(root / "LEZAC.EXE", 0x2ae32f89b95e200bull);
        const auto fixture = readPinned(root / "tests/fixtures/shipped_monster_profiles_original.bin",
                                        0xbe9d74b942656b0bull);
        constexpr size_t data = 0x770 + 0xaa20;
        constexpr size_t prefix = 64 + 368 + 1980;
        constexpr size_t stateSize = 112;
        constexpr size_t caseSize = 18 + 30 + 130 * stateSize;
        require(original.size() > data + 0x89, "original table extent");
        require(fixture.size() == prefix + 45 * caseSize, "native fixture extent");
        int states = 0, ranges = 0;
        for (size_t index = 0; index < 45; ++index) {
            const size_t at = prefix + index * caseSize;
            const size_t constructed = at + 48 + stateSize;
            const uint8_t kind = fixture[at + 18 + 11];
            require(kind >= 1 && kind <= 4, "unobserved shipped kind");
            lezac::gameplay::ActiveMonster monster;
            monster.kind = kind;
            const auto selectors = lezac::gameplay::monsterAnimationSelectors(kind);
            monster.animationSetLeft = selectors[0];
            monster.animationSetRight = selectors[1];
            require(selectors[0] == original[data + 0x80 + 2 * kind] &&
                    selectors[1] == original[data + 0x81 + 2 * kind], "constructor selector table");
            for (size_t state = 0; state < 129; ++state) {
                const size_t raw = constructed + state * stateSize + 6;
                require(monster.kind == fixture[raw], "native kind");
                require(monster.animationSetLeft == fixture[raw + 3] &&
                        monster.animationSetRight == fixture[raw + 4], "native selector bytes");
                ++states;
                for (int16_t velocity : {int16_t{-1}, int16_t{0}, int16_t{1}}) {
                    monster.vx8 = velocity;
                    const auto range = lezac::gameplay::monsterFacingFrameRange(monster);
                    const uint8_t selector = fixture[raw + (velocity > 0 ? 4 : 3)];
                    require(range[0] + 1 == original[data + 0x58 + 2 * selector] &&
                            range[1] + 1 == original[data + 0x59 + 2 * selector], "native range table");
                    ++ranges;
                }
            }
        }
        lezac::gameplay::ActiveMonster override;
        override.kind = 1;
        override.animationSetLeft = 13;
        override.animationSetRight = 12;
        override.vx8 = -1;
        require(lezac::gameplay::monsterFacingFrameRange(override) == std::array<int, 2>{53, 55},
                "stored left selector must override kind");
        override.vx8 = 1;
        require(lezac::gameplay::monsterFacingFrameRange(override) == std::array<int, 2>{49, 51},
                "stored right selector must override kind");
        int fallback = 0;
        for (uint8_t kind : {uint8_t{0}, uint8_t{1}, uint8_t{2}, uint8_t{3}, uint8_t{4}}) {
            for (int16_t velocity : {int16_t{-1}, int16_t{0}, int16_t{1}}) {
                lezac::gameplay::ActiveMonster seeded;
                seeded.kind = kind;
                seeded.vx8 = velocity;
                const auto selectors = lezac::gameplay::monsterAnimationSelectors(kind);
                require(lezac::gameplay::monsterFacingFrameRange(seeded) ==
                        lezac::gameplay::monsterAnimationSetRange(selectors[velocity > 0 ? 1 : 0]),
                        "legacy diagnostic fallback");
                ++fallback;
            }
        }
        std::cout << "monster_animation_selectors=ok constructors=45 states=" << states
                  << " ranges=" << ranges << " overrides=2 fallback=" << fallback
                  << " compiled_helper=1 full_game_claim=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "monster_animation_selectors failed: " << error.what() << '\n';
        return 1;
    }
}
