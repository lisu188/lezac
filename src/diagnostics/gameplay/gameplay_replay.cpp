#include "diagnostics/gameplay/gameplay_replay.hpp"
namespace lezac::diagnostics {
namespace {
template<class T> void reconcile(T& target, const T& source) { target = source; }
template<class T> void reconcile(std::vector<T>& target, const std::vector<T>& source) {
    target.resize(source.size());
    std::copy(source.begin(), source.end(), target.begin());
}
}
void GameplayReplay::refresh() const {
    const auto state = session_.view();
    reconcile(fixture_.level_, state.level_);
    reconcile(fixture_.levelIndex_, state.levelIndex_);
    reconcile(fixture_.collected_, state.collected_);
    reconcile(fixture_.destroyed_, state.destroyed_);
    reconcile(fixture_.completeTimer_, state.completeTimer_);
    reconcile(fixture_.levelResetGeneration_, state.levelResetGeneration_);
    reconcile(fixture_.levelIntroFrame_, state.levelIntroFrame_);
    reconcile(fixture_.logicTick_, state.logicTick_);
    reconcile(fixture_.playerCount_, state.playerCount_);
    reconcile(fixture_.player_, state.player_);
    reconcile(fixture_.player2_, state.player2_);
    reconcile(fixture_.portalCooldown_, state.portalCooldown_);
    reconcile(fixture_.triggerCooldown_, state.triggerCooldown_);
    reconcile(fixture_.portalCooldown2_, state.portalCooldown2_);
    reconcile(fixture_.triggerCooldown2_, state.triggerCooldown2_);
    reconcile(fixture_.energy_, state.energy_);
    reconcile(fixture_.energy2_, state.energy2_);
    reconcile(fixture_.lives_, state.lives_);
    reconcile(fixture_.lives2_, state.lives2_);
    reconcile(fixture_.playerDead_, state.playerDead_);
    reconcile(fixture_.player2Dead_, state.player2Dead_);
    reconcile(fixture_.reentryTimer_, state.reentryTimer_);
    reconcile(fixture_.reentryTimer2_, state.reentryTimer2_);
    reconcile(fixture_.reentryFire1_, state.reentryFire1_);
    reconcile(fixture_.reentryFire2_, state.reentryFire2_);
    reconcile(fixture_.reentryGate_, state.reentryGate_);
    reconcile(fixture_.noActivePlayerTicks_, state.noActivePlayerTicks_);
    reconcile(fixture_.levelRestartPromoted_, state.levelRestartPromoted_);
    reconcile(fixture_.deathStateTimer_, state.deathStateTimer_);
    reconcile(fixture_.deathStateTimer2_, state.deathStateTimer2_);
    reconcile(fixture_.pendingLifeLoss_, state.pendingLifeLoss_);
    reconcile(fixture_.pendingLifeLoss2_, state.pendingLifeLoss2_);
    reconcile(fixture_.state2Visual_, state.state2Visual_);
    reconcile(fixture_.state2Visual2_, state.state2Visual2_);
    reconcile(fixture_.state2Effect_, state.state2Effect_);
    reconcile(fixture_.state2Effect2_, state.state2Effect2_);
    reconcile(fixture_.state2VisualCursorPreview_, state.state2VisualCursorPreview_);
    reconcile(fixture_.state2VisualRowPreview_, state.state2VisualRowPreview_);
    reconcile(fixture_.damageCooldown_, state.damageCooldown_);
    reconcile(fixture_.damageCooldown2_, state.damageCooldown2_);
    reconcile(fixture_.pendingDamage_, state.pendingDamage_);
    reconcile(fixture_.pendingDamage2_, state.pendingDamage2_);
    reconcile(fixture_.bombInventory_, state.bombInventory_);
    reconcile(fixture_.bombInventory2_, state.bombInventory2_);
    reconcile(fixture_.weaponSwitchHoldTicks_, state.weaponSwitchHoldTicks_);
    reconcile(fixture_.weaponSwitchHoldTicks2_, state.weaponSwitchHoldTicks2_);
    reconcile(fixture_.score_, state.score_);
    reconcile(fixture_.score2_, state.score2_);
    reconcile(fixture_.spawnerStates_, state.spawnerStates_);
    reconcile(fixture_.monsters_, state.monsters_);
    reconcile(fixture_.bossLinks_, state.bossLinks_);
    reconcile(fixture_.bossSinTable_, state.bossSinTable_);
    reconcile(fixture_.bossPresent_, state.bossPresent_);
    reconcile(fixture_.bossDefeated_, state.bossDefeated_);
    reconcile(fixture_.bonusDrops_, state.bonusDrops_);
    reconcile(fixture_.bombs_, state.bombs_);
    reconcile(fixture_.launchPadMarkers_, state.launchPadMarkers_);
    reconcile(fixture_.transientActors_, state.transientActors_);
    reconcile(fixture_.nextActorOrder_, state.nextActorOrder_);
    reconcile(fixture_.orderedActorPass_, state.orderedActorPass_);
    reconcile(fixture_.flashes_, state.flashes_);
    reconcile(fixture_.cameraShakeTicks_, state.cameraShakeTicks_);
    reconcile(fixture_.cameraShakeOffset_, state.cameraShakeOffset_);
    reconcile(fixture_.explosionEffects_, state.explosionEffects_);
    reconcile(fixture_.flameRecords_, state.flameRecords_);
    reconcile(fixture_.debrisQueue_, state.debrisQueue_);
    reconcile(fixture_.collapseQueue_, state.collapseQueue_);
    reconcile(fixture_.nextCollapseFragmentWord_, state.nextCollapseFragmentWord_);
    fixture_.randomSeed_ = state.randomSeed_;
}
}
