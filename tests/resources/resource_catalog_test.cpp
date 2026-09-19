#include "resources/asset_catalog.hpp"

#include <iostream>
#include <stdexcept>
#include <type_traits>
#include <utility>

using namespace lezac::resources;

static_assert(std::is_same_v<decltype(std::declval<AssetCatalog&>().levels()),
                             const std::vector<Level>&>);
static_assert(std::is_same_v<decltype(std::declval<AssetCatalog&>().sounds()),
                             const SoundBank&>);
static_assert(std::is_same_v<decltype(std::declval<AssetCatalog&>().palette()),
                             const Palette&>);

int main() {
    const auto raw = AssetCatalog::load(AssetFormat::Original);
    const auto json = AssetCatalog::load(AssetFormat::Json);
    auto require = [](bool condition) {
        if (!condition) throw std::runtime_error("asset catalog mismatch");
    };
    require(raw.levels().size() == 7 && json.levels().size() == 7);
    require(raw.background().width == 320 && raw.background().height == 200);
    require(raw.background().pixels == json.background().pixels);
    require(raw.tiles().count == 132 && raw.tiles().pixels == json.tiles().pixels);
    for (size_t i = 0; i < 256; ++i) {
        const auto a = raw.palette()[i], b = json.palette()[i];
        const auto c = raw.backgroundPalette()[i], d = json.backgroundPalette()[i];
        require(a.r == b.r && a.g == b.g && a.b == b.b);
        require(c.r == d.r && c.g == d.g && c.b == d.b);
    }
    auto spritesEqual = [&](const SpriteBank& a, const SpriteBank& b) {
        require(a.sprites.size() == b.sprites.size());
        for (size_t i = 0; i < a.sprites.size(); ++i) {
            require(a.sprites[i].width == b.sprites[i].width &&
                    a.sprites[i].height == b.sprites[i].height &&
                    a.sprites[i].pixels == b.sprites[i].pixels);
        }
    };
    spritesEqual(raw.sprites(), json.sprites());
    spritesEqual(raw.altSprites(), json.altSprites());
    spritesEqual(raw.fontSprites(), json.fontSprites());
    require(raw.sounds().stepCount == 130 && raw.sounds().payload == json.sounds().payload);
    require(raw.gran().records.size() == 7 && json.gran().records.size() == 7);
    for (size_t i = 0; i < 7; ++i) {
        require(raw.gran().records[i].bytes == json.gran().records[i].bytes);
        const auto& a = raw.levels()[i];
        const auto& b = json.levels()[i];
        require(a.width == b.width && a.height == b.height && a.tiles == b.tiles &&
                a.wordLayer == b.wordLayer && a.fieldA == b.fieldA && a.fieldB == b.fieldB &&
                a.startingObjectiveTiles == b.startingObjectiveTiles &&
                a.startingDestructibleTiles == b.startingDestructibleTiles);
    }
    require(raw.initialRecords().size() == 7 && json.initialRecords().size() == 7);
    for (size_t i = 0; i < 7; ++i) {
        require(raw.initialRecords()[i].score == json.initialRecords()[i].score &&
                raw.initialRecords()[i].encodedName == json.initialRecords()[i].encodedName);
    }
    auto level = raw.levels().front();
    auto palette = raw.palette();
    auto records = raw.initialRecords();
    const auto tile = level.tiles.front();
    const auto color = palette.front();
    const auto score = records.front().score;
    level.tiles.front() ^= 0xff;
    palette.front().r ^= 0xff;
    ++records.front().score;
    require(raw.levels().front().tiles.front() == tile && raw.palette().front().r == color.r &&
            raw.initialRecords().front().score == score);
    std::cout << "resource_catalog=ok formats=2 levels=7 sprite_banks=3 immutable_runtime_copies=3\n";
}
