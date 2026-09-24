#include "diagnostics/gameplay/gameplay_replay.hpp"
namespace lezac::diagnostics {
void GameplayReplay::refreshState2EffectEntry(const Player& player, const State2VisualCursor& cursor, State2EffectEntry& entry) {
    auto target_player = targetOf(&player);
    auto target_cursor = targetOf(&cursor);
    auto target_entry = targetOf(&entry);
    beginCommand();
    session_.replay_refreshState2EffectEntry(target_player, target_cursor, target_entry);
    finishCommand();
    if (target_entry.slot == ReplaySlot::Detached) entry = target_entry.value;
}

void GameplayReplay::resetState2VisualCursor(State2VisualCursor& cursor) {
    auto target_cursor = targetOf(&cursor);
    beginCommand();
    session_.replay_resetState2VisualCursor(target_cursor);
    finishCommand();
    if (target_cursor.slot == ReplaySlot::Detached) cursor = target_cursor.value;
}

bool GameplayReplay::updateState2VisualCursor(State2VisualCursor& cursor) {
    auto target_cursor = targetOf(&cursor);
    beginCommand();
    auto result = session_.replay_updateState2VisualCursor(target_cursor);
    finishCommand();
    if (target_cursor.slot == ReplaySlot::Detached) cursor = target_cursor.value;
    return result;
}

bool GameplayReplay::allPlayersOutOfLives() const {

    beginCommand();
    auto result = session_.replay_allPlayersOutOfLives();
    finishCommand();

    return result;
}

int& GameplayReplay::deathStateTimerFor(uint8_t startMarker) {

    beginCommand();
    auto result = session_.replay_deathStateTimerFor(startMarker);
    finishCommand();

    return *resolvePointer(result);
}

bool& GameplayReplay::pendingLifeLossFor(uint8_t startMarker) {

    beginCommand();
    auto result = session_.replay_pendingLifeLossFor(startMarker);
    finishCommand();

    return *resolvePointer(result);
}

void GameplayReplay::finalizePendingLifeLoss(bool& dead, int& lives, int& timer, uint8_t startMarker) {
    auto target_dead = targetOf(&dead);
    auto target_lives = targetOf(&lives);
    auto target_timer = targetOf(&timer);
    if (target_timer.slot == ReplaySlot::Detached && target_lives.slot == ReplaySlot::Detached &&
        target_timer.detachedAlias == 0 && &timer == &lives) target_timer.detachedAlias = 2;
    beginCommand();
    session_.replay_finalizePendingLifeLoss(target_dead, target_lives, target_timer, startMarker);
    finishCommand();
    if (target_dead.slot == ReplaySlot::Detached) dead = target_dead.value;
    if (target_lives.slot == ReplaySlot::Detached) lives = target_lives.value;
    if (target_timer.slot == ReplaySlot::Detached) timer = target_timer.value;
}

bool GameplayReplay::canReenterLevel() const {

    beginCommand();
    auto result = session_.replay_canReenterLevel();
    finishCommand();

    return result;
}

int GameplayReplay::remainingObjectiveTiles() const {

    beginCommand();
    auto result = session_.replay_remainingObjectiveTiles();
    finishCommand();

    return result;
}

void GameplayReplay::updateWaitingPlayerPlacement(Player& player) {
    auto target_player = targetOf(&player);
    beginCommand();
    session_.replay_updateWaitingPlayerPlacement(target_player);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
}

void GameplayReplay::updateReentry(Player& player, int& energy, int& lives, bool& dead, int& timer, uint8_t startMarker, bool allowLevelRestart) {
    auto target_player = targetOf(&player);
    auto target_energy = targetOf(&energy);
    auto target_lives = targetOf(&lives);
    auto target_dead = targetOf(&dead);
    auto target_timer = targetOf(&timer);
    if (target_lives.slot == ReplaySlot::Detached && target_energy.slot == ReplaySlot::Detached &&
        target_lives.detachedAlias == 0 && &lives == &energy) target_lives.detachedAlias = 2;
    if (target_timer.slot == ReplaySlot::Detached && target_energy.slot == ReplaySlot::Detached &&
        target_timer.detachedAlias == 0 && &timer == &energy) target_timer.detachedAlias = 2;
    if (target_timer.slot == ReplaySlot::Detached && target_lives.slot == ReplaySlot::Detached &&
        target_timer.detachedAlias == 0 && &timer == &lives) target_timer.detachedAlias = 3;
    beginCommand();
    session_.replay_updateReentry(target_player, target_energy, target_lives, target_dead, target_timer, startMarker, allowLevelRestart);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
    if (target_energy.slot == ReplaySlot::Detached) energy = target_energy.value;
    if (target_lives.slot == ReplaySlot::Detached) lives = target_lives.value;
    if (target_dead.slot == ReplaySlot::Detached) dead = target_dead.value;
    if (target_timer.slot == ReplaySlot::Detached) timer = target_timer.value;
}

uint8_t GameplayReplay::originalPlayerState(uint8_t player) const {

    beginCommand();
    auto result = session_.replay_originalPlayerState(player);
    finishCommand();

    return result;
}

bool GameplayReplay::updateSharedReentryFallback() {

    beginCommand();
    auto result = session_.replay_updateSharedReentryFallback();
    finishCommand();

    return result;
}

void GameplayReplay::tryReenterPlayer(Player& player, int& energy, int& lives, bool& dead, int& timer, int& damageCooldown, uint8_t startMarker) {
    auto target_player = targetOf(&player);
    auto target_energy = targetOf(&energy);
    auto target_lives = targetOf(&lives);
    auto target_dead = targetOf(&dead);
    auto target_timer = targetOf(&timer);
    auto target_damageCooldown = targetOf(&damageCooldown);
    if (target_lives.slot == ReplaySlot::Detached && target_energy.slot == ReplaySlot::Detached &&
        target_lives.detachedAlias == 0 && &lives == &energy) target_lives.detachedAlias = 2;
    if (target_timer.slot == ReplaySlot::Detached && target_energy.slot == ReplaySlot::Detached &&
        target_timer.detachedAlias == 0 && &timer == &energy) target_timer.detachedAlias = 2;
    if (target_timer.slot == ReplaySlot::Detached && target_lives.slot == ReplaySlot::Detached &&
        target_timer.detachedAlias == 0 && &timer == &lives) target_timer.detachedAlias = 3;
    if (target_damageCooldown.slot == ReplaySlot::Detached && target_energy.slot == ReplaySlot::Detached &&
        target_damageCooldown.detachedAlias == 0 && &damageCooldown == &energy) target_damageCooldown.detachedAlias = 2;
    if (target_damageCooldown.slot == ReplaySlot::Detached && target_lives.slot == ReplaySlot::Detached &&
        target_damageCooldown.detachedAlias == 0 && &damageCooldown == &lives) target_damageCooldown.detachedAlias = 3;
    if (target_damageCooldown.slot == ReplaySlot::Detached && target_timer.slot == ReplaySlot::Detached &&
        target_damageCooldown.detachedAlias == 0 && &damageCooldown == &timer) target_damageCooldown.detachedAlias = 5;
    beginCommand();
    session_.replay_tryReenterPlayer(target_player, target_energy, target_lives, target_dead, target_timer, target_damageCooldown, startMarker);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
    if (target_energy.slot == ReplaySlot::Detached) energy = target_energy.value;
    if (target_lives.slot == ReplaySlot::Detached) lives = target_lives.value;
    if (target_dead.slot == ReplaySlot::Detached) dead = target_dead.value;
    if (target_timer.slot == ReplaySlot::Detached) timer = target_timer.value;
    if (target_damageCooldown.slot == ReplaySlot::Detached) damageCooldown = target_damageCooldown.value;
}

void GameplayReplay::respawnPlayerAtStart(Player& player, int& energy, uint8_t startMarker) {
    auto target_player = targetOf(&player);
    auto target_energy = targetOf(&energy);
    beginCommand();
    session_.replay_respawnPlayerAtStart(target_player, target_energy, startMarker);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
    if (target_energy.slot == ReplaySlot::Detached) energy = target_energy.value;
}

void GameplayReplay::restartCurrentLevelAfterDeath() {

    beginCommand();
    session_.replay_restartCurrentLevelAfterDeath();
    finishCommand();

}

uint32_t& GameplayReplay::scoreForPlayer(uint8_t player) {

    beginCommand();
    auto result = session_.replay_scoreForPlayer(player);
    finishCommand();

    return *resolvePointer(result);
}

void GameplayReplay::addScore(uint8_t player, uint32_t amount) {

    beginCommand();
    session_.replay_addScore(player, amount);
    finishCommand();

}

void GameplayReplay::clearRunScores() {

    beginCommand();
    session_.replay_clearRunScores();
    finishCommand();

}

bool GameplayReplay::isFinalLevel() const {

    beginCommand();
    auto result = session_.replay_isFinalLevel();
    finishCommand();

    return result;
}

void GameplayReplay::placeBombAt(const Player& player, BombInventory& inventory, uint8_t owner) {
    auto target_player = targetOf(&player);
    auto target_inventory = targetOf(&inventory);
    beginCommand();
    session_.replay_placeBombAt(target_player, target_inventory, owner);
    finishCommand();
    if (target_inventory.slot == ReplaySlot::Detached) inventory = target_inventory.value;
}

int GameplayReplay::bombHeightOffset(BombType type) const {

    beginCommand();
    auto result = session_.replay_bombHeightOffset(type);
    finishCommand();

    return result;
}

void GameplayReplay::updateBombMotion(Bomb& bomb) {
    auto target_bomb = targetOf(&bomb);
    beginCommand();
    session_.replay_updateBombMotion(target_bomb);
    finishCommand();
    if (target_bomb.slot == ReplaySlot::Detached) bomb = target_bomb.value;
}

void GameplayReplay::updateTimedActorMotion(int& x, int& y, int16_t& vx, int16_t& vy, uint8_t& fracX, uint8_t& fracY, const ActiveMonster::EdgeFlags& edges) {
    auto target_x = targetOf(&x);
    auto target_y = targetOf(&y);
    auto target_vx = targetOf(&vx);
    auto target_vy = targetOf(&vy);
    auto target_fracX = targetOf(&fracX);
    auto target_fracY = targetOf(&fracY);
    if (target_y.slot == ReplaySlot::Detached && target_x.slot == ReplaySlot::Detached &&
        target_y.detachedAlias == 0 && &y == &x) target_y.detachedAlias = 1;
    if (target_vy.slot == ReplaySlot::Detached && target_vx.slot == ReplaySlot::Detached &&
        target_vy.detachedAlias == 0 && &vy == &vx) target_vy.detachedAlias = 3;
    if (target_fracY.slot == ReplaySlot::Detached && target_fracX.slot == ReplaySlot::Detached &&
        target_fracY.detachedAlias == 0 && &fracY == &fracX) target_fracY.detachedAlias = 5;
    beginCommand();
    session_.replay_updateTimedActorMotion(target_x, target_y, target_vx, target_vy, target_fracX, target_fracY, edges);
    finishCommand();
    if (target_x.slot == ReplaySlot::Detached) x = target_x.value;
    if (target_y.slot == ReplaySlot::Detached) y = target_y.value;
    if (target_vx.slot == ReplaySlot::Detached) vx = target_vx.value;
    if (target_vy.slot == ReplaySlot::Detached) vy = target_vy.value;
    if (target_fracX.slot == ReplaySlot::Detached) fracX = target_fracX.value;
    if (target_fracY.slot == ReplaySlot::Detached) fracY = target_fracY.value;
}

void GameplayReplay::updateBombs(uint64_t onlyOrder) {

    beginCommand();
    session_.replay_updateBombs(onlyOrder);
    finishCommand();

}

std::vector<std::array<int, 2>> GameplayReplay::explosionTilesFor(const Bomb& bomb) const {
    auto target_bomb = targetOf(&bomb);
    beginCommand();
    auto result = session_.replay_explosionTilesFor(target_bomb);
    finishCommand();

    return result;
}

void GameplayReplay::spawnExplosionEffect(const Bomb& bomb) {
    auto target_bomb = targetOf(&bomb);
    beginCommand();
    session_.replay_spawnExplosionEffect(target_bomb);
    finishCommand();

}

void GameplayReplay::seedFlameRecords(int cell, int type) {

    beginCommand();
    session_.replay_seedFlameRecords(cell, type);
    finishCommand();

}

void GameplayReplay::updateFlameRecords() {

    beginCommand();
    session_.replay_updateFlameRecords();
    finishCommand();

}

bool GameplayReplay::isBombObjectTile(uint8_t tile) const {

    beginCommand();
    auto result = session_.replay_isBombObjectTile(tile);
    finishCommand();

    return result;
}

bool GameplayReplay::isHighBombObjectSoundTile(uint8_t tile) const {

    beginCommand();
    auto result = session_.replay_isHighBombObjectSoundTile(tile);
    finishCommand();

    return result;
}

bool GameplayReplay::isPassableObjectTile(uint8_t tile) const {

    beginCommand();
    auto result = session_.replay_isPassableObjectTile(tile);
    finishCommand();

    return result;
}

bool GameplayReplay::isPassableObjectCell(int tx, int ty) const {

    beginCommand();
    auto result = session_.replay_isPassableObjectCell(tx, ty);
    finishCommand();

    return result;
}

bool GameplayReplay::requestBombObjectScoreSound(bool sawHighObjectTile) {

    beginCommand();
    auto result = session_.replay_requestBombObjectScoreSound(sawHighObjectTile);
    finishCommand();

    return result;
}

bool GameplayReplay::requestBombPlaceSound() {

    beginCommand();
    auto result = session_.replay_requestBombPlaceSound();
    finishCommand();

    return result;
}

bool GameplayReplay::requestMonsterDeathSound() {

    beginCommand();
    auto result = session_.replay_requestMonsterDeathSound();
    finishCommand();

    return result;
}

bool GameplayReplay::requestWeaponSwitchSound() {

    beginCommand();
    auto result = session_.replay_requestWeaponSwitchSound();
    finishCommand();

    return result;
}

bool GameplayReplay::requestLaunchPadSound() {

    beginCommand();
    auto result = session_.replay_requestLaunchPadSound();
    finishCommand();

    return result;
}

bool GameplayReplay::requestPortalTeleportSound() {

    beginCommand();
    auto result = session_.replay_requestPortalTeleportSound();
    finishCommand();

    return result;
}

bool GameplayReplay::requestTileTriggerSound() {

    beginCommand();
    auto result = session_.replay_requestTileTriggerSound();
    finishCommand();

    return result;
}

bool GameplayReplay::requestPlayerDamageSound() {

    beginCommand();
    auto result = session_.replay_requestPlayerDamageSound();
    finishCommand();

    return result;
}

bool GameplayReplay::requestPlayerDeathSound() {

    beginCommand();
    auto result = session_.replay_requestPlayerDeathSound();
    finishCommand();

    return result;
}

bool GameplayReplay::consumeBombObjectTile(int tx, int ty) {

    beginCommand();
    auto result = session_.replay_consumeBombObjectTile(tx, ty);
    finishCommand();

    return result;
}

bool GameplayReplay::markDamagedTile(int tx, int ty) {

    beginCommand();
    auto result = session_.replay_markDamagedTile(tx, ty);
    finishCommand();

    return result;
}

void GameplayReplay::queueTileDamage(int tx, int ty, uint8_t forwardPhase, uint8_t reversePhase, bool preserveCollapseGlyphs) {

    beginCommand();
    session_.replay_queueTileDamage(tx, ty, forwardPhase, reversePhase, preserveCollapseGlyphs);
    finishCommand();

}
}
