#include "rendering/game_renderer.hpp"
#include "rendering/presentation_state.hpp"
#include "rendering/world_camera.hpp"
#include "resources/asset_catalog.hpp"
#include "ui/ui_controller.hpp"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace lezac;
namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
struct Reader {
    std::ifstream stream;
    explicit Reader(const char* path) : stream(path, std::ios::binary) { require(stream.good(), "Width oracle missing"); }
    uint32_t number(unsigned size) {
        uint32_t value = 0;
        for (unsigned i = 0; i < size; ++i) {
            const int byte = stream.get();
            require(byte >= 0, "Width oracle truncated");
            value |= static_cast<uint32_t>(byte) << (8 * i);
        }
        return value;
    }
    std::vector<uint8_t> take(unsigned size) {
        std::vector<uint8_t> result;
        result.reserve(size);
        for (unsigned i = 0; i < size; ++i) result.push_back(static_cast<uint8_t>(number(1)));
        return result;
    }
};
uint32_t color(const resources::Palette& palette, uint8_t index) {
    const auto& value = palette[index];
    return 0xff000000u | (uint32_t{value.r} << 16) | (uint32_t{value.g} << 8) | value.b;
}
void rgb(std::ostream& stream, uint32_t pixel) {
    stream.put(static_cast<char>(pixel >> 16));
    stream.put(static_cast<char>(pixel >> 8));
    stream.put(static_cast<char>(pixel));
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 2 || argc == 3, "Expected width oracle and optional pixel dump");
        Reader reader(argv[1]);
        require(reader.take(8) == std::vector<uint8_t>({'L','Z','W','I','D','T','H','1'}), "Width oracle version differs");
        require(reader.number(4) == 44 && reader.number(4) == 60, "Width oracle domain differs");
        require(reader.number(2) == 60 && reader.number(2) == 33, "Width oracle map dimensions differ");
        const auto spriteWidth = reader.number(1), spriteHeight = reader.number(1);
        const auto map = reader.take(1980), backdrop = reader.take(60000), descriptors = reader.take(368);
        const auto sprite = reader.take(spriteWidth * spriteHeight);
        const auto assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
        require(spriteWidth == static_cast<unsigned>(assets.sprites().sprites.front().width) &&
                spriteHeight == static_cast<unsigned>(assets.sprites().sprites.front().height) &&
                sprite == assets.sprites().sprites.front().pixels, "Original width sprite backing differs");
        require(descriptors[4] == spriteWidth && descriptors[5] == spriteHeight, "Original width descriptor differs");
        unsigned controlDifferences = 0, controlPixels = 0, controlPixelDifferences = 0;
        for (unsigned index = 0; index < 44; ++index) {
            int width = static_cast<int>(reader.number(2));
            const auto key = reader.number(1);
            const int players = static_cast<int>(reader.number(1));
            std::array<uint32_t, 7> fields{};
            for (auto& field : fields) field = reader.number(2);
            const auto consumed = reader.number(1);
            reader.number(4); // Unicorn instructions are not DOSBox work-clock credits.
            const auto expected = reader.take(64000);
            const bool changed = fields[1] != static_cast<unsigned>(width);
            require(fields[0] * 8 == fields[1] && fields[2] == 320 - fields[1] &&
                    fields[3] == (328 - fields[1]) / 2 && fields[4] == fields[2] &&
                    fields[5] == ((fields[0] - 2) / 2) * 8 && fields[6] == fields[0] &&
                    consumed == (changed ? static_cast<unsigned>('9') : key), "Original width control fields differ");
            rendering::Canvas canvas;
            rendering::PresentationState presentation;
            presentation.setPalette(assets.palette());
            canvas.indexedRect(0, 0, 320, 200, 0x4f, color(assets.palette(), 0x4f));
            rendering::TextRenderer text(canvas, presentation.palette(), assets.fontSprites());
            rendering::GameRenderer renderer(canvas, text, assets, presentation);
            ui::UiController controller;
            controller.setMenu(false);
            ui::RecordStore records;
            ui::UiActions actions;
            actions.adjustViewWidth = [&](int delta) {
                const int next = std::clamp(width + delta, 168, 320);
                if (next == width) return;
                width = next;
                renderer.resizePlayfield(width);
            };
            bool running = true;
            controller.onKey(key == 'e' ? ui::Key::E : key == 'r' ? ui::Key::R : ui::Key::Unknown,
                             running, 0, players, records, actions);
            controlDifferences += static_cast<unsigned>(width) != fields[1];
            for (size_t at = 0; at < expected.size(); ++at) {
                ++controlPixels;
                controlPixelDifferences += canvas.pixels()[at] != color(assets.palette(), expected[at]);
            }
        }
        auto level = assets.levels().front();
        level.tiles = map;
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
            require(dump.good(), "Cannot create width pixel dump");
            dump.write("LZWPIX01", 8);
        }
        unsigned viewPixels = 0, viewDifferences = 0;
        for (unsigned index = 0; index < 60; ++index) {
            const int width = static_cast<int>(reader.number(2));
            gameplay::Player first, second;
            first.x = static_cast<float>(reader.number(2));
            first.y = static_cast<float>(reader.number(2));
            const auto shake = static_cast<uint16_t>(reader.number(1));
            const bool background = reader.number(1) != 0;
            std::array<uint32_t, 9> fields{};
            for (auto& field : fields) field = reader.number(2);
            reader.number(4);
            const auto camera=rendering::cameraForViewport(static_cast<int>(first.x),
                static_cast<int>(first.y),level.width,level.height,width,shake);
            require(camera.coarseX==fields[0] && camera.coarseY==fields[1] &&
                    camera.fineX==fields[2] && camera.fineY==fields[3] && camera.mapOffset==fields[4],
                    "Live viewport camera differs from original context");
            require(width == 168 + static_cast<int>(index / 3) * 8 && fields[5] == static_cast<unsigned>(width) &&
                    fields[6] == 320 && fields[7] == static_cast<unsigned>(320 - width) &&
                    fields[8] == static_cast<unsigned>(1280 + (328 - width) / 2), "Original width presentation geometry differs");
            const auto expected = reader.take(64000);
            rendering::Canvas canvas;
            rendering::PresentationState presentation;
            presentation.setPalette(assets.palette());
            presentation.initializeBackdropBuffer(1);
            presentation.restoreBackdrop(backdrop);
            rendering::TextRenderer text(canvas, presentation.palette(), assets.fontSprites());
            rendering::GameRenderer renderer(canvas, text, assets, presentation);
            renderer.initializePlayfield(1, width);
            rendering::WorldRenderView world{level, 0, 1,
                {{{first, false, 2, cursor, effect, 1}, {second, false, 2, cursor, effect, 0}}},
                bombs, monsters, bonuses, flashes, markers, transients, order, width, background, shake, false, false};
            rendering::HudView hud{1, {{{{}, 0, 2, ammo}, {{}, 0, 2, ammo}}},
                level.objectiveTile, level.requiredBonus, level.requiredDestruction, 0, 0, false, false};
            renderer.drawGame(world, hud);
            for (size_t at = 0; at < 51200; ++at) {
                ++viewPixels;
                viewDifferences += canvas.pixels()[at] != presentation.backdropColor(expected[at]);
            }
            if (dump.is_open() && (index == 1 || index == 55)) {
                dump.put(static_cast<char>(index));
                dump.put(static_cast<char>(width));
                dump.put(static_cast<char>(width >> 8));
                for (size_t at = 0; at < 51200; ++at) rgb(dump, presentation.backdropColor(expected[at]));
                for (size_t at = 0; at < 51200; ++at) rgb(dump, canvas.pixels()[at]);
            }
        }
        require(reader.stream.get() < 0, "Width oracle has trailing bytes");
        if (dump.is_open()) { dump.flush(); require(dump.good(), "Width pixel dump failed"); }
        const bool passed = controlDifferences == 0 && controlPixelDifferences == 0 && viewDifferences == 0;
        std::cout << "viewport_width=" << (passed ? "ok" : "failed") << " controls=44 views=60 widths=20"
                  << " control_differences=" << controlDifferences << " control_pixels=" << controlPixels
                  << " control_pixel_differences=" << controlPixelDifferences << " view_pixels=" << viewPixels
                  << " view_differences=" << viewDifferences << " native_app_claim=0 whole_game_claim=0\n";
        return passed ? 0 : 1;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
