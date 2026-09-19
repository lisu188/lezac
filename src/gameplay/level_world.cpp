#include "gameplay/level_world.hpp"
#include "core/fixed_point.hpp"
#include "core/progress.hpp"
#include <cmath>

namespace lezac::gameplay {
using namespace lezac::core;
namespace {
int16_t clampI16(int value) { return static_cast<int16_t>(std::clamp(value, -32768, 32767)); }
void integrateAxis8_8(int& pos, uint8_t& frac, int16_t velocity) {
    core::Fixed8_8Axis axis{pos, frac};
    core::integrateFixed8_8(axis, velocity);
    pos = axis.position; frac = axis.fraction;
}
}

const LevelPortal* LevelWorld::findStartPortal(uint8_t marker) const {
        for (const LevelPortal& portal : state_.level_.portals) {
            if (portal.key == 0 && portal.marker == marker) {
                return &portal;
            }
        }
        return nullptr;
    }

int LevelWorld::tileAt(int tx, int ty) const {
        if (tx < 0 || ty < 0 || tx >= state_.level_.width || ty >= state_.level_.height) return 0;
        return state_.level_.tiles[static_cast<size_t>(ty) * state_.level_.width + tx];
    }

uint16_t LevelWorld::wordAt(int tx, int ty) const {
        if (tx < 0 || ty < 0 || tx >= state_.level_.width || ty >= state_.level_.height) return 0;
        size_t index = static_cast<size_t>(ty) * state_.level_.width + tx;
        return index < state_.level_.wordLayer.size() ? state_.level_.wordLayer[index] : 0;
    }

uint8_t& LevelWorld::tileRef(int tx, int ty) {
        return state_.level_.tiles[static_cast<size_t>(ty) * state_.level_.width + tx];
    }

uint16_t& LevelWorld::wordRef(int tx, int ty) {
        return state_.level_.wordLayer[static_cast<size_t>(ty) * state_.level_.width + tx];
    }

bool LevelWorld::solidPixel(float px, float py) const {
        int tx = static_cast<int>(px) / kTileSize;
        int ty = static_cast<int>(py) / kTileSize;
        uint8_t tileByte = static_cast<uint8_t>(tileAt(tx, ty));
        return countsForDestructionProgress(tileByte, state_.level_.objectiveTile) &&
               !isPassableObjectCell(tx, ty);
    }

bool LevelWorld::solidTileSide(uint8_t t) { return t >= 1 && t <= 0x4c; }

bool LevelWorld::solidTileBottom(uint8_t t) { return t >= 1 && t <= 0x52; }

ActiveMonster::EdgeFlags LevelWorld::scanActorEdges(int x, int yCollide) const {
        const int C = (x + 4) >> 3;
        const int R = yCollide >> 3;
        auto side = [&](int c, int r) { return solidTileSide(static_cast<uint8_t>(tileAt(c, r))); };
        auto bot = [&](int c, int r) { return solidTileBottom(static_cast<uint8_t>(tileAt(c, r))); };
        ActiveMonster::EdgeFlags e;
        e.top = side(C, R - 1) || side(C + 1, R - 1);
        e.bottom = bot(C, R + 2) || bot(C + 1, R + 2);
        e.left = side(C - 1, R) || side(C - 1, R + 1);
        e.right = side(C + 2, R) || side(C + 2, R + 1);
        return e;
    }

bool LevelWorld::scanActorStrongBottom(int x, int yCollide) const {
        const int column = (x + 4) >> 3;
        const int row = yCollide >> 3;
        return solidTileSide(
                   static_cast<uint8_t>(tileAt(column, row + 2))) ||
               solidTileSide(
                   static_cast<uint8_t>(tileAt(column + 1, row + 2)));
    }

bool LevelWorld::collides(float x, float y) const {
        return solidPixel(x, y) || solidPixel(x + 11.0f, y) ||
               solidPixel(x, y + 15.0f) || solidPixel(x + 11.0f, y + 15.0f);
    }

bool LevelWorld::monsterCollides(float x, float y) const {
        return solidPixel(x, y) || solidPixel(x + 13.0f, y) ||
               solidPixel(x, y + 15.0f) || solidPixel(x + 13.0f, y + 15.0f);
    }

bool LevelWorld::isBombObjectTile(uint8_t tile) const {
        return tile > 0x66 && tile < 0x73;
    }

bool LevelWorld::isHighBombObjectSoundTile(uint8_t tile) const {
        return tile > kBombObjectHighSoundThreshold;
    }

bool LevelWorld::isPassableObjectTile(uint8_t tile) const {
        return tile == 0x45 || isBombObjectTile(tile);
    }

bool LevelWorld::isPassableObjectCell(int tx, int ty) const {
        uint8_t tile = static_cast<uint8_t>(tileAt(tx, ty));
        if (isPassableObjectTile(tile)) return true;
        return countsForPhysicalDamageProgress(wordAt(tx, ty));
    }

bool LevelWorld::consumeBombObjectTile(int tx, int ty) {
        if (tx < 0 || ty < 0 || tx >= state_.level_.width || ty >= state_.level_.height) return false;
        uint8_t& tile = tileRef(tx, ty);
        if (!isBombObjectTile(tile)) return false;
        const bool flagged = (wordAt(tx, ty) & 0x8000u) != 0;
        tile = flagged ? 0xff : 0;
        if (!flagged) state_.level_.wordLayer[static_cast<size_t>(ty) * state_.level_.width + tx] = 0;
        return true;
    }

bool LevelWorld::markDamagedTile(int tx, int ty) {
        if (tx < 0 || ty < 0 || tx >= state_.level_.width || ty >= state_.level_.height) return false;
        uint8_t& tile = tileRef(tx, ty);
        bool counted = countsForDestructionProgress(tile, state_.level_.objectiveTile);
        if (tile != state_.level_.objectiveTile) {
            tile = 1;
        }
        return counted;
    }

bool LevelWorld::canReenterLevel() const {
        return state_.collected_ + remainingObjectiveTiles() >= state_.level_.requiredBonus;
    }

int LevelWorld::remainingObjectiveTiles() const {
        return static_cast<int>(std::count(state_.level_.tiles.begin(), state_.level_.tiles.end(),
                                           state_.level_.objectiveTile));
    }

int LevelWorld::destructionPercent() const {
        if (state_.level_.startingDestructibleTiles == 0) return 100;
        return std::min(100, state_.destroyed_ * 100 / state_.level_.startingDestructibleTiles);
    }

bool LevelWorld::isComplete() const {
        return state_.collected_ >= state_.level_.requiredBonus &&
               destructionPercent() >= static_cast<int>(state_.level_.requiredDestruction);
    }

bool LevelWorld::bossScanTileSolid(int index, int upper) const {
        if (index < 0 || static_cast<size_t>(index) >= state_.level_.tiles.size()) {
            return false;
        }
        int tile = state_.level_.tiles[static_cast<size_t>(index)];
        return tile >= 1 && tile <= upper;
    }

BossHeadEdges LevelWorld::scanBossHeadEdges(const ActiveMonster& monster) const {
        BossHeadEdges edges;
        const int stride = state_.level_.width;
        const int width = monster.bossBoxW;
        const int height = monster.bossBoxH;
        const int base = (monster.y >> 3) * stride + (monster.x >> 3);
        for (int i = 0; i < width; ++i) {
            if (bossScanTileSolid(base - stride + i, 0x4c)) edges.top = true;
            if (bossScanTileSolid(base + height * stride + i, 0x52)) {
                edges.bottom = true;
            }
        }
        for (int i = 0; i < height; ++i) {
            if (bossScanTileSolid(base - 1 + i * stride, 0x4c)) edges.left = true;
            if (bossScanTileSolid(base + width + i * stride, 0x4c)) {
                edges.right = true;
            }
        }
        return edges;
    }
}
