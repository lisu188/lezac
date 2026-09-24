#pragma once
#include "gameplay/world_models.hpp"
#include "core/random.hpp"

namespace lezac::gameplay {

struct TerrainEffectsSnapshot {
    std::vector<Flash> flashes_;
    uint16_t cameraShakeTicks_ = 0;
    uint16_t cameraShakeOffset_ = 0;
    std::vector<ExplosionEffect> explosionEffects_;
    std::vector<FlameRecord> flameRecords_;
    std::vector<DebrisRecord> debrisQueue_;
    std::vector<CollapseRecord> collapseQueue_;
    uint16_t nextCollapseFragmentWord_ = 0;
};

class GameSession;
// The session alone coordinates cross-owner writes at recovered tick boundaries.
class TerrainEffects {
public:
    const TerrainEffectsSnapshot& snapshot() const { return state_; }

    DamagePhaseLookup resolveDamagePhase(uint16_t flaggedWord, bool reverse) const;
    uint8_t explosionDispatcherState(int visualSelector) const;
    int explosionEffectTicks(int visualType) const;
    uint8_t explosionVariantByte(int visualType) const;
    uint16_t explosionSoundOffset(int visualType) const;
    uint8_t explosionSoundSelector(int visualType) const;
private:
    friend class GameSession;
    void queueTileDamage(Level& level, int tx, int ty, uint8_t forwardPhase,
                         uint8_t reversePhase, bool preserveCollapseGlyphs);
    void expireVisualEffects();
    void updateCameraShake(core::TurboRandom& random);

    TerrainEffectsSnapshot state_;
};
}
