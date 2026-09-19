#include "gameplay/game_session.hpp"
#include "gameplay/motion_math.hpp"
#include "core/progress.hpp"
#include "resources/binary.hpp"
#include <cmath>

namespace lezac::gameplay {
using namespace lezac::core;
using detail::clampI16;
using detail::integrateAxis8_8;

GameSession::GameSession(const AssetCatalog& assets, sound::SoundEngine& sound, core::TurboRandom& random)
    : assets_(assets), sound_(sound), random_(random), levels_(assets.levels()),
      sprites_(assets.sprites()), altSprites_(assets.altSprites()), gran_(assets.gran()) {}

void GameSession::fireAtPlayer(uint8_t index, int x, int y) {
    tryActivePlayerFireAt(index == 2 ? player2_ : player_, x, y, index);
}
void GameSession::setFireLatch(uint8_t index, bool held) {
    (index == 2 ? reentryFire2_ : reentryFire1_) = held;
}
void GameSession::startRun(int playerCount) {
    playerCount_ = playerCount;
    lives_ = lives2_ = 3;
    clearRunScores();
}
void GameSession::notifyReentryBoundary(const char* phase) const {
    if (hooks_.reentryBoundaryObserver) hooks_.reentryBoundaryObserver(phase, view());
}

void GameSession::beginLevelSelection(int index, bool fromMenu, const DecodeLevelPlane& decodePlane) {
    // Level advance skips the original new-game clock reset (file 0x7f4c).
    levelIntroFrame_ = fromMenu ? 0 : logicTick_;
    if (levelRestartPromoted_) notifyReentryBoundary("level_init");
    levelIndex_ = (index + static_cast<int>(levels_.size())) % static_cast<int>(levels_.size());
    level_ = levels_[levelIndex_];
    // The presentation owner retains the shared compressed-input tail.
    if (!level_.encodedTiles.empty()) {
        level_.tiles = decodePlane(level_.encodedTiles, level_.tiles.size());
        const auto words = decodePlane(level_.encodedWords, level_.wordLayer.size() * 2);
        for (size_t i = 0; i < level_.wordLayer.size(); ++i) level_.wordLayer[i] = resources::le16(words, i * 2);
    }
}

void GameSession::finishLevelSetup(int index) {
    if (levelRestartPromoted_) notifyReentryBoundary("intro_ack");
    const uint32_t frame = levelIntroFrame_;
    const int countdown1 = reentryTimer_, countdown2 = reentryTimer2_;
    const uint8_t fallback = noActivePlayerTicks_;
    Level decodedLevel = std::move(level_);
    resetLevel(index);
    level_ = std::move(decodedLevel);
    logicTick_ = frame;
    reentryTimer_ = countdown1;
    reentryTimer2_ = countdown2;
    noActivePlayerTicks_ = fallback;
    player_.animation = ActorAnimation::initialize(2, 9, 1, 1);
}

CompletionAction GameSession::advanceCompletionState(bool interactive) {
    if (!isComplete()) {
        completeTimer_ = 0;
        return CompletionAction::None;
    }
    if (interactive) return CompletionAction::UpdateOutro;
    if (completeTimer_ == 0) playCompatibilitySound(kLevelCompleteCompatibilityHookSlot);
    if (++completeTimer_ > 100) {
        return isFinalLevel() ? CompletionAction::EndRun : CompletionAction::NextLevel;
    }
    return CompletionAction::None;
}

std::vector<SharedActorEntry> GameSession::renderActorOrder() {
    // Adoption stays at the existing draw boundary, before visual ordering.
    adoptUnorderedActors();
    auto order = sharedActorEntries();
    std::stable_sort(order.begin(), order.end(), [&](const auto& a, const auto& b) {
        return sharedActorVisualKey(a) < sharedActorVisualKey(b);
    });
    return order;
}
void GameSession::applyAfterActorPassActions() {
    auto actions = std::move(afterActorPassActions_);
    afterActorPassActions_.clear();
    for (auto& action : actions) for (auto actor : action.appendActors) {
        actor.actorOrder = claimActorOrder();
        transientActors_.push_back(std::move(actor));
    }
}

GameplayView GameSession::view() const { return {level_, levelIndex_, collected_, destroyed_, completeTimer_, levelResetGeneration_, levelIntroFrame_, logicTick_, playerCount_, player_, player2_, portalCooldown_, triggerCooldown_, portalCooldown2_, triggerCooldown2_, energy_, energy2_, lives_, lives2_, playerDead_, player2Dead_, reentryTimer_, reentryTimer2_, reentryFire1_, reentryFire2_, reentryGate_, noActivePlayerTicks_, levelRestartPromoted_, deathStateTimer_, deathStateTimer2_, pendingLifeLoss_, pendingLifeLoss2_, state2Visual_, state2Visual2_, state2Effect_, state2Effect2_, state2VisualCursorPreview_, state2VisualRowPreview_, damageCooldown_, damageCooldown2_, pendingDamage_, pendingDamage2_, bombInventory_, bombInventory2_, weaponSwitchHoldTicks_, weaponSwitchHoldTicks2_, score_, score2_, spawnerStates_, monsters_, bossLinks_, bossSinTable_, bossPresent_, bossDefeated_, bonusDrops_, bombs_, launchPadMarkers_, transientActors_, nextActorOrder_, orderedActorPass_, flashes_, cameraShakeTicks_, cameraShakeOffset_, explosionEffects_, flameRecords_, debrisQueue_, collapseQueue_, nextCollapseFragmentWord_, random_.seed()}; }
GameplayFixture GameSession::snapshot() const {
    GameplayFixture result;
    static_cast<LevelWorldSnapshot&>(result) = level_world_.state_;
    static_cast<PlayerRosterSnapshot&>(result) = player_roster_.state_;
    static_cast<ActorSystemSnapshot&>(result) = actor_system_.state_;
    static_cast<TerrainEffectsSnapshot&>(result) = terrain_effects_.state_;
    result.randomSeed_ = random_.seed();
    return result;
}
void GameSession::restoreFixture(const GameplayFixture& fixture) {
    level_world_.state_ = static_cast<const LevelWorldSnapshot&>(fixture);
    player_roster_.state_ = static_cast<const PlayerRosterSnapshot&>(fixture);
    actor_system_.state_ = static_cast<const ActorSystemSnapshot&>(fixture);
    terrain_effects_.state_ = static_cast<const TerrainEffectsSnapshot&>(fixture);
    random_.setSeed(fixture.randomSeed_);
}

}
