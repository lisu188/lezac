#include "rendering/game_renderer.hpp"
#include "rendering/presentation_state.hpp"
#include "gameplay/map_plane_memory.hpp"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <stdexcept>

using namespace lezac;
namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
uint32_t number(std::istream& stream, unsigned bytes) {
    uint32_t value = 0;
    for (unsigned i = 0; i < bytes; ++i) {
        const int byte = stream.get();
        require(byte >= 0,"Standalone camera fixture truncated");
        value |= static_cast<uint32_t>(byte) << (8*i);
    }
    return value;
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 2 || argc == 3,"Expected standalone camera oracle and optional pixel dump");
        std::ifstream input(argv[1],std::ios::binary);
        require(input.good(),"Standalone camera oracle missing");
        std::string magic(8,' ');
        input.read(magic.data(),8);
        require(magic == "LZSVIEW1" && number(input,4) == 24,"Standalone camera fixture version differs");
        const auto assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
        auto level = assets.levels().front();
        level.width = 60; level.height = 33;
        level.tiles.assign(1980,0); level.wordLayer.assign(1980,0);
        gameplay::MapPlaneMemory map;
        map.beginLevel({}, {}, level.tiles.size());
        gameplay::ActorStorage slots;
        slots.resetForLevel({16,16,0,0});
        gameplay::Player first, second;
        first.x = 104; first.y = 168;
        second.x = 136; second.y = 168; second.spriteIndex = 1;
        const gameplay::State2VisualCursor cursor;
        const gameplay::State2EffectEntry effect;
        const std::vector<gameplay::Bomb> bombs;
        const std::vector<gameplay::ActiveMonster> monsters;
        const std::vector<gameplay::BonusDrop> bonuses;
        const std::vector<gameplay::Flash> flashes;
        const std::vector<gameplay::LaunchPadMarker> markers;
        const std::vector<gameplay::TransientActor> transients;
        const std::vector<gameplay::SharedActorEntry> order;
        const auto before = slots.state();
        std::ofstream dump;
        if (argc == 3) {
            dump.open(argv[2],std::ios::binary);
            require(dump.good(),"Cannot create standalone camera pixel dump");
            dump.write("LZSVPIX1",8);
        }
        uint64_t differences = 0;
        for (unsigned index = 0; index < 24; ++index) {
            const int x = static_cast<int>(number(input,2)), y = static_cast<int>(number(input,2));
            const int width = static_cast<int>(number(input,2)), height = static_cast<int>(number(input,2));
            const bool background = number(input,1) != 0;
            const unsigned mode = number(input,1);
            gameplay::Player independent = second;
            independent.x = static_cast<float>(number(input,2));
            independent.y = static_cast<float>(number(input,2));
            require(mode == index%4 && background == (index>=12) && height == 152,
                "Standalone camera fixture domain differs");
            const gameplay::Player* camera = mode == 0 ? &first : mode == 1 ? &second : &independent;
            require(camera->x == independent.x && camera->y == independent.y,"Independent camera arguments differ");
            rendering::Canvas canvas;
            rendering::PresentationState presentation;
            presentation.setPalette(assets.palette());
            presentation.initializeBackdropBuffer(1);
            presentation.restoreBackdrop(std::vector<uint8_t>(60000,17));
            for (size_t at = 0; at < 64000; ++at) {
                const auto value = static_cast<uint8_t>(at*11+(at>>8)*7+index);
                canvas.indexedPixel(static_cast<int>(at%320),static_cast<int>(at/320),value,presentation.backdropColor(value));
            }
            rendering::TextRenderer text(canvas,presentation.palette(),assets.fontSprites());
            rendering::GameRenderer renderer(canvas,text,assets,presentation);
            const rendering::WorldRenderView world{level,0,2,
                {{{first,false,2,cursor,effect,1},{second,false,2,cursor,effect,1}}},
                bombs,monsters,bonuses,flashes,markers,transients,order,320,background,0,false,false,
                nullptr,&map,&slots.state()};
            renderer.drawWorldView(world,*camera,x,y,width,height);
            const auto& work = renderer.lastCompletedWorldRasterWork();
            require(work.physicalVisuals && work.dispatchedInstructions > 0 && work.transferredWords > 0,
                "Standalone camera bypassed live production raster");
            require(first.x == 104 && first.y == 168 && second.x == 136 && second.y == 168 &&
                slots.state().actors == before.actors && slots.state().visuals == before.visuals,
                "Standalone camera mutated live visual owners");
            std::vector<uint8_t> expected(64000);
            input.read(reinterpret_cast<char*>(expected.data()),64000);
            require(input.gcount() == 64000,"Standalone camera pixels truncated");
            for (size_t at = 0; at < expected.size(); ++at)
                differences += canvas.paletteIndices()[at] != expected[at];
            if (dump.is_open()) {
                dump.write(reinterpret_cast<const char*>(expected.data()),64000);
                dump.write(reinterpret_cast<const char*>(canvas.paletteIndices().data()),64000);
            }
        }
        require(input.get() < 0,"Standalone camera fixture has trailing bytes");
        if (dump.is_open()) { dump.flush(); require(dump.good(),"Standalone camera pixel dump failed"); }
        std::cout << "standalone_camera_original=" << (differences ? "failed" : "ok")
            << " cases=24 pixels=1536000 differences=" << differences
            << " live_owners=1 controlled=1 natural=0 whole_game_claim=0\n";
        return differences ? 1 : 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
