#include "resources/asset_catalog.hpp"

#include "resources/background.hpp"
#include "resources/io.hpp"
#include "resources/palette.hpp"
#include "resources/sprites.hpp"
#include "resources/tiles.hpp"

#include <stdexcept>

namespace lezac::resources {

AssetCatalog AssetCatalog::load(AssetFormat format) {
    AssetCatalog catalog;
    if (format == AssetFormat::Json) {
        catalog.palette_ = loadPaletteFile("BOMPAL.PAL.json");
        catalog.background_ = loadBackground("SFONLEF.ZBG.json", catalog.backgroundPalette_);
        catalog.tiles_ = loadTiles("CARO.CAR.json");
        catalog.sprites_ = loadSprites("BOMOMIMK.SPR.json");
        catalog.altSprites_ = loadSprites("PROVA.SPR.json");
        catalog.fontSprites_ = loadSprites("FONTS.SPR.json");
        catalog.records_ = loadRecords("RECS.DAT.json");
        catalog.sounds_ = loadSon("PROEFS.SON.json");
        catalog.gran_ = loadGran("GRAN.MST.json");
        catalog.levels_ = loadLevels("LIVELS.SCH.json");
    } else {
        catalog.palette_ = loadPalette(readFile("BOMPAL.PAL"), 0);
        catalog.background_ = loadRawBackground("SFONLEF.ZBG", catalog.backgroundPalette_);
        catalog.tiles_ = loadRawTiles("CARO.CAR");
        catalog.sprites_ = loadRawSprites("BOMOMIMK.SPR");
        catalog.altSprites_ = loadRawSprites("PROVA.SPR");
        catalog.fontSprites_ = loadRawSprites("FONTS.SPR");
        catalog.records_ = loadRawRecords("RECS.DAT");
        catalog.sounds_ = loadRawSon("PROEFS.SON");
        catalog.gran_ = loadRawGran("GRAN.MST");
        catalog.levels_ = loadRawLevels("LIVELS.SCH");
    }
    if (catalog.levels_.empty()) {
        throw std::runtime_error("no levels");
    }
    return catalog;
}

}
