#include "gameplay/game_session.hpp"
namespace lezac::gameplay {
void GameSession::replay_resetLevel(int index) { resetLevel(index); }
ReplayTarget<LevelPortal> GameSession::replay_findStartPortal(uint8_t marker) { return targetOf(findStartPortal(marker)); }
void GameSession::replay_tryActivePlayerFireAt(ReplayTarget<Player>& player, int x, int y, uint8_t playerIndex) { tryActivePlayerFireAt(resolve(player), x, y, playerIndex); }
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
bool GameSession::replay_playerOverlaps(ReplayTarget<Player>& player, float x, float y, float w, float h) { return playerOverlaps(resolve(player), x, y, w, h); }
int GameSession::replay_bombTypeIndex(BombType type) { return bombTypeIndex(type); }
int GameSession::replay_explosionVisualType(BombType type) { return explosionVisualType(type); }
uint8_t GameSession::replay_explosionDispatcherState(int visualSelector) { return explosionDispatcherState(visualSelector); }
int GameSession::replay_explosionEffectTicks(int visualType) { return explosionEffectTicks(visualType); }
uint8_t GameSession::replay_explosionVariantByte(int visualType) { return explosionVariantByte(visualType); }
uint16_t GameSession::replay_explosionSoundOffset(int visualType) { return explosionSoundOffset(visualType); }
uint8_t GameSession::replay_explosionSoundSelector(int visualType) { return explosionSoundSelector(visualType); }
bool GameSession::replay_hasBomb(ReplayTarget<BombInventory>& inventory, BombType type) { return hasBomb(resolve(inventory), type); }
void GameSession::replay_selectNextAvailableBomb(ReplayTarget<BombInventory>& inventory) { selectNextAvailableBomb(resolve(inventory)); }
void GameSession::replay_updateWeaponSwitch(ReplayTarget<BombInventory>& inventory, ReplayTarget<uint8_t>& holdTicks, bool pressed) { updateWeaponSwitch(resolve(inventory), resolve(holdTicks), pressed); }
void GameSession::replay_updatePlayerReentryPrepass(const FrameControls& controls) { updatePlayerReentryPrepass(controls); }
void GameSession::replay_updateWithControls(const FrameControls& controls, float dt) { updateWithControls(controls, dt); }
bool GameSession::replay_activateLaunchPad(ReplayTarget<Player>& player, bool down, int localY) { return activateLaunchPad(resolve(player), down, localY); }
void GameSession::replay_updateLaunchPadMarkers(uint64_t onlyOrder) { updateLaunchPadMarkers(onlyOrder); }
void GameSession::replay_selectPlayerPosture(ReplayTarget<Player>& player, uint8_t spriteBase, bool dropping) { selectPlayerPosture(resolve(player), spriteBase, dropping); }
void GameSession::replay_updatePlayerGravity(ReplayTarget<Player>& player, bool bottom, uint8_t spriteBase, ReplayTarget<int>& y) { updatePlayerGravity(resolve(player), bottom, spriteBase, resolve(y)); }
void GameSession::replay_updatePlayer(ReplayTarget<Player>& player, bool left, bool right, bool jump, bool switchWeapon, uint8_t spriteBase, bool down) { updatePlayer(resolve(player), left, right, jump, switchWeapon, spriteBase, down); }
void GameSession::replay_applyPlayerTerrainDamage(ReplayTarget<Player>& player, ReplayTarget<int>& energy) { applyPlayerTerrainDamage(resolve(player), resolve(energy)); }
void GameSession::replay_updateDyingPlayerMotion(ReplayTarget<Player>& player) { updateDyingPlayerMotion(resolve(player)); }
void GameSession::replay_integratePlayerMotion(ReplayTarget<Player>& player, int x, int y, const ActiveMonster::EdgeFlags& edges) { integratePlayerMotion(resolve(player), x, y, edges); }
void GameSession::replay_syncPlayerVelocityMirror(ReplayTarget<Player>& player) { syncPlayerVelocityMirror(resolve(player)); }
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
void GameSession::replay_updateTransientActor(ReplayTarget<TransientActor>& actor) { updateTransientActor(resolve(actor)); }
void GameSession::replay_updateTransientActors() { updateTransientActors(); }
void GameSession::replay_collectObjectiveTiles(ReplayTarget<Player>& player, uint8_t playerIndex) { collectObjectiveTiles(resolve(player), playerIndex); }
void GameSession::replay_updatePortalsAndTriggers(ReplayTarget<Player>& player, ReplayTarget<int>& portalCooldown, ReplayTarget<int>& triggerCooldown, bool down) { updatePortalsAndTriggers(resolve(player), resolve(portalCooldown), resolve(triggerCooldown), down); }
bool GameSession::replay_applyTileTrigger(uint16_t key) { return applyTileTrigger(key); }
void GameSession::replay_accountTileRewrite(uint8_t from, uint8_t to) { accountTileRewrite(from, to); }
std::array<int, 2> GameSession::replay_monsterFrameRange(uint8_t kind) { return monsterFrameRange(kind); }
std::array<int, 2> GameSession::replay_monsterDirectionalFrameRange(uint8_t kind, int16_t vx8) { return monsterDirectionalFrameRange(kind, vx8); }
uint8_t GameSession::replay_monsterHotspotY(uint8_t kind) { return monsterHotspotY(kind); }
bool GameSession::replay_actorTouchesPlayer(ReplayTarget<Player>& player, int ax, int ayCollide) { return actorTouchesPlayer(resolve(player), ax, ayCollide); }
uint16_t GameSession::replay_randomRangeValue(uint16_t base, uint16_t range) { return randomRangeValue(base, range); }
int GameSession::replay_randomInclusive(int low, int high) { return randomInclusive(low, high); }
int16_t GameSession::replay_groundWalkerSpeed8(ReplayTarget<ActiveMonster>& monster) { return groundWalkerSpeed8(resolve(monster)); }
int16_t GameSession::replay_retargetSpeed8(ReplayTarget<ActiveMonster>& monster) { return retargetSpeed8(resolve(monster)); }
void GameSession::replay_refreshMonsterAnimationProfile(ReplayTarget<ActiveMonster>& monster) { refreshMonsterAnimationProfile(resolve(monster)); }
void GameSession::replay_reselectWalkerFacing(ReplayTarget<ActiveMonster>& monster) { reselectWalkerFacing(resolve(monster)); }
void GameSession::replay_initializeMonsterMotion(ReplayTarget<ActiveMonster>& monster) { initializeMonsterMotion(resolve(monster)); }
void GameSession::replay_retargetMonster(ReplayTarget<ActiveMonster>& monster) { retargetMonster(resolve(monster)); }
ReplayTarget<Player> GameSession::replay_nearestPlayer(float x, float y) { return targetOf(&nearestPlayer(x, y)); }
void GameSession::replay_updateMonsterMotion(ReplayTarget<ActiveMonster>& monster, float unused1) { updateMonsterMotion(resolve(monster), unused1); }
void GameSession::replay_spawnLevel7Boss() { spawnLevel7Boss(); }
ReplayTarget<ActiveMonster> GameSession::replay_findBossActorByVisual(uint8_t visual) { return targetOf(findBossActorByVisual(visual)); }
void GameSession::replay_updateBossLinks() { updateBossLinks(); }
void GameSession::replay_applyBossSegmentLinks(ReplayTarget<ActiveMonster>& monster) { applyBossSegmentLinks(resolve(monster)); }
bool GameSession::replay_isBossMotionBehavior(int behavior) { return isBossMotionBehavior(behavior); }
bool GameSession::replay_bossScanTileSolid(int index, int upper) { return bossScanTileSolid(index, upper); }
BossHeadEdges GameSession::replay_scanBossHeadEdges(ReplayTarget<ActiveMonster>& monster) { return scanBossHeadEdges(resolve(monster)); }
void GameSession::replay_updateBossHead(ReplayTarget<ActiveMonster>& monster) { updateBossHead(resolve(monster)); }
void GameSession::replay_damageBossHeadFromFlames(ReplayTarget<ActiveMonster>& monster) { damageBossHeadFromFlames(resolve(monster)); }
void GameSession::replay_bossDeathChain(ReplayTarget<ActiveMonster>& head) { bossDeathChain(resolve(head)); }
void GameSession::replay_updateMonsterSpawners() { updateMonsterSpawners(); }
void GameSession::replay_updateMonsters(float dt, uint64_t onlyOrder) { updateMonsters(dt, onlyOrder); }
void GameSession::replay_releaseMonsterSlot(ReplayTarget<ActiveMonster>& monster) { releaseMonsterSlot(resolve(monster)); }
void GameSession::replay_updateDamageCooldowns() { updateDamageCooldowns(); }
void GameSession::replay_queuePlayerDamage(uint8_t startMarker, uint8_t amount) { queuePlayerDamage(startMarker, amount); }
void GameSession::replay_drainPlayerDamageCounters() { drainPlayerDamageCounters(); }
void GameSession::replay_drainPlayerDamageCounter(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, ReplayTarget<uint8_t>& pending, uint8_t startMarker) { drainPlayerDamageCounter(resolve(player), resolve(energy), resolve(lives), resolve(dead), resolve(timer), resolve(pending), startMarker); }
void GameSession::replay_damagePlayer(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, ReplayTarget<int>& damageCooldown, uint8_t startMarker) { damagePlayer(resolve(player), resolve(energy), resolve(lives), resolve(dead), resolve(timer), resolve(damageCooldown), startMarker); }
bool GameSession::replay_playerOverlapsTileArea(ReplayTarget<Player>& player, int tx0, int ty0, int tx1, int ty1) { return playerOverlapsTileArea(resolve(player), tx0, ty0, tx1, ty1); }
void GameSession::replay_damagePlayersInTileArea(int tx0, int ty0, int tx1, int ty1) { damagePlayersInTileArea(tx0, ty0, tx1, ty1); }
void GameSession::replay_beginPlayerDeath(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, uint8_t startMarker) { beginPlayerDeath(resolve(player), resolve(energy), resolve(lives), resolve(dead), resolve(timer), startMarker); }
ReplayTarget<State2VisualCursor> GameSession::replay_state2VisualCursorFor(uint8_t startMarker) { return targetOf(&state2VisualCursorFor(startMarker)); }
ReplayTarget<State2EffectEntry> GameSession::replay_state2EffectEntryFor(uint8_t startMarker) { return targetOf(&state2EffectEntryFor(startMarker)); }
void GameSession::replay_refreshState2EffectEntry(ReplayTarget<Player>& player, ReplayTarget<State2VisualCursor>& cursor, ReplayTarget<State2EffectEntry>& entry) { refreshState2EffectEntry(resolve(player), resolve(cursor), resolve(entry)); }
void GameSession::replay_resetState2VisualCursor(ReplayTarget<State2VisualCursor>& cursor) { resetState2VisualCursor(resolve(cursor)); }
bool GameSession::replay_updateState2VisualCursor(ReplayTarget<State2VisualCursor>& cursor) { return updateState2VisualCursor(resolve(cursor)); }
bool GameSession::replay_allPlayersOutOfLives() { return allPlayersOutOfLives(); }
ReplayTarget<int> GameSession::replay_deathStateTimerFor(uint8_t startMarker) { return targetOf(&deathStateTimerFor(startMarker)); }
ReplayTarget<bool> GameSession::replay_pendingLifeLossFor(uint8_t startMarker) { return targetOf(&pendingLifeLossFor(startMarker)); }
void GameSession::replay_finalizePendingLifeLoss(ReplayTarget<bool>& dead, ReplayTarget<int>& lives, ReplayTarget<int>& timer, uint8_t startMarker) { finalizePendingLifeLoss(resolve(dead), resolve(lives), resolve(timer), startMarker); }
bool GameSession::replay_canReenterLevel() { return canReenterLevel(); }
int GameSession::replay_remainingObjectiveTiles() { return remainingObjectiveTiles(); }
void GameSession::replay_updateWaitingPlayerPlacement(ReplayTarget<Player>& player) { updateWaitingPlayerPlacement(resolve(player)); }
void GameSession::replay_updateReentry(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, uint8_t startMarker, bool allowLevelRestart) { updateReentry(resolve(player), resolve(energy), resolve(lives), resolve(dead), resolve(timer), startMarker, allowLevelRestart); }
uint8_t GameSession::replay_originalPlayerState(uint8_t player) { return originalPlayerState(player); }
bool GameSession::replay_updateSharedReentryFallback() { return updateSharedReentryFallback(); }
void GameSession::replay_tryReenterPlayer(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, ReplayTarget<int>& damageCooldown, uint8_t startMarker) { tryReenterPlayer(resolve(player), resolve(energy), resolve(lives), resolve(dead), resolve(timer), resolve(damageCooldown), startMarker); }
void GameSession::replay_respawnPlayerAtStart(ReplayTarget<Player>& player, ReplayTarget<int>& energy, uint8_t startMarker) { respawnPlayerAtStart(resolve(player), resolve(energy), startMarker); }
void GameSession::replay_restartCurrentLevelAfterDeath() { restartCurrentLevelAfterDeath(); }
ReplayTarget<uint32_t> GameSession::replay_scoreForPlayer(uint8_t player) { return targetOf(&scoreForPlayer(player)); }
void GameSession::replay_addScore(uint8_t player, uint32_t amount) { addScore(player, amount); }
void GameSession::replay_clearRunScores() { clearRunScores(); }
bool GameSession::replay_isFinalLevel() { return isFinalLevel(); }
void GameSession::replay_placeBombAt(ReplayTarget<Player>& player, ReplayTarget<BombInventory>& inventory, uint8_t owner) { placeBombAt(resolve(player), resolve(inventory), owner); }
int GameSession::replay_bombHeightOffset(BombType type) { return bombHeightOffset(type); }
void GameSession::replay_updateBombMotion(ReplayTarget<Bomb>& bomb) { updateBombMotion(resolve(bomb)); }
void GameSession::replay_updateTimedActorMotion(ReplayTarget<int>& x, ReplayTarget<int>& y, ReplayTarget<int16_t>& vx, ReplayTarget<int16_t>& vy, ReplayTarget<uint8_t>& fracX, ReplayTarget<uint8_t>& fracY, const ActiveMonster::EdgeFlags& edges) { updateTimedActorMotion(resolve(x), resolve(y), resolve(vx), resolve(vy), resolve(fracX), resolve(fracY), edges); }
void GameSession::replay_updateBombs(uint64_t onlyOrder) { updateBombs(onlyOrder); }
std::vector<std::array<int, 2>> GameSession::replay_explosionTilesFor(ReplayTarget<Bomb>& bomb) { return explosionTilesFor(resolve(bomb)); }
void GameSession::replay_spawnExplosionEffect(ReplayTarget<Bomb>& bomb) { spawnExplosionEffect(resolve(bomb)); }
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
void GameSession::replay_blendDebrisImpactLane(int target, uint16_t word, ReplayTarget<int>& velocity, bool reverse) { blendDebrisImpactLane(target, word, resolve(velocity), reverse); }
void GameSession::replay_explode(ReplayTarget<Bomb>& bomb) { explode(resolve(bomb)); }
int GameSession::replay_monsterDamageForBomb(BombType type) { return monsterDamageForBomb(type); }
void GameSession::replay_damageMonstersInExplosion(const std::vector<std::array<int, 2>>& tiles, BombType type) { damageMonstersInExplosion(tiles, type); }
bool GameSession::replay_monsterOverlapsExplosionTiles(ReplayTarget<ActiveMonster>& monster, const std::vector<std::array<int, 2>>& tiles) { return monsterOverlapsExplosionTiles(resolve(monster), tiles); }
bool GameSession::replay_rectsOverlap(float ax, float ay, float aw, float ah, float bx, float by, float bw, float bh) { return rectsOverlap(ax, ay, aw, ah, bx, by, bw, bh); }
void GameSession::replay_damageMonster(ReplayTarget<ActiveMonster>& monster, int damage, bool updatedThisTick) { damageMonster(resolve(monster), damage, updatedThisTick); }
bool GameSession::replay_playerOverlapsAnyExplosionTile(ReplayTarget<Player>& player, const std::vector<std::array<int, 2>>& tiles) { return playerOverlapsAnyExplosionTile(resolve(player), tiles); }
void GameSession::replay_damagePlayersInExplosion(const std::vector<std::array<int, 2>>& tiles) { damagePlayersInExplosion(tiles); }
int GameSession::replay_monsterCorpseSprite(ReplayTarget<ActiveMonster>& monster) { return monsterCorpseSprite(resolve(monster)); }
void GameSession::replay_enterMonsterDeath(ReplayTarget<ActiveMonster>& monster, bool updatedThisTick) { enterMonsterDeath(resolve(monster), updatedThisTick); }
void GameSession::replay_spawnBonusDrop(float x, float y, BonusType type) { spawnBonusDrop(x, y, type); }
void GameSession::replay_finishMonsterDeathReward(ReplayTarget<ActiveMonster>& monster) { finishMonsterDeathReward(resolve(monster)); }
void GameSession::replay_spawnExpiryParticles(int x, int y, int count) { spawnExpiryParticles(x, y, count); }
void GameSession::replay_updateBonusDrops(size_t initialDrops, uint64_t onlyOrder) { updateBonusDrops(initialDrops, onlyOrder); }
float GameSession::replay_bonusDistanceSq(ReplayTarget<Player>& player, ReplayTarget<BonusDrop>& drop) { return bonusDistanceSq(resolve(player), resolve(drop)); }
void GameSession::replay_collectBonusDrop(ReplayTarget<BonusDrop>& drop, ReplayTarget<Player>& collector, ReplayTarget<int>& energy, ReplayTarget<BombInventory>& inventory, uint8_t playerIndex) { collectBonusDrop(resolve(drop), resolve(collector), resolve(energy), resolve(inventory), playerIndex); }
void GameSession::replay_applyBonus(BonusType type, ReplayTarget<Player>& collector, ReplayTarget<int>& energy, ReplayTarget<BombInventory>& inventory, uint8_t playerIndex) { applyBonus(type, resolve(collector), resolve(energy), resolve(inventory), playerIndex); }
void GameSession::replay_grantNormalBombSet(ReplayTarget<BombInventory>& inventory) { grantNormalBombSet(resolve(inventory)); }
void GameSession::replay_grantSuperBombSet(ReplayTarget<BombInventory>& inventory) { grantSuperBombSet(resolve(inventory)); }
void GameSession::replay_spawnBonusRain(ReplayTarget<Player>& collector) { spawnBonusRain(resolve(collector)); }
void GameSession::replay_updateDebrisRecords() { updateDebrisRecords(); }
void GameSession::replay_updateCollapseRecords() { updateCollapseRecords(); }
void GameSession::replay_updateFlashes() { updateFlashes(); }
int GameSession::replay_destructionPercent() { return destructionPercent(); }
bool GameSession::replay_isComplete() { return isComplete(); }
}
