#include "rendering/game_renderer.hpp"
#include "rendering/presentation_state.hpp"
#include "resources/asset_catalog.hpp"
#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace lezac;
namespace {
void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

struct Reader {
    std::ifstream stream;
    explicit Reader(const char* path) : stream(path, std::ios::binary) {
        require(stream.good(), "Original HUD oracle is missing");
    }
    uint32_t number(unsigned size) {
        uint32_t result = 0;
        for (unsigned i = 0; i < size; ++i) {
            const int value = stream.get();
            require(value >= 0, "Original HUD oracle is truncated");
            result |= static_cast<uint32_t>(value) << (8 * i);
        }
        return result;
    }
    std::vector<uint8_t> take(unsigned size) {
        std::vector<uint8_t> result;
        for (unsigned i = 0; i < size; ++i) result.push_back(static_cast<uint8_t>(number(1)));
        return result;
    }
};

uint8_t byte(const std::vector<uint8_t>& hud, unsigned address) {
    return hud.at(address < 0x79b3 ? address - 0x206e : 30 + address - 0x79b3);
}
uint16_t word(const std::vector<uint8_t>& hud, unsigned address) {
    return static_cast<uint16_t>(byte(hud, address) | (uint16_t{byte(hud, address + 1)} << 8));
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 2 || argc == 3, "Expected oracle path and optional pixel dump path");
        Reader reader(argv[1]);
        require(reader.take(8) == std::vector<uint8_t>({'L','Z','H','U','D','O','R','1'}), "Original HUD oracle version differs");
        require(reader.number(4) == 17, "Original HUD oracle case count differs");
        const auto assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
        std::ofstream dump;
        if (argc == 3) {
            dump.open(argv[2], std::ios::binary);
            require(dump.good(), "Cannot open production HUD pixel dump");
            dump.write("LZHAPP01", 8);
        }
        unsigned cases = 0, draws = 0, compared = 0, differences = 0, flagDifferences = 0;
        for (unsigned index = 0; index < 17; ++index) {
            const bool error = reader.number(1) != 0;
            const auto registers = reader.take(30);
            reader.take(128);
            const auto input = reader.take(86), font = reader.take(640);
            reader.take(272 + 30 + 128);
            const auto expected = reader.take(86), pixels = reader.take(272);
            // DF=1 and the original fatal-error path are not App renderer inputs.
            if (error || (registers[27] & 4) != 0) continue;
            ++cases;
            for (unsigned digit = 0; digit < 10; ++digit) {
                const auto* tile = assets.tiles().tile(121 + digit);
                require(tile && std::equal(tile, tile + 64, font.begin() + digit * 64),
                        "App digit atlas differs from the captured original font");
            }
            for (int players : {1, 2}) for (int bias : {0, 1, -1}) {
                rendering::PresentationState presentation;
                presentation.setPalette(assets.palette());
                auto state = presentation.snapshot();
                state.hudPreviousCollected = word(input, 0x208a);
                state.hudPreviousDestruction = byte(input, 0x79b6);
                state.hudDestructionPercent = byte(input, 0x79b5);
                state.hudBonusComplete = byte(input, 0x79c5) != 0;
                state.hudDestructionComplete = byte(input, 0x79c6) != 0;
                presentation.restore(state);
                const auto required = word(input, 0x2086), collected = word(input, 0x2088);
                const auto destructionRequired = byte(input, 0x79b3), destruction = byte(input, 0x79b5);
                presentation.prepareHudObjectives(1, int{collected} + bias * 65536, int{destruction} + bias * 256 + 1,
                    int{required} + bias * 65536, int{destructionRequired} + bias * 256);
                flagDifferences += presentation.hudBonusComplete() != (byte(expected, 0x79c5) != 0);
                flagDifferences += presentation.hudDestructionComplete() != (byte(expected, 0x79c6) != 0);
                require(presentation.hudPreviousCollected() == word(expected, 0x208a) &&
                        presentation.hudPreviousDestruction() == byte(expected, 0x79b6),
                        "App objective dirty caches differ from original endpoints");
                rendering::PresentationState sampled;
                sampled.restore(state);
                sampled.prepareHudObjectives(30, int{collected} + bias * 65536, int{destruction} + bias * 256,
                    int{required} + bias * 65536, int{destructionRequired} + bias * 256);
                require(sampled.hudDestructionPercent() == destruction &&
                        sampled.hudPreviousCollected() == word(expected, 0x208a) &&
                        sampled.hudPreviousDestruction() == byte(expected, 0x79b6) &&
                        sampled.hudBonusComplete() == (byte(expected, 0x79c5) != 0) &&
                        sampled.hudDestructionComplete() == (byte(expected, 0x79c6) != 0),
                        "App modulo-30 objective sampling differs from original endpoints");
                rendering::Canvas canvas;
                rendering::TextRenderer text(canvas, presentation.palette(), assets.fontSprites());
                rendering::GameRenderer renderer(canvas, text, assets, presentation);
                const rendering::HudAmmoPanel ammo;
                rendering::HudView view{players, {{{{}, 0, 0, ammo}, {{}, 0, 0, ammo}}},
                    108, required, destructionRequired, int{collected} + bias * 65536,
                    int{destruction} + bias * 256, false, false};
                renderer.drawHud(view);
                for (unsigned block = 0; block < 2; ++block) {
                    const bool dirty = block == 0 ? collected != word(input, 0x208a) : destruction != byte(input, 0x79b6);
                    if (!dirty) continue;
                    for (unsigned row = 0; row < 8; ++row) for (unsigned x = 0; x < 17; ++x) {
                        // The full panel repaints the gutter; the original glyph call does not.
                        if (x == 8) continue;
                        const auto offset = (166 + block * 16 + row) * 320 + 159 + x;
                        ++compared;
                        differences += canvas.indexedPixels()[offset] != 1 ||
                                       canvas.paletteIndices()[offset] != pixels[block * 136 + row * 17 + x];
                    }
                }
                if (dump.is_open() && bias == 0) {
                    dump.put(static_cast<char>(index));
                    dump.put(static_cast<char>(players));
                    for (const auto& color : presentation.palette()) {
                        dump.put(static_cast<char>(color.r)); dump.put(static_cast<char>(color.g)); dump.put(static_cast<char>(color.b));
                    }
                    dump.write(reinterpret_cast<const char*>(pixels.data()), static_cast<std::streamsize>(pixels.size()));
                    for (unsigned block = 0; block < 2; ++block) for (unsigned row = 0; row < 8; ++row) for (unsigned x = 0; x < 17; ++x) {
                        const auto color = canvas.pixels()[(166 + block * 16 + row) * 320 + 159 + x];
                        dump.put(static_cast<char>(color >> 16)); dump.put(static_cast<char>(color >> 8)); dump.put(static_cast<char>(color));
                    }
                }
                ++draws;
            }
        }
        require(reader.stream.get() < 0, "Original HUD oracle has unexpected trailing bytes");
        if (dump.is_open()) {
            dump.flush();
            require(dump.good(), "Production HUD pixel dump failed");
        }
        std::cout << "hud_objective_original=" << (differences || flagDifferences ? "failed" : "ok")
                  << " cases=" << cases << " draws=" << draws << " indexed_pixels=" << compared
                  << " differences=" << differences << " flag_differences=" << flagDifferences << '\n';
        return differences || flagDifferences ? 1 : 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
