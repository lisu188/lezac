#include "rendering/game_renderer.hpp"
#include "rendering/presentation_state.hpp"
#include "resources/asset_catalog.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace lezac;
namespace {
void require(bool value, const std::string& message) {
    if (!value) throw std::runtime_error(message);
}
struct Reader {
    std::ifstream stream;
    explicit Reader(const char* path) : stream(path, std::ios::binary) { require(stream.good(), "View oracle is missing"); }
    uint32_t number(unsigned size) {
        uint32_t value = 0;
        for (unsigned i = 0; i < size; ++i) {
            const int byte = stream.get();
            require(byte >= 0, "View oracle is truncated");
            value |= static_cast<uint32_t>(byte) << (8 * i);
        }
        return value;
    }
    std::vector<uint8_t> take(unsigned size) {
        std::vector<uint8_t> value;
        for (unsigned i = 0; i < size; ++i) value.push_back(static_cast<uint8_t>(number(1)));
        return value;
    }
};
uint32_t color(const resources::Palette& palette, uint8_t index) {
    const auto& entry = palette[index];
    return 0xff000000u | (uint32_t{entry.r} << 16) | (uint32_t{entry.g} << 8) | entry.b;
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 2 || argc == 3, "Expected view oracle and optional pixel dump");
        Reader reader(argv[1]);
        require(reader.take(8) == std::vector<uint8_t>({'L','Z','V','I','E','W','0','1'}), "View oracle version differs");
        require(reader.number(4) == 20, "View oracle domain differs");
        const auto assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
        const auto& level = assets.levels().front();
        gameplay::Player first, second;
        first.x = 104; first.y = 168; second.x = 296; second.y = 168;
        const gameplay::State2VisualCursor cursor;
        const gameplay::State2EffectEntry effect;
        const std::vector<gameplay::Bomb> bombs;
        const std::vector<gameplay::ActiveMonster> monsters;
        const std::vector<gameplay::BonusDrop> bonuses;
        const std::vector<gameplay::Flash> flashes;
        const std::vector<gameplay::LaunchPadMarker> markers;
        const std::vector<gameplay::TransientActor> transients;
        const std::vector<gameplay::SharedActorEntry> order;
        const rendering::HudAmmoPanel ammo;
        std::ofstream dump;
        if (argc == 3) {
            dump.open(argv[2], std::ios::binary);
            require(dump.good(), "Cannot create view pixel dump");
            dump.write("LZVGPIX1", 8);
        }
        unsigned compared = 0, differences = 0, ownershipDifferences = 0, activeViews = 0;
        for (unsigned index = 0; index < 20; ++index) {
            const int players = static_cast<int>(reader.number(1));
            const std::array<uint8_t, 2> states{{static_cast<uint8_t>(reader.number(1)), static_cast<uint8_t>(reader.number(1))}};
            require(players == (index < 4 ? 1 : 2), "Original view geometry differs");
            reader.take(60); // Complete original input/output registers, including flags.
            reader.number(4); // Unicorn steps are not DOSBox work-clock credits.
            const std::array<uint32_t, 2> writes{{reader.number(4), reader.number(4)}};
            const auto count = reader.number(1);
            unsigned consumed = 0;
            for (unsigned player = 0; player < 2; ++player) {
                if (!states[player]) continue;
                for (unsigned kind = 0; kind < 3; ++kind) {
                    require(consumed++ < count && reader.number(1) == player && reader.number(1) == kind,
                            "Original camera/draw/present call order differs");
                    const uint16_t returns[2][3] = {{0x7a25, 0x7a2a, 0x7a35}, {0x7a47, 0x7a4c, 0x7a57}};
                    require(reader.number(2) == returns[player][kind], "Original view caller stack return differs");
                }
            }
            require(consumed == count, "Original view call tail differs");
            for (unsigned player = 0; player < 2; ++player) {
                const auto expectedWrites = players == 1 ? (states[0] ? 23712u : 0u) : (states[player] ? 23104u : 0u);
                require(writes[player] == expectedWrites, "Original view write geometry differs");
            }
            const auto initial = reader.take(64000), expected = reader.take(64000);
            for (unsigned phase = 0; phase < 2; ++phase) {
                rendering::PresentationState presentation;
                auto palette = assets.palette();
                rendering::Canvas canvas;
                for (int y = 0; y < 200; ++y) for (int x = 0; x < 320; ++x) {
                    const auto at = static_cast<size_t>(y * 320 + x);
                    canvas.indexedPixel(x, y, initial[at], color(palette, initial[at]));
                }
                if (phase) for (auto& entry : palette) {
                    const auto rotate = [](uint8_t component, unsigned step) {
                        const auto value = static_cast<uint8_t>(((component >> 2) + step) & 63);
                        return static_cast<uint8_t>((value << 2) | (value >> 4));
                    };
                    entry.r = rotate(entry.r, 9);
                    entry.g = rotate(entry.g, 15);
                    entry.b = rotate(entry.b, 21);
                }
                presentation.setPalette(palette);
                presentation.initializeBackdropBuffer(players);
                rendering::TextRenderer text(canvas, presentation.palette(), assets.fontSprites());
                rendering::GameRenderer renderer(canvas, text, assets, presentation);
                rendering::WorldRenderView world{level, 0, players,
                    {{{first, false, 2, cursor, effect, states[0]}, {second, false, 2, cursor, effect, states[1]}}},
                    bombs, monsters, bonuses, flashes, markers, transients, order, 320, true, 0, false, false};
                rendering::HudView hud{players, {{{{}, 0, 2, ammo}, {{}, 0, 2, ammo}}},
                    level.objectiveTile, level.requiredBonus, level.requiredDestruction, 0, 0, false, false};
                renderer.drawGame(world, hud);
                for (int player = 0; player < players; ++player) {
                    const int left = players == 1 ? 0 : player * 160, extent = players == 1 ? 320 : 160;
                    unsigned changed = 0;
                    for (int y = 0; y < 160; ++y) for (int x = left; x < left + extent; ++x) {
                        const auto at = static_cast<size_t>(y * 320 + x);
                        if (states[static_cast<size_t>(player)]) {
                            changed += canvas.pixels()[at] != color(palette, initial[at]);
                        } else {
                            require(expected[at] == initial[at], "Original inactive view was overwritten");
                            ++compared;
                            differences += canvas.pixels()[at] != color(palette, expected[at]);
                            ownershipDifferences += canvas.indexedPixels()[at] != 1 || canvas.paletteIndices()[at] != expected[at];
                        }
                    }
                    if (states[static_cast<size_t>(player)]) {
                        require(changed > 1024, "Nonzero original state did not repaint its active view");
                        ++activeViews;
                    }
                }
                if (dump.is_open() && index == 5) {
                    dump.put(static_cast<char>(index)); dump.put(static_cast<char>(phase));
                    for (const auto& entry : palette) {
                        dump.put(static_cast<char>(entry.r)); dump.put(static_cast<char>(entry.g)); dump.put(static_cast<char>(entry.b));
                    }
                    dump.write(reinterpret_cast<const char*>(expected.data()), static_cast<std::streamsize>(expected.size()));
                    for (auto pixel : canvas.pixels()) {
                        dump.put(static_cast<char>(pixel >> 16)); dump.put(static_cast<char>(pixel >> 8)); dump.put(static_cast<char>(pixel));
                    }
                    dump.write(reinterpret_cast<const char*>(canvas.paletteIndices().data()), 64000);
                    dump.write(reinterpret_cast<const char*>(canvas.indexedPixels().data()), 64000);
                }
            }
        }
        require(reader.stream.get() < 0, "Original view oracle has trailing bytes");
        if (dump.is_open()) { dump.flush(); require(dump.good(), "View pixel dump failed"); }
        std::cout << "render_view_gate=" << (differences || ownershipDifferences ? "failed" : "ok")
                  << " cases=20 retained_pixels=" << compared << " differences=" << differences
                  << " ownership_differences=" << ownershipDifferences << " active_views=" << activeViews << '\n';
        return differences || ownershipDifferences ? 1 : 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
