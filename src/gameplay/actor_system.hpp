#pragma once
#include "gameplay/world_models.hpp"

namespace lezac::gameplay {

struct ActorSystemSnapshot {
    std::vector<SpawnerState> spawnerStates_;
    std::vector<ActiveMonster> monsters_;
    std::vector<BossMotionLink> bossLinks_;
    std::array<float, 128> bossSinTable_{};
    bool bossPresent_ = false;
    bool bossDefeated_ = false;
    std::vector<BonusDrop> bonusDrops_;
    std::vector<Bomb> bombs_;
    std::vector<LaunchPadMarker> launchPadMarkers_;
    std::vector<TransientActor> transientActors_;
    uint64_t nextActorOrder_ = 1;
    bool orderedActorPass_ = false;
};

class GameSession;
// The session alone coordinates cross-owner writes at recovered tick boundaries.
class ActorSystem {
public:
    const ActorSystemSnapshot& snapshot() const { return state_; }

    std::vector<SharedActorEntry> sharedActorEntries() const;
    uint64_t sharedActorVisualKey(const SharedActorEntry& entry) const;
    size_t sharedActorCount() const;
    size_t pickupActorCount() const;
private:
    friend class GameSession;
    void adoptUnorderedActors();
    uint64_t claimActorOrder();
    ActorSystemSnapshot state_;
};
}
