#pragma once

#include "resources/gran.hpp"
#include "resources/levels.hpp"
#include "resources/records.hpp"
#include "resources/sound.hpp"
#include "resources/types.hpp"

namespace lezac::resources {

enum class AssetFormat { Original, Json };

// Loaded definitions are immutable to consumers. Runtime palettes, level planes,
// records, and diagnostic fixtures use independent copies of the relevant data.
class AssetCatalog {
public:
    static AssetCatalog load(AssetFormat format);

    const Palette& palette() const { return palette_; }
    const Palette& backgroundPalette() const { return backgroundPalette_; }
    const IndexedImage& background() const { return background_; }
    const TileBank& tiles() const { return tiles_; }
    const SpriteBank& sprites() const { return sprites_; }
    const SpriteBank& altSprites() const { return altSprites_; }
    const SpriteBank& fontSprites() const { return fontSprites_; }
    const SoundBank& sounds() const { return sounds_; }
    const GranBank& gran() const { return gran_; }
    const std::vector<Record>& initialRecords() const { return records_; }
    const std::vector<Level>& levels() const { return levels_; }

private:
    Palette palette_{};
    Palette backgroundPalette_{};
    IndexedImage background_;
    TileBank tiles_;
    SpriteBank sprites_;
    SpriteBank altSprites_;
    SpriteBank fontSprites_;
    SoundBank sounds_;
    GranBank gran_;
    std::vector<Record> records_;
    std::vector<Level> levels_;
};

}
