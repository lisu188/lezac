#pragma once
#include "gameplay/gameplay_fixture.hpp"

namespace lezac::gameplay {
enum class ReplaySlot { Detached, Null, levelIndex_, playerCount_, player_, player2_, spawnerStates_, monsters_, bossLinks_, bossPresent_, bossDefeated_, bonusDrops_, bombs_, flashes_, launchPadMarkers_, transientActors_, cameraShakeTicks_, cameraShakeOffset_, explosionEffects_, flameRecords_, debrisQueue_, collapseQueue_, nextCollapseFragmentWord_, collected_, destroyed_, completeTimer_, portalCooldown_, triggerCooldown_, portalCooldown2_, triggerCooldown2_, energy_, energy2_, lives_, lives2_, playerDead_, player2Dead_, reentryTimer_, reentryTimer2_, reentryFire1_, reentryFire2_, reentryGate_, noActivePlayerTicks_, levelRestartPromoted_, levelIntroFrame_, deathStateTimer_, deathStateTimer2_, pendingLifeLoss_, pendingLifeLoss2_, state2Visual_, state2Visual2_, state2Effect_, state2Effect2_, state2VisualCursorPreview_, state2VisualRowPreview_, damageCooldown_, damageCooldown2_, pendingDamage_, pendingDamage2_, levelResetGeneration_, bombInventory_, bombInventory2_, weaponSwitchHoldTicks_, weaponSwitchHoldTicks2_, logicTick_, orderedActorPass_, score_, score2_, levelTiles, levelWords, levelPortals };
template<class T> struct ReplayTarget {
    ReplaySlot slot = ReplaySlot::Detached;
    size_t index = 0;
    T value{};
};
}
