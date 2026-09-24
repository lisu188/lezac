#pragma once
#include "gameplay/world_models.hpp"

namespace lezac::gameplay {

struct LevelWorldSnapshot {
    Level level_;
    int levelIndex_ = 0;
    int collected_ = 0;
    int destroyed_ = 0;
    int completeTimer_ = 0;
    int levelResetGeneration_ = 0;
    uint32_t levelIntroFrame_ = 0;
    uint32_t logicTick_ = 0;
};

class GameSession;
// The session alone coordinates cross-owner writes at recovered tick boundaries.
class LevelWorld {
public:
    const LevelWorldSnapshot& snapshot() const { return state_; }

    int tileAt(int tx, int ty) const;
    uint16_t wordAt(int tx, int ty) const;
    bool solidPixel(float px, float py) const;
    ActiveMonster::EdgeFlags scanActorEdges(int x, int yCollide) const;
    bool scanActorStrongBottom(int x, int yCollide) const;
    bool collides(float x, float y) const;
    bool monsterCollides(float x, float y) const;
    bool isBombObjectTile(uint8_t tile) const;
    bool isHighBombObjectSoundTile(uint8_t tile) const;
    bool isPassableObjectTile(uint8_t tile) const;
    bool isPassableObjectCell(int tx, int ty) const;
    bool canReenterLevel() const;
    int remainingObjectiveTiles() const;
    int destructionPercent() const;
    bool isComplete() const;
    bool bossScanTileSolid(int index, int upper) const;
    BossHeadEdges scanBossHeadEdges(const ActiveMonster& monster) const;
private:
    friend class GameSession;
    const LevelPortal* findStartPortal(uint8_t marker) const;
    uint8_t& tileRef(int tx, int ty);
    uint16_t& wordRef(int tx, int ty);
    static bool solidTileSide(uint8_t t);
    static bool solidTileBottom(uint8_t t);
    bool consumeBombObjectTile(int tx, int ty);
    bool markDamagedTile(int tx, int ty);
    LevelWorldSnapshot state_;
};
}
