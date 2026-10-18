#include "rendering/world_raster.hpp"
#include "rendering/canvas.hpp"
#include "rendering/presentation_state.hpp"
#include "gameplay/actor_storage.hpp"
#include "gameplay/map_plane_memory.hpp"

#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <string>
#include <type_traits>

using namespace lezac;
namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
}

int main() {
    static_assert(!std::is_copy_constructible_v<rendering::WorldRaster> &&
        !std::is_move_constructible_v<rendering::WorldRaster>);
    try {
        resources::AssetCatalog assets;
        rendering::WorldRaster raster(assets);
        assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
        rendering::PresentationState presentation;
        presentation.setPalette(assets.palette());
        presentation.initializeBackdropBuffer(1);
        auto level = assets.levels().front();
        std::fill(level.tiles.begin(), level.tiles.end(), uint8_t{0});
        std::fill(level.wordLayer.begin(), level.wordLayer.end(), uint16_t{0});
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
        const auto layout = rendering::ViewportLayout::initialize(1,320);
        const rendering::WorldRenderView world{level,0,1,
            {{{first,false,2,cursor,effect,1},{second,false,2,cursor,effect,0}}},
            bombs,monsters,bonuses,flashes,markers,transients,order,320,true,0,false,false,
            &layout,&map,&slots.state()};
        rendering::Canvas canvas;
        for (unsigned missing = 0; missing < 2; ++missing) {
            auto unowned = world;
            if (missing == 0) unowned.mapMemory = nullptr;
            else unowned.physicalVisuals = nullptr;
            bool rejected = false;
            try { raster.drawGame(unowned,presentation,canvas); }
            catch (const std::invalid_argument&) { rejected = true; }
            require(rejected,"Production raster silently used a seeded diagnostic projection");
        }
        raster.drawGame(world,presentation,canvas);
        require(raster.lastCompletedWork().physicalVisuals &&
            raster.lastCompletedWork().dispatchedInstructions > 0,
            "Raster did not dispatch with the live physical visual owner");
        const auto baseline = canvas.pixels();

        const auto split = rendering::ViewportLayout::initialize(2,320);
        auto twoPlayers = world;
        twoPlayers.playerCount = 2; twoPlayers.players[1].globalState = 1; twoPlayers.viewportLayout = &split;
        rendering::Canvas full, oneView;
        raster.drawGame(twoPlayers,presentation,full);
        raster.drawView(twoPlayers,second,164,4,152,152,presentation,oneView);
        for (size_t y = 4; y < 156; ++y) for (size_t x = 164; x < 316; ++x) {
            const size_t at = y*320+x;
            require(oneView.paletteIndices()[at] == full.paletteIndices()[at],
                "Second-player camera overwrote the first player's visual position");
        }

        const auto& sprite = assets.sprites().sprites.front().pixels;
        const auto nonzero = std::find_if(sprite.begin(),sprite.end(),[](uint8_t value) { return value != 0; });
        require(nonzero != sprite.end(),"Sprite ownership control has no visible pixels");
        const auto source = static_cast<uint16_t>(nonzero-sprite.begin());
        require(static_cast<size_t>(source)+15 <= sprite.size(),"Sprite ownership control exceeds its source");
        const gameplay::ActorStorage::Descriptor latched{5,3,static_cast<uint8_t>(source),static_cast<uint8_t>(source>>8)};
        require(slots.append({10,30,5,1,0,0,100,130},latched) == 1,"Physical actor allocation failed");
        const auto before = slots.state();
        raster.drawGame(world,presentation,canvas);
        for (size_t y = 0; y < 3; ++y) for (size_t x = 0; x < 5; ++x) {
            const auto value = sprite[source+y*5+x];
            const size_t at = (46+y)*320+104+x;
            require(value ? canvas.paletteIndices()[at] == value : canvas.pixels()[at] == baseline[at],
                "Raster reconstructed rather than borrowed the latched physical visual");
        }
        require(canvas.pixels()[46*320+109] == baseline[46*320+109],"Raster replaced latched width with sprite-bank width");
        require(slots.state().actors == before.actors && slots.state().visuals == before.visuals,
            "Raster mutated the live physical actor owner");

        auto& moved = slots.visual(2);
        moved[0] = 120; moved[1] = 0;
        moved[2] = 140; moved[3] = 0;
        raster.drawGame(world,presentation,canvas);
        require(canvas.paletteIndices()[56*320+124] == *nonzero &&
            canvas.pixels()[46*320+104] == baseline[46*320+104],
            "Raster cached an actor snapshot or refreshed a latched descriptor");

        const auto& tile = assets.tiles().pixels;
        const auto colored = std::find_if(tile.begin()+64,tile.begin()+128,[](uint8_t value) { return value != 0; });
        require(colored != tile.begin()+128,"Tile ownership control has no visible pixels");
        const size_t within = static_cast<size_t>(colored-tile.begin()-64);
        level.tiles[13*static_cast<size_t>(level.width)+8] = 1;
        raster.drawGame(world,presentation,canvas);
        require(canvas.paletteIndices()[(20+within/8)*320+68+within%8] == *colored,
            "Raster cached rather than read the live map plane");

        gameplay::MapPlaneMemory adjacent;
        adjacent.restoreSeparatedPlanesForFixture();
        const std::vector<uint8_t> tinyTiles{0x12};
        const std::vector<uint16_t> tinyWords{0xabcd};
        require(adjacent.readObject(65536,tinyTiles,tinyWords) == 0x12 &&
            adjacent.readObjectAddress(65536,tinyTiles,tinyWords) == 0xcd,
            "Physical word high byte wrapped to the map segment start");
        std::vector<uint8_t> tallTiles(8000);
        std::vector<uint16_t> tallWords(8000);
        tallTiles[5519] = 0x56; tallTiles[5520] = 0x67;
        require(presentation.backdropAddress(65535,tallTiles,tallWords,&adjacent) == 0x56 &&
            presentation.backdropAddress(65536,tallTiles,tallWords,&adjacent) == 0x67,
            "Backdrop word high byte did not retain its physical map alias");
        rendering::PresentationState uninitialized;
        bool missingBackdrop = false;
        try { (void)uninitialized.backdropAddress(8,tinyTiles,tinyWords,&adjacent); }
        catch (const std::out_of_range&) { missingBackdrop = true; }
        require(missingBackdrop,"Uninitialized backdrop payload reached padding with a negative index");

        level.tiles[13*static_cast<size_t>(level.width)+8] = 255;
        bool unknownTile = false;
        try { raster.drawGame(world,presentation,canvas); }
        catch (const std::out_of_range& error) {
            unknownTile = std::string(error.what()).find("unrecovered data byte") != std::string::npos;
        }
        require(unknownTile,"Unrecovered tile-mask data was silently painted");
        level.tiles[13*static_cast<size_t>(level.width)+8] = 1;

        const gameplay::ActorStorage::Descriptor invalid{2,1,255,255};
        std::copy(invalid.begin(),invalid.end(),slots.visual(2).begin()+4);
        const auto retained = canvas.pixels();
        bool rejected = false;
        try { raster.drawGame(world,presentation,canvas); }
        catch (const std::out_of_range&) { rejected = true; }
        require(rejected && canvas.pixels() == retained,"Unrecovered sprite heap access was silently painted");
        std::cout << "world_raster_owners=ok lazy_assets=1 physical_rows=1 live_map=1 word_adjacent_byte=1 rejected_sprite_heap=1 rejected_unknown_tile=1\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "world_raster_owners=failed " << error.what() << '\n';
        return 1;
    }
}
