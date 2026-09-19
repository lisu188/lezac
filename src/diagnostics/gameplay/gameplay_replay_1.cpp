#include "diagnostics/gameplay/gameplay_replay.hpp"
namespace lezac::diagnostics {
void GameplayReplay::resetLevel(int index) {

    beginCommand();
    session_.replay_resetLevel(index);
    finishCommand();

}

const LevelPortal* GameplayReplay::findStartPortal(uint8_t marker) const {

    beginCommand();
    auto result = session_.replay_findStartPortal(marker);
    finishCommand();

    return resolvePointer(result);
}

void GameplayReplay::tryActivePlayerFireAt(const Player& player, int x, int y, uint8_t playerIndex) {
    auto target_player = targetOf(&player);
    beginCommand();
    session_.replay_tryActivePlayerFireAt(target_player, x, y, playerIndex);
    finishCommand();

}

int GameplayReplay::tileAt(int tx, int ty) const {

    beginCommand();
    auto result = session_.replay_tileAt(tx, ty);
    finishCommand();

    return result;
}

uint16_t GameplayReplay::wordAt(int tx, int ty) const {

    beginCommand();
    auto result = session_.replay_wordAt(tx, ty);
    finishCommand();

    return result;
}

uint8_t& GameplayReplay::tileRef(int tx, int ty) {

    beginCommand();
    auto result = session_.replay_tileRef(tx, ty);
    finishCommand();

    return *resolvePointer(result);
}

uint16_t& GameplayReplay::wordRef(int tx, int ty) {

    beginCommand();
    auto result = session_.replay_wordRef(tx, ty);
    finishCommand();

    return *resolvePointer(result);
}

bool GameplayReplay::solidPixel(float px, float py) const {

    beginCommand();
    auto result = session_.replay_solidPixel(px, py);
    finishCommand();

    return result;
}

bool GameplayReplay::solidTileSide(uint8_t t) {

    beginCommand();
    auto result = session_.replay_solidTileSide(t);
    finishCommand();

    return result;
}

bool GameplayReplay::solidTileBottom(uint8_t t) {

    beginCommand();
    auto result = session_.replay_solidTileBottom(t);
    finishCommand();

    return result;
}

ActiveMonster::EdgeFlags GameplayReplay::scanActorEdges(int x, int yCollide) const {

    beginCommand();
    auto result = session_.replay_scanActorEdges(x, yCollide);
    finishCommand();

    return result;
}

bool GameplayReplay::scanActorStrongBottom(int x, int yCollide) const {

    beginCommand();
    auto result = session_.replay_scanActorStrongBottom(x, yCollide);
    finishCommand();

    return result;
}

bool GameplayReplay::collides(float x, float y) const {

    beginCommand();
    auto result = session_.replay_collides(x, y);
    finishCommand();

    return result;
}

bool GameplayReplay::monsterCollides(float x, float y) const {

    beginCommand();
    auto result = session_.replay_monsterCollides(x, y);
    finishCommand();

    return result;
}

bool GameplayReplay::playerOverlaps(const Player& player, float x, float y, float w, float h) const {
    auto target_player = targetOf(&player);
    beginCommand();
    auto result = session_.replay_playerOverlaps(target_player, x, y, w, h);
    finishCommand();

    return result;
}

int GameplayReplay::bombTypeIndex(BombType type) const {

    beginCommand();
    auto result = session_.replay_bombTypeIndex(type);
    finishCommand();

    return result;
}

int GameplayReplay::explosionVisualType(BombType type) const {

    beginCommand();
    auto result = session_.replay_explosionVisualType(type);
    finishCommand();

    return result;
}

uint8_t GameplayReplay::explosionDispatcherState(int visualSelector) const {

    beginCommand();
    auto result = session_.replay_explosionDispatcherState(visualSelector);
    finishCommand();

    return result;
}

int GameplayReplay::explosionEffectTicks(int visualType) const {

    beginCommand();
    auto result = session_.replay_explosionEffectTicks(visualType);
    finishCommand();

    return result;
}

uint8_t GameplayReplay::explosionVariantByte(int visualType) const {

    beginCommand();
    auto result = session_.replay_explosionVariantByte(visualType);
    finishCommand();

    return result;
}

uint16_t GameplayReplay::explosionSoundOffset(int visualType) const {

    beginCommand();
    auto result = session_.replay_explosionSoundOffset(visualType);
    finishCommand();

    return result;
}

uint8_t GameplayReplay::explosionSoundSelector(int visualType) const {

    beginCommand();
    auto result = session_.replay_explosionSoundSelector(visualType);
    finishCommand();

    return result;
}

bool GameplayReplay::hasBomb(const BombInventory& inventory, BombType type) const {
    auto target_inventory = targetOf(&inventory);
    beginCommand();
    auto result = session_.replay_hasBomb(target_inventory, type);
    finishCommand();

    return result;
}

void GameplayReplay::selectNextAvailableBomb(BombInventory& inventory) {
    auto target_inventory = targetOf(&inventory);
    beginCommand();
    session_.replay_selectNextAvailableBomb(target_inventory);
    finishCommand();
    if (target_inventory.slot == ReplaySlot::Detached) inventory = target_inventory.value;
}

void GameplayReplay::updateWeaponSwitch(BombInventory& inventory, uint8_t& holdTicks, bool pressed) {
    auto target_inventory = targetOf(&inventory);
    auto target_holdTicks = targetOf(&holdTicks);
    beginCommand();
    session_.replay_updateWeaponSwitch(target_inventory, target_holdTicks, pressed);
    finishCommand();
    if (target_inventory.slot == ReplaySlot::Detached) inventory = target_inventory.value;
    if (target_holdTicks.slot == ReplaySlot::Detached) holdTicks = target_holdTicks.value;
}

void GameplayReplay::updatePlayerReentryPrepass(const FrameControls& controls) {

    beginCommand();
    session_.replay_updatePlayerReentryPrepass(controls);
    finishCommand();

}

void GameplayReplay::updateWithControls(const FrameControls& controls, float dt) {

    beginCommand();
    session_.replay_updateWithControls(controls, dt);
    finishCommand();

}

bool GameplayReplay::activateLaunchPad(Player& player, bool down, int localY) {
    auto target_player = targetOf(&player);
    beginCommand();
    auto result = session_.replay_activateLaunchPad(target_player, down, localY);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
    return result;
}

void GameplayReplay::updateLaunchPadMarkers(uint64_t onlyOrder) {

    beginCommand();
    session_.replay_updateLaunchPadMarkers(onlyOrder);
    finishCommand();

}

void GameplayReplay::selectPlayerPosture(Player& player, uint8_t spriteBase, bool dropping) {
    auto target_player = targetOf(&player);
    beginCommand();
    session_.replay_selectPlayerPosture(target_player, spriteBase, dropping);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
}

void GameplayReplay::updatePlayerGravity(Player& player, bool bottom, uint8_t spriteBase, int& y) {
    auto target_player = targetOf(&player);
    auto target_y = targetOf(&y);
    beginCommand();
    session_.replay_updatePlayerGravity(target_player, bottom, spriteBase, target_y);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
    if (target_y.slot == ReplaySlot::Detached) y = target_y.value;
}

void GameplayReplay::updatePlayer(Player& player, bool left, bool right, bool jump, bool switchWeapon, uint8_t spriteBase, bool down) {
    auto target_player = targetOf(&player);
    beginCommand();
    session_.replay_updatePlayer(target_player, left, right, jump, switchWeapon, spriteBase, down);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
}

void GameplayReplay::applyPlayerTerrainDamage(Player& player, int& energy) {
    auto target_player = targetOf(&player);
    auto target_energy = targetOf(&energy);
    beginCommand();
    session_.replay_applyPlayerTerrainDamage(target_player, target_energy);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
    if (target_energy.slot == ReplaySlot::Detached) energy = target_energy.value;
}

void GameplayReplay::updateDyingPlayerMotion(Player& player) {
    auto target_player = targetOf(&player);
    beginCommand();
    session_.replay_updateDyingPlayerMotion(target_player);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
}

void GameplayReplay::integratePlayerMotion(Player& player, int x, int y, const ActiveMonster::EdgeFlags& edges) {
    auto target_player = targetOf(&player);
    beginCommand();
    session_.replay_integratePlayerMotion(target_player, x, y, edges);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
}

void GameplayReplay::syncPlayerVelocityMirror(Player& player) {
    auto target_player = targetOf(&player);
    beginCommand();
    session_.replay_syncPlayerVelocityMirror(target_player);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
}

int16_t GameplayReplay::actorFloorFriction(int16_t velocity) {

    beginCommand();
    auto result = session_.replay_actorFloorFriction(velocity);
    finishCommand();

    return result;
}

int16_t GameplayReplay::playerWalkVelocity(int16_t velocity, bool left, bool right, bool bottom) {

    beginCommand();
    auto result = session_.replay_playerWalkVelocity(velocity, left, right, bottom);
    finishCommand();

    return result;
}

std::vector<SharedActorEntry> GameplayReplay::sharedActorEntries() const {

    beginCommand();
    auto result = session_.replay_sharedActorEntries();
    finishCommand();

    return result;
}

uint64_t GameplayReplay::sharedActorVisualKey(const SharedActorEntry& entry) const {

    beginCommand();
    auto result = session_.replay_sharedActorVisualKey(entry);
    finishCommand();

    return result;
}

void GameplayReplay::adoptUnorderedActors() {

    beginCommand();
    session_.replay_adoptUnorderedActors();
    finishCommand();

}

uint64_t GameplayReplay::claimActorOrder() {

    beginCommand();
    auto result = session_.replay_claimActorOrder();
    finishCommand();

    return result;
}

void GameplayReplay::updateOrderedActors(float dt) {

    beginCommand();
    session_.replay_updateOrderedActors(dt);
    finishCommand();

}

size_t GameplayReplay::sharedActorCount() const {

    beginCommand();
    auto result = session_.replay_sharedActorCount();
    finishCommand();

    return result;
}

void GameplayReplay::updateCameraShake() {

    beginCommand();
    session_.replay_updateCameraShake();
    finishCommand();

}
}
