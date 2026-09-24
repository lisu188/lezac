#pragma once
#include "gameplay/level_world.hpp"
#include "gameplay/player_roster.hpp"
#include "gameplay/actor_system.hpp"
#include "gameplay/terrain_effects.hpp"

namespace lezac::gameplay {
// An owned value: mutations cannot affect a live session until an explicit restore.
struct GameplayFixture : LevelWorldSnapshot, PlayerRosterSnapshot, ActorSystemSnapshot, TerrainEffectsSnapshot {
    uint32_t randomSeed_ = 0x1234abcd;
};

// Cheap read-only projection; no mutable runtime references leave GameSession.
struct GameplayView {
    const Level& level_;
    const int& levelIndex_;
    const int& collected_;
    const int& destroyed_;
    const int& completeTimer_;
    const int& levelResetGeneration_;
    const uint32_t& levelIntroFrame_;
    const uint32_t& logicTick_;
    const int& playerCount_;
    const Player& player_;
    const Player& player2_;
    const int& portalCooldown_;
    const int& triggerCooldown_;
    const int& portalCooldown2_;
    const int& triggerCooldown2_;
    const int& energy_;
    const int& energy2_;
    const int& lives_;
    const int& lives2_;
    const bool& playerDead_;
    const bool& player2Dead_;
    const int& reentryTimer_;
    const int& reentryTimer2_;
    const bool& reentryFire1_;
    const bool& reentryFire2_;
    const bool& reentryGate_;
    const uint8_t& noActivePlayerTicks_;
    const bool& levelRestartPromoted_;
    const int& deathStateTimer_;
    const int& deathStateTimer2_;
    const bool& pendingLifeLoss_;
    const bool& pendingLifeLoss2_;
    const State2VisualCursor& state2Visual_;
    const State2VisualCursor& state2Visual2_;
    const State2EffectEntry& state2Effect_;
    const State2EffectEntry& state2Effect2_;
    const bool& state2VisualCursorPreview_;
    const bool& state2VisualRowPreview_;
    const int& damageCooldown_;
    const int& damageCooldown2_;
    const uint8_t& pendingDamage_;
    const uint8_t& pendingDamage2_;
    const BombInventory& bombInventory_;
    const BombInventory& bombInventory2_;
    const uint8_t& weaponSwitchHoldTicks_;
    const uint8_t& weaponSwitchHoldTicks2_;
    const uint32_t& score_;
    const uint32_t& score2_;
    const std::vector<SpawnerState>& spawnerStates_;
    const std::vector<ActiveMonster>& monsters_;
    const std::vector<BossMotionLink>& bossLinks_;
    const std::array<float, 128>& bossSinTable_;
    const bool& bossPresent_;
    const bool& bossDefeated_;
    const std::vector<BonusDrop>& bonusDrops_;
    const std::vector<Bomb>& bombs_;
    const std::vector<LaunchPadMarker>& launchPadMarkers_;
    const std::vector<TransientActor>& transientActors_;
    const uint64_t& nextActorOrder_;
    const bool& orderedActorPass_;
    const std::vector<Flash>& flashes_;
    const uint16_t& cameraShakeTicks_;
    const uint16_t& cameraShakeOffset_;
    const std::vector<ExplosionEffect>& explosionEffects_;
    const std::vector<FlameRecord>& flameRecords_;
    const std::vector<DebrisRecord>& debrisQueue_;
    const std::vector<CollapseRecord>& collapseQueue_;
    const uint16_t& nextCollapseFragmentWord_;
    uint32_t randomSeed_;
};
}
