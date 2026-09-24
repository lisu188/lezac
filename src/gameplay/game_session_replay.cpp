#include "gameplay/game_session.hpp"
namespace lezac::gameplay {
void GameSession::replay_resetLevel(int index) { resetLevel(index); }
ReplayTarget<LevelPortal> GameSession::replay_findStartPortal(uint8_t marker) { return targetOf(findStartPortal(marker)); }
void GameSession::replay_tryActivePlayerFireAt(ReplayTarget<Player>& player, int x, int y, uint8_t playerIndex) {
    auto& bound_player = bindDetachedAlias(player, {});
    tryActivePlayerFireAt(resolve(bound_player), x, y, playerIndex);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
}
int GameSession::replay_tileAt(int tx, int ty) { return tileAt(tx, ty); }
uint16_t GameSession::replay_wordAt(int tx, int ty) { return wordAt(tx, ty); }
ReplayTarget<uint8_t> GameSession::replay_tileRef(int tx, int ty) { return targetOf(&tileRef(tx, ty)); }
ReplayTarget<uint16_t> GameSession::replay_wordRef(int tx, int ty) { return targetOf(&wordRef(tx, ty)); }
bool GameSession::replay_solidPixel(float px, float py) { return solidPixel(px, py); }
bool GameSession::replay_solidTileSide(uint8_t t) { return solidTileSide(t); }
bool GameSession::replay_solidTileBottom(uint8_t t) { return solidTileBottom(t); }
ActiveMonster::EdgeFlags GameSession::replay_scanActorEdges(int x, int yCollide) { return scanActorEdges(x, yCollide); }
bool GameSession::replay_scanActorStrongBottom(int x, int yCollide) { return scanActorStrongBottom(x, yCollide); }
bool GameSession::replay_collides(float x, float y) { return collides(x, y); }
bool GameSession::replay_monsterCollides(float x, float y) { return monsterCollides(x, y); }
bool GameSession::replay_playerOverlaps(ReplayTarget<Player>& player, float x, float y, float w, float h) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto result = playerOverlaps(resolve(bound_player), x, y, w, h);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    return result;
}
int GameSession::replay_bombTypeIndex(BombType type) { return bombTypeIndex(type); }
int GameSession::replay_explosionVisualType(BombType type) { return explosionVisualType(type); }
uint8_t GameSession::replay_explosionDispatcherState(int visualSelector) { return explosionDispatcherState(visualSelector); }
int GameSession::replay_explosionEffectTicks(int visualType) { return explosionEffectTicks(visualType); }
uint8_t GameSession::replay_explosionVariantByte(int visualType) { return explosionVariantByte(visualType); }
uint16_t GameSession::replay_explosionSoundOffset(int visualType) { return explosionSoundOffset(visualType); }
uint8_t GameSession::replay_explosionSoundSelector(int visualType) { return explosionSoundSelector(visualType); }
bool GameSession::replay_hasBomb(ReplayTarget<BombInventory>& inventory, BombType type) {
    auto& bound_inventory = bindDetachedAlias(inventory, {});
    auto result = hasBomb(resolve(bound_inventory), type);
    if (inventory.slot == ReplaySlot::Detached) inventory.value = bound_inventory.value;
    return result;
}
void GameSession::replay_selectNextAvailableBomb(ReplayTarget<BombInventory>& inventory) {
    auto& bound_inventory = bindDetachedAlias(inventory, {});
    selectNextAvailableBomb(resolve(bound_inventory));
    if (inventory.slot == ReplaySlot::Detached) inventory.value = bound_inventory.value;
}
void GameSession::replay_updateWeaponSwitch(ReplayTarget<BombInventory>& inventory, ReplayTarget<uint8_t>& holdTicks, bool pressed) {
    auto& bound_inventory = bindDetachedAlias(inventory, {});
    auto& bound_holdTicks = bindDetachedAlias(holdTicks, {});
    updateWeaponSwitch(resolve(bound_inventory), resolve(bound_holdTicks), pressed);
    if (inventory.slot == ReplaySlot::Detached) inventory.value = bound_inventory.value;
    if (holdTicks.slot == ReplaySlot::Detached) holdTicks.value = bound_holdTicks.value;
}
void GameSession::replay_updatePlayerReentryPrepass(const FrameControls& controls) { updatePlayerReentryPrepass(controls); }
void GameSession::replay_updateWithControls(const FrameControls& controls, float dt) { updateWithControls(controls, dt); }
bool GameSession::replay_activateLaunchPad(ReplayTarget<Player>& player, bool down, int localY) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto result = activateLaunchPad(resolve(bound_player), down, localY);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    return result;
}
void GameSession::replay_updateLaunchPadMarkers(uint64_t onlyOrder) { updateLaunchPadMarkers(onlyOrder); }
void GameSession::replay_selectPlayerPosture(ReplayTarget<Player>& player, uint8_t spriteBase, bool dropping) {
    auto& bound_player = bindDetachedAlias(player, {});
    selectPlayerPosture(resolve(bound_player), spriteBase, dropping);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
}
void GameSession::replay_updatePlayerGravity(ReplayTarget<Player>& player, bool bottom, uint8_t spriteBase, ReplayTarget<int>& y) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto& bound_y = bindDetachedAlias(y, {});
    updatePlayerGravity(resolve(bound_player), bottom, spriteBase, resolve(bound_y));
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    if (y.slot == ReplaySlot::Detached) y.value = bound_y.value;
}
void GameSession::replay_updatePlayer(ReplayTarget<Player>& player, bool left, bool right, bool jump, bool switchWeapon, uint8_t spriteBase, bool down) {
    auto& bound_player = bindDetachedAlias(player, {});
    updatePlayer(resolve(bound_player), left, right, jump, switchWeapon, spriteBase, down);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
}
void GameSession::replay_applyPlayerTerrainDamage(ReplayTarget<Player>& player, ReplayTarget<int>& energy) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto& bound_energy = bindDetachedAlias(energy, {});
    applyPlayerTerrainDamage(resolve(bound_player), resolve(bound_energy));
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    if (energy.slot == ReplaySlot::Detached) energy.value = bound_energy.value;
}
void GameSession::replay_updateDyingPlayerMotion(ReplayTarget<Player>& player) {
    auto& bound_player = bindDetachedAlias(player, {});
    updateDyingPlayerMotion(resolve(bound_player));
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
}
void GameSession::replay_integratePlayerMotion(ReplayTarget<Player>& player, int x, int y, const ActiveMonster::EdgeFlags& edges) {
    auto& bound_player = bindDetachedAlias(player, {});
    integratePlayerMotion(resolve(bound_player), x, y, edges);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
}
void GameSession::replay_syncPlayerVelocityMirror(ReplayTarget<Player>& player) {
    auto& bound_player = bindDetachedAlias(player, {});
    syncPlayerVelocityMirror(resolve(bound_player));
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
}
int16_t GameSession::replay_actorFloorFriction(int16_t velocity) { return actorFloorFriction(velocity); }
int16_t GameSession::replay_playerWalkVelocity(int16_t velocity, bool left, bool right, bool bottom) { return playerWalkVelocity(velocity, left, right, bottom); }
std::vector<SharedActorEntry> GameSession::replay_sharedActorEntries() { return sharedActorEntries(); }
uint64_t GameSession::replay_sharedActorVisualKey(const SharedActorEntry& entry) { return sharedActorVisualKey(entry); }
void GameSession::replay_adoptUnorderedActors() { adoptUnorderedActors(); }
uint64_t GameSession::replay_claimActorOrder() { return claimActorOrder(); }
void GameSession::replay_updateOrderedActors(float dt) { updateOrderedActors(dt); }
size_t GameSession::replay_sharedActorCount() { return sharedActorCount(); }
void GameSession::replay_updateCameraShake() { updateCameraShake(); }
size_t GameSession::replay_pickupActorCount() { return pickupActorCount(); }
ReplayTarget<TransientActor> GameSession::replay_spawnTransientActor(int x, int y, int16_t vy8, uint8_t sprite, uint8_t kind, uint8_t timer, ActorAnimation animation) { return targetOf(spawnTransientActor(x, y, vy8, sprite, kind, timer, animation)); }
void GameSession::replay_updateTransientActor(ReplayTarget<TransientActor>& actor) {
    auto& bound_actor = bindDetachedAlias(actor, {});
    updateTransientActor(resolve(bound_actor));
    if (actor.slot == ReplaySlot::Detached) actor.value = bound_actor.value;
}
void GameSession::replay_updateTransientActors() { updateTransientActors(); }
void GameSession::replay_collectObjectiveTiles(ReplayTarget<Player>& player, uint8_t playerIndex) {
    auto& bound_player = bindDetachedAlias(player, {});
    collectObjectiveTiles(resolve(bound_player), playerIndex);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
}
void GameSession::replay_updatePortalsAndTriggers(ReplayTarget<Player>& player, ReplayTarget<int>& portalCooldown, ReplayTarget<int>& triggerCooldown, bool down) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto& bound_portalCooldown = bindDetachedAlias(portalCooldown, {});
    auto& bound_triggerCooldown = bindDetachedAlias(triggerCooldown, {{2, &bound_portalCooldown}});
    updatePortalsAndTriggers(resolve(bound_player), resolve(bound_portalCooldown), resolve(bound_triggerCooldown), down);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    if (portalCooldown.slot == ReplaySlot::Detached) portalCooldown.value = bound_portalCooldown.value;
    if (triggerCooldown.slot == ReplaySlot::Detached) triggerCooldown.value = bound_triggerCooldown.value;
}
bool GameSession::replay_applyTileTrigger(uint16_t key) { return applyTileTrigger(key); }
void GameSession::replay_accountTileRewrite(uint8_t from, uint8_t to) { accountTileRewrite(from, to); }
std::array<int, 2> GameSession::replay_monsterFrameRange(uint8_t kind) { return monsterFrameRange(kind); }
std::array<int, 2> GameSession::replay_monsterDirectionalFrameRange(uint8_t kind, int16_t vx8) { return monsterDirectionalFrameRange(kind, vx8); }
uint8_t GameSession::replay_monsterHotspotY(uint8_t kind) { return monsterHotspotY(kind); }
bool GameSession::replay_actorTouchesPlayer(ReplayTarget<Player>& player, int ax, int ayCollide) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto result = actorTouchesPlayer(resolve(bound_player), ax, ayCollide);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    return result;
}
uint16_t GameSession::replay_randomRangeValue(uint16_t base, uint16_t range) { return randomRangeValue(base, range); }
int GameSession::replay_randomInclusive(int low, int high) { return randomInclusive(low, high); }
int16_t GameSession::replay_groundWalkerSpeed8(ReplayTarget<ActiveMonster>& monster) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    auto result = groundWalkerSpeed8(resolve(bound_monster));
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
    return result;
}
int16_t GameSession::replay_retargetSpeed8(ReplayTarget<ActiveMonster>& monster) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    auto result = retargetSpeed8(resolve(bound_monster));
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
    return result;
}
void GameSession::replay_refreshMonsterAnimationProfile(ReplayTarget<ActiveMonster>& monster) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    refreshMonsterAnimationProfile(resolve(bound_monster));
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
}
void GameSession::replay_reselectWalkerFacing(ReplayTarget<ActiveMonster>& monster) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    reselectWalkerFacing(resolve(bound_monster));
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
}
void GameSession::replay_initializeMonsterMotion(ReplayTarget<ActiveMonster>& monster) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    initializeMonsterMotion(resolve(bound_monster));
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
}
void GameSession::replay_retargetMonster(ReplayTarget<ActiveMonster>& monster) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    retargetMonster(resolve(bound_monster));
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
}
ReplayTarget<Player> GameSession::replay_nearestPlayer(float x, float y) { return targetOf(&nearestPlayer(x, y)); }
void GameSession::replay_updateMonsterMotion(ReplayTarget<ActiveMonster>& monster, float unused1) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    updateMonsterMotion(resolve(bound_monster), unused1);
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
}
void GameSession::replay_spawnLevel7Boss() { spawnLevel7Boss(); }
ReplayTarget<ActiveMonster> GameSession::replay_findBossActorByVisual(uint8_t visual) { return targetOf(findBossActorByVisual(visual)); }
void GameSession::replay_updateBossLinks() { updateBossLinks(); }
void GameSession::replay_applyBossSegmentLinks(ReplayTarget<ActiveMonster>& monster) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    applyBossSegmentLinks(resolve(bound_monster));
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
}
bool GameSession::replay_isBossMotionBehavior(int behavior) { return isBossMotionBehavior(behavior); }
bool GameSession::replay_bossScanTileSolid(int index, int upper) { return bossScanTileSolid(index, upper); }
BossHeadEdges GameSession::replay_scanBossHeadEdges(ReplayTarget<ActiveMonster>& monster) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    auto result = scanBossHeadEdges(resolve(bound_monster));
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
    return result;
}
void GameSession::replay_updateBossHead(ReplayTarget<ActiveMonster>& monster) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    updateBossHead(resolve(bound_monster));
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
}
void GameSession::replay_damageBossHeadFromFlames(ReplayTarget<ActiveMonster>& monster) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    damageBossHeadFromFlames(resolve(bound_monster));
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
}
void GameSession::replay_bossDeathChain(ReplayTarget<ActiveMonster>& head) {
    auto& bound_head = bindDetachedAlias(head, {});
    bossDeathChain(resolve(bound_head));
    if (head.slot == ReplaySlot::Detached) head.value = bound_head.value;
}
void GameSession::replay_updateMonsterSpawners() { updateMonsterSpawners(); }
void GameSession::replay_updateMonsters(float dt, uint64_t onlyOrder) { updateMonsters(dt, onlyOrder); }
void GameSession::replay_releaseMonsterSlot(ReplayTarget<ActiveMonster>& monster) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    releaseMonsterSlot(resolve(bound_monster));
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
}
void GameSession::replay_updateDamageCooldowns() { updateDamageCooldowns(); }
void GameSession::replay_queuePlayerDamage(uint8_t startMarker, uint8_t amount) { queuePlayerDamage(startMarker, amount); }
void GameSession::replay_drainPlayerDamageCounters() { drainPlayerDamageCounters(); }
void GameSession::replay_drainPlayerDamageCounter(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, ReplayTarget<uint8_t>& pending, uint8_t startMarker) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto& bound_energy = bindDetachedAlias(energy, {});
    auto& bound_lives = bindDetachedAlias(lives, {{2, &bound_energy}});
    auto& bound_dead = bindDetachedAlias(dead, {});
    auto& bound_timer = bindDetachedAlias(timer, {{2, &bound_energy}, {3, &bound_lives}});
    auto& bound_pending = bindDetachedAlias(pending, {});
    drainPlayerDamageCounter(resolve(bound_player), resolve(bound_energy), resolve(bound_lives), resolve(bound_dead), resolve(bound_timer), resolve(bound_pending), startMarker);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    if (energy.slot == ReplaySlot::Detached) energy.value = bound_energy.value;
    if (lives.slot == ReplaySlot::Detached) lives.value = bound_lives.value;
    if (dead.slot == ReplaySlot::Detached) dead.value = bound_dead.value;
    if (timer.slot == ReplaySlot::Detached) timer.value = bound_timer.value;
    if (pending.slot == ReplaySlot::Detached) pending.value = bound_pending.value;
}
void GameSession::replay_damagePlayer(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, ReplayTarget<int>& damageCooldown, uint8_t startMarker) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto& bound_energy = bindDetachedAlias(energy, {});
    auto& bound_lives = bindDetachedAlias(lives, {{2, &bound_energy}});
    auto& bound_dead = bindDetachedAlias(dead, {});
    auto& bound_timer = bindDetachedAlias(timer, {{2, &bound_energy}, {3, &bound_lives}});
    auto& bound_damageCooldown = bindDetachedAlias(damageCooldown, {{2, &bound_energy}, {3, &bound_lives}, {5, &bound_timer}});
    damagePlayer(resolve(bound_player), resolve(bound_energy), resolve(bound_lives), resolve(bound_dead), resolve(bound_timer), resolve(bound_damageCooldown), startMarker);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    if (energy.slot == ReplaySlot::Detached) energy.value = bound_energy.value;
    if (lives.slot == ReplaySlot::Detached) lives.value = bound_lives.value;
    if (dead.slot == ReplaySlot::Detached) dead.value = bound_dead.value;
    if (timer.slot == ReplaySlot::Detached) timer.value = bound_timer.value;
    if (damageCooldown.slot == ReplaySlot::Detached) damageCooldown.value = bound_damageCooldown.value;
}
bool GameSession::replay_playerOverlapsTileArea(ReplayTarget<Player>& player, int tx0, int ty0, int tx1, int ty1) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto result = playerOverlapsTileArea(resolve(bound_player), tx0, ty0, tx1, ty1);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    return result;
}
void GameSession::replay_damagePlayersInTileArea(int tx0, int ty0, int tx1, int ty1) { damagePlayersInTileArea(tx0, ty0, tx1, ty1); }
void GameSession::replay_beginPlayerDeath(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, uint8_t startMarker) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto& bound_energy = bindDetachedAlias(energy, {});
    auto& bound_lives = bindDetachedAlias(lives, {{2, &bound_energy}});
    auto& bound_dead = bindDetachedAlias(dead, {});
    auto& bound_timer = bindDetachedAlias(timer, {{2, &bound_energy}, {3, &bound_lives}});
    beginPlayerDeath(resolve(bound_player), resolve(bound_energy), resolve(bound_lives), resolve(bound_dead), resolve(bound_timer), startMarker);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    if (energy.slot == ReplaySlot::Detached) energy.value = bound_energy.value;
    if (lives.slot == ReplaySlot::Detached) lives.value = bound_lives.value;
    if (dead.slot == ReplaySlot::Detached) dead.value = bound_dead.value;
    if (timer.slot == ReplaySlot::Detached) timer.value = bound_timer.value;
}
ReplayTarget<State2VisualCursor> GameSession::replay_state2VisualCursorFor(uint8_t startMarker) { return targetOf(&state2VisualCursorFor(startMarker)); }
ReplayTarget<State2EffectEntry> GameSession::replay_state2EffectEntryFor(uint8_t startMarker) { return targetOf(&state2EffectEntryFor(startMarker)); }
void GameSession::replay_refreshState2EffectEntry(ReplayTarget<Player>& player, ReplayTarget<State2VisualCursor>& cursor, ReplayTarget<State2EffectEntry>& entry) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto& bound_cursor = bindDetachedAlias(cursor, {});
    auto& bound_entry = bindDetachedAlias(entry, {});
    refreshState2EffectEntry(resolve(bound_player), resolve(bound_cursor), resolve(bound_entry));
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    if (cursor.slot == ReplaySlot::Detached) cursor.value = bound_cursor.value;
    if (entry.slot == ReplaySlot::Detached) entry.value = bound_entry.value;
}
void GameSession::replay_resetState2VisualCursor(ReplayTarget<State2VisualCursor>& cursor) {
    auto& bound_cursor = bindDetachedAlias(cursor, {});
    resetState2VisualCursor(resolve(bound_cursor));
    if (cursor.slot == ReplaySlot::Detached) cursor.value = bound_cursor.value;
}
bool GameSession::replay_updateState2VisualCursor(ReplayTarget<State2VisualCursor>& cursor) {
    auto& bound_cursor = bindDetachedAlias(cursor, {});
    auto result = updateState2VisualCursor(resolve(bound_cursor));
    if (cursor.slot == ReplaySlot::Detached) cursor.value = bound_cursor.value;
    return result;
}
bool GameSession::replay_allPlayersOutOfLives() { return allPlayersOutOfLives(); }
ReplayTarget<int> GameSession::replay_deathStateTimerFor(uint8_t startMarker) { return targetOf(&deathStateTimerFor(startMarker)); }
ReplayTarget<bool> GameSession::replay_pendingLifeLossFor(uint8_t startMarker) { return targetOf(&pendingLifeLossFor(startMarker)); }
void GameSession::replay_finalizePendingLifeLoss(ReplayTarget<bool>& dead, ReplayTarget<int>& lives, ReplayTarget<int>& timer, uint8_t startMarker) {
    auto& bound_dead = bindDetachedAlias(dead, {});
    auto& bound_lives = bindDetachedAlias(lives, {});
    auto& bound_timer = bindDetachedAlias(timer, {{2, &bound_lives}});
    finalizePendingLifeLoss(resolve(bound_dead), resolve(bound_lives), resolve(bound_timer), startMarker);
    if (dead.slot == ReplaySlot::Detached) dead.value = bound_dead.value;
    if (lives.slot == ReplaySlot::Detached) lives.value = bound_lives.value;
    if (timer.slot == ReplaySlot::Detached) timer.value = bound_timer.value;
}
bool GameSession::replay_canReenterLevel() { return canReenterLevel(); }
int GameSession::replay_remainingObjectiveTiles() { return remainingObjectiveTiles(); }
void GameSession::replay_updateWaitingPlayerPlacement(ReplayTarget<Player>& player) {
    auto& bound_player = bindDetachedAlias(player, {});
    updateWaitingPlayerPlacement(resolve(bound_player));
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
}
void GameSession::replay_updateReentry(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, uint8_t startMarker, bool allowLevelRestart) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto& bound_energy = bindDetachedAlias(energy, {});
    auto& bound_lives = bindDetachedAlias(lives, {{2, &bound_energy}});
    auto& bound_dead = bindDetachedAlias(dead, {});
    auto& bound_timer = bindDetachedAlias(timer, {{2, &bound_energy}, {3, &bound_lives}});
    updateReentry(resolve(bound_player), resolve(bound_energy), resolve(bound_lives), resolve(bound_dead), resolve(bound_timer), startMarker, allowLevelRestart);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    if (energy.slot == ReplaySlot::Detached) energy.value = bound_energy.value;
    if (lives.slot == ReplaySlot::Detached) lives.value = bound_lives.value;
    if (dead.slot == ReplaySlot::Detached) dead.value = bound_dead.value;
    if (timer.slot == ReplaySlot::Detached) timer.value = bound_timer.value;
}
uint8_t GameSession::replay_originalPlayerState(uint8_t player) { return originalPlayerState(player); }
bool GameSession::replay_updateSharedReentryFallback() { return updateSharedReentryFallback(); }
void GameSession::replay_tryReenterPlayer(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, ReplayTarget<int>& damageCooldown, uint8_t startMarker) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto& bound_energy = bindDetachedAlias(energy, {});
    auto& bound_lives = bindDetachedAlias(lives, {{2, &bound_energy}});
    auto& bound_dead = bindDetachedAlias(dead, {});
    auto& bound_timer = bindDetachedAlias(timer, {{2, &bound_energy}, {3, &bound_lives}});
    auto& bound_damageCooldown = bindDetachedAlias(damageCooldown, {{2, &bound_energy}, {3, &bound_lives}, {5, &bound_timer}});
    tryReenterPlayer(resolve(bound_player), resolve(bound_energy), resolve(bound_lives), resolve(bound_dead), resolve(bound_timer), resolve(bound_damageCooldown), startMarker);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    if (energy.slot == ReplaySlot::Detached) energy.value = bound_energy.value;
    if (lives.slot == ReplaySlot::Detached) lives.value = bound_lives.value;
    if (dead.slot == ReplaySlot::Detached) dead.value = bound_dead.value;
    if (timer.slot == ReplaySlot::Detached) timer.value = bound_timer.value;
    if (damageCooldown.slot == ReplaySlot::Detached) damageCooldown.value = bound_damageCooldown.value;
}
void GameSession::replay_respawnPlayerAtStart(ReplayTarget<Player>& player, ReplayTarget<int>& energy, uint8_t startMarker) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto& bound_energy = bindDetachedAlias(energy, {});
    respawnPlayerAtStart(resolve(bound_player), resolve(bound_energy), startMarker);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    if (energy.slot == ReplaySlot::Detached) energy.value = bound_energy.value;
}
void GameSession::replay_restartCurrentLevelAfterDeath() { restartCurrentLevelAfterDeath(); }
ReplayTarget<uint32_t> GameSession::replay_scoreForPlayer(uint8_t player) { return targetOf(&scoreForPlayer(player)); }
void GameSession::replay_addScore(uint8_t player, uint32_t amount) { addScore(player, amount); }
void GameSession::replay_clearRunScores() { clearRunScores(); }
bool GameSession::replay_isFinalLevel() { return isFinalLevel(); }
void GameSession::replay_placeBombAt(ReplayTarget<Player>& player, ReplayTarget<BombInventory>& inventory, uint8_t owner) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto& bound_inventory = bindDetachedAlias(inventory, {});
    placeBombAt(resolve(bound_player), resolve(bound_inventory), owner);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    if (inventory.slot == ReplaySlot::Detached) inventory.value = bound_inventory.value;
}
int GameSession::replay_bombHeightOffset(BombType type) { return bombHeightOffset(type); }
void GameSession::replay_updateBombMotion(ReplayTarget<Bomb>& bomb) {
    auto& bound_bomb = bindDetachedAlias(bomb, {});
    updateBombMotion(resolve(bound_bomb));
    if (bomb.slot == ReplaySlot::Detached) bomb.value = bound_bomb.value;
}
void GameSession::replay_updateTimedActorMotion(ReplayTarget<int>& x, ReplayTarget<int>& y, ReplayTarget<int16_t>& vx, ReplayTarget<int16_t>& vy, ReplayTarget<uint8_t>& fracX, ReplayTarget<uint8_t>& fracY, const ActiveMonster::EdgeFlags& edges) {
    auto& bound_x = bindDetachedAlias(x, {});
    auto& bound_y = bindDetachedAlias(y, {{1, &bound_x}});
    auto& bound_vx = bindDetachedAlias(vx, {});
    auto& bound_vy = bindDetachedAlias(vy, {{3, &bound_vx}});
    auto& bound_fracX = bindDetachedAlias(fracX, {});
    auto& bound_fracY = bindDetachedAlias(fracY, {{5, &bound_fracX}});
    updateTimedActorMotion(resolve(bound_x), resolve(bound_y), resolve(bound_vx), resolve(bound_vy), resolve(bound_fracX), resolve(bound_fracY), edges);
    if (x.slot == ReplaySlot::Detached) x.value = bound_x.value;
    if (y.slot == ReplaySlot::Detached) y.value = bound_y.value;
    if (vx.slot == ReplaySlot::Detached) vx.value = bound_vx.value;
    if (vy.slot == ReplaySlot::Detached) vy.value = bound_vy.value;
    if (fracX.slot == ReplaySlot::Detached) fracX.value = bound_fracX.value;
    if (fracY.slot == ReplaySlot::Detached) fracY.value = bound_fracY.value;
}
void GameSession::replay_updateBombs(uint64_t onlyOrder) { updateBombs(onlyOrder); }
std::vector<std::array<int, 2>> GameSession::replay_explosionTilesFor(ReplayTarget<Bomb>& bomb) {
    auto& bound_bomb = bindDetachedAlias(bomb, {});
    auto result = explosionTilesFor(resolve(bound_bomb));
    if (bomb.slot == ReplaySlot::Detached) bomb.value = bound_bomb.value;
    return result;
}
void GameSession::replay_spawnExplosionEffect(ReplayTarget<Bomb>& bomb) {
    auto& bound_bomb = bindDetachedAlias(bomb, {});
    spawnExplosionEffect(resolve(bound_bomb));
    if (bomb.slot == ReplaySlot::Detached) bomb.value = bound_bomb.value;
}
void GameSession::replay_seedFlameRecords(int cell, int type) { seedFlameRecords(cell, type); }
void GameSession::replay_updateFlameRecords() { updateFlameRecords(); }
bool GameSession::replay_isBombObjectTile(uint8_t tile) { return isBombObjectTile(tile); }
bool GameSession::replay_isHighBombObjectSoundTile(uint8_t tile) { return isHighBombObjectSoundTile(tile); }
bool GameSession::replay_isPassableObjectTile(uint8_t tile) { return isPassableObjectTile(tile); }
bool GameSession::replay_isPassableObjectCell(int tx, int ty) { return isPassableObjectCell(tx, ty); }
bool GameSession::replay_requestBombObjectScoreSound(bool sawHighObjectTile) { return requestBombObjectScoreSound(sawHighObjectTile); }
bool GameSession::replay_requestBombPlaceSound() { return requestBombPlaceSound(); }
bool GameSession::replay_requestMonsterDeathSound() { return requestMonsterDeathSound(); }
bool GameSession::replay_requestWeaponSwitchSound() { return requestWeaponSwitchSound(); }
bool GameSession::replay_requestLaunchPadSound() { return requestLaunchPadSound(); }
bool GameSession::replay_requestPortalTeleportSound() { return requestPortalTeleportSound(); }
bool GameSession::replay_requestTileTriggerSound() { return requestTileTriggerSound(); }
bool GameSession::replay_requestPlayerDamageSound() { return requestPlayerDamageSound(); }
bool GameSession::replay_requestPlayerDeathSound() { return requestPlayerDeathSound(); }
bool GameSession::replay_consumeBombObjectTile(int tx, int ty) { return consumeBombObjectTile(tx, ty); }
bool GameSession::replay_markDamagedTile(int tx, int ty) { return markDamagedTile(tx, ty); }
void GameSession::replay_queueTileDamage(int tx, int ty, uint8_t forwardPhase, uint8_t reversePhase, bool preserveCollapseGlyphs) { queueTileDamage(tx, ty, forwardPhase, reversePhase, preserveCollapseGlyphs); }
DamagePhaseLookup GameSession::replay_resolveDamagePhase(uint16_t flaggedWord, bool reverse) { return resolveDamagePhase(flaggedWord, reverse); }
void GameSession::replay_blendDebrisImpactLane(int target, uint16_t word, ReplayTarget<int>& velocity, bool reverse) {
    auto& bound_velocity = bindDetachedAlias(velocity, {});
    blendDebrisImpactLane(target, word, resolve(bound_velocity), reverse);
    if (velocity.slot == ReplaySlot::Detached) velocity.value = bound_velocity.value;
}
void GameSession::replay_explode(ReplayTarget<Bomb>& bomb) {
    auto& bound_bomb = bindDetachedAlias(bomb, {});
    explode(resolve(bound_bomb));
    if (bomb.slot == ReplaySlot::Detached) bomb.value = bound_bomb.value;
}
int GameSession::replay_monsterDamageForBomb(BombType type) { return monsterDamageForBomb(type); }
void GameSession::replay_damageMonstersInExplosion(const std::vector<std::array<int, 2>>& tiles, BombType type) { damageMonstersInExplosion(tiles, type); }
bool GameSession::replay_monsterOverlapsExplosionTiles(ReplayTarget<ActiveMonster>& monster, const std::vector<std::array<int, 2>>& tiles) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    auto result = monsterOverlapsExplosionTiles(resolve(bound_monster), tiles);
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
    return result;
}
bool GameSession::replay_rectsOverlap(float ax, float ay, float aw, float ah, float bx, float by, float bw, float bh) { return rectsOverlap(ax, ay, aw, ah, bx, by, bw, bh); }
void GameSession::replay_damageMonster(ReplayTarget<ActiveMonster>& monster, int damage, bool updatedThisTick) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    damageMonster(resolve(bound_monster), damage, updatedThisTick);
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
}
bool GameSession::replay_playerOverlapsAnyExplosionTile(ReplayTarget<Player>& player, const std::vector<std::array<int, 2>>& tiles) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto result = playerOverlapsAnyExplosionTile(resolve(bound_player), tiles);
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    return result;
}
void GameSession::replay_damagePlayersInExplosion(const std::vector<std::array<int, 2>>& tiles) { damagePlayersInExplosion(tiles); }
int GameSession::replay_monsterCorpseSprite(ReplayTarget<ActiveMonster>& monster) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    auto result = monsterCorpseSprite(resolve(bound_monster));
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
    return result;
}
void GameSession::replay_enterMonsterDeath(ReplayTarget<ActiveMonster>& monster, bool updatedThisTick) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    enterMonsterDeath(resolve(bound_monster), updatedThisTick);
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
}
void GameSession::replay_spawnBonusDrop(float x, float y, BonusType type) { spawnBonusDrop(x, y, type); }
void GameSession::replay_finishMonsterDeathReward(ReplayTarget<ActiveMonster>& monster) {
    auto& bound_monster = bindDetachedAlias(monster, {});
    finishMonsterDeathReward(resolve(bound_monster));
    if (monster.slot == ReplaySlot::Detached) monster.value = bound_monster.value;
}
void GameSession::replay_spawnExpiryParticles(int x, int y, int count) { spawnExpiryParticles(x, y, count); }
void GameSession::replay_updateBonusDrops(size_t initialDrops, uint64_t onlyOrder) { updateBonusDrops(initialDrops, onlyOrder); }
float GameSession::replay_bonusDistanceSq(ReplayTarget<Player>& player, ReplayTarget<BonusDrop>& drop) {
    auto& bound_player = bindDetachedAlias(player, {});
    auto& bound_drop = bindDetachedAlias(drop, {});
    auto result = bonusDistanceSq(resolve(bound_player), resolve(bound_drop));
    if (player.slot == ReplaySlot::Detached) player.value = bound_player.value;
    if (drop.slot == ReplaySlot::Detached) drop.value = bound_drop.value;
    return result;
}
void GameSession::replay_collectBonusDrop(ReplayTarget<BonusDrop>& drop, ReplayTarget<Player>& collector, ReplayTarget<int>& energy, ReplayTarget<BombInventory>& inventory, uint8_t playerIndex) {
    auto& bound_drop = bindDetachedAlias(drop, {});
    auto& bound_collector = bindDetachedAlias(collector, {});
    auto& bound_energy = bindDetachedAlias(energy, {});
    auto& bound_inventory = bindDetachedAlias(inventory, {});
    collectBonusDrop(resolve(bound_drop), resolve(bound_collector), resolve(bound_energy), resolve(bound_inventory), playerIndex);
    if (drop.slot == ReplaySlot::Detached) drop.value = bound_drop.value;
    if (collector.slot == ReplaySlot::Detached) collector.value = bound_collector.value;
    if (energy.slot == ReplaySlot::Detached) energy.value = bound_energy.value;
    if (inventory.slot == ReplaySlot::Detached) inventory.value = bound_inventory.value;
}
void GameSession::replay_applyBonus(BonusType type, ReplayTarget<Player>& collector, ReplayTarget<int>& energy, ReplayTarget<BombInventory>& inventory, uint8_t playerIndex) {
    auto& bound_collector = bindDetachedAlias(collector, {});
    auto& bound_energy = bindDetachedAlias(energy, {});
    auto& bound_inventory = bindDetachedAlias(inventory, {});
    applyBonus(type, resolve(bound_collector), resolve(bound_energy), resolve(bound_inventory), playerIndex);
    if (collector.slot == ReplaySlot::Detached) collector.value = bound_collector.value;
    if (energy.slot == ReplaySlot::Detached) energy.value = bound_energy.value;
    if (inventory.slot == ReplaySlot::Detached) inventory.value = bound_inventory.value;
}
void GameSession::replay_grantNormalBombSet(ReplayTarget<BombInventory>& inventory) {
    auto& bound_inventory = bindDetachedAlias(inventory, {});
    grantNormalBombSet(resolve(bound_inventory));
    if (inventory.slot == ReplaySlot::Detached) inventory.value = bound_inventory.value;
}
void GameSession::replay_grantSuperBombSet(ReplayTarget<BombInventory>& inventory) {
    auto& bound_inventory = bindDetachedAlias(inventory, {});
    grantSuperBombSet(resolve(bound_inventory));
    if (inventory.slot == ReplaySlot::Detached) inventory.value = bound_inventory.value;
}
void GameSession::replay_spawnBonusRain(ReplayTarget<Player>& collector) {
    auto& bound_collector = bindDetachedAlias(collector, {});
    spawnBonusRain(resolve(bound_collector));
    if (collector.slot == ReplaySlot::Detached) collector.value = bound_collector.value;
}
void GameSession::replay_updateDebrisRecords() { updateDebrisRecords(); }
void GameSession::replay_updateCollapseRecords() { updateCollapseRecords(); }
void GameSession::replay_updateFlashes() { updateFlashes(); }
int GameSession::replay_destructionPercent() { return destructionPercent(); }
bool GameSession::replay_isComplete() { return isComplete(); }
}
