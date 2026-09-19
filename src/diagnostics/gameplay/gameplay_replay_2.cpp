#include "diagnostics/gameplay/gameplay_replay.hpp"
namespace lezac::diagnostics {
size_t GameplayReplay::pickupActorCount() const {

    beginCommand();
    auto result = session_.replay_pickupActorCount();
    finishCommand();

    return result;
}

TransientActor* GameplayReplay::spawnTransientActor(int x, int y, int16_t vy8, uint8_t sprite, uint8_t kind, uint8_t timer, ActorAnimation animation) {

    beginCommand();
    auto result = session_.replay_spawnTransientActor(x, y, vy8, sprite, kind, timer, animation);
    finishCommand();

    return resolvePointer(result);
}

void GameplayReplay::updateTransientActor(TransientActor& actor) {
    auto target_actor = targetOf(&actor);
    beginCommand();
    session_.replay_updateTransientActor(target_actor);
    finishCommand();
    if (target_actor.slot == ReplaySlot::Detached) actor = target_actor.value;
}

void GameplayReplay::updateTransientActors() {

    beginCommand();
    session_.replay_updateTransientActors();
    finishCommand();

}

void GameplayReplay::collectObjectiveTiles(const Player& player, uint8_t playerIndex) {
    auto target_player = targetOf(&player);
    beginCommand();
    session_.replay_collectObjectiveTiles(target_player, playerIndex);
    finishCommand();

}

void GameplayReplay::updatePortalsAndTriggers(Player& player, int& portalCooldown, int& triggerCooldown, bool down) {
    auto target_player = targetOf(&player);
    auto target_portalCooldown = targetOf(&portalCooldown);
    auto target_triggerCooldown = targetOf(&triggerCooldown);
    beginCommand();
    session_.replay_updatePortalsAndTriggers(target_player, target_portalCooldown, target_triggerCooldown, down);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
    if (target_portalCooldown.slot == ReplaySlot::Detached) portalCooldown = target_portalCooldown.value;
    if (target_triggerCooldown.slot == ReplaySlot::Detached) triggerCooldown = target_triggerCooldown.value;
}

bool GameplayReplay::applyTileTrigger(uint16_t key) {

    beginCommand();
    auto result = session_.replay_applyTileTrigger(key);
    finishCommand();

    return result;
}

void GameplayReplay::accountTileRewrite(uint8_t from, uint8_t to) {

    beginCommand();
    session_.replay_accountTileRewrite(from, to);
    finishCommand();

}

std::array<int, 2> GameplayReplay::monsterFrameRange(uint8_t kind) const {

    beginCommand();
    auto result = session_.replay_monsterFrameRange(kind);
    finishCommand();

    return result;
}

std::array<int, 2> GameplayReplay::monsterDirectionalFrameRange(uint8_t kind, int16_t vx8) const {

    beginCommand();
    auto result = session_.replay_monsterDirectionalFrameRange(kind, vx8);
    finishCommand();

    return result;
}

uint8_t GameplayReplay::monsterHotspotY(uint8_t kind) {

    beginCommand();
    auto result = session_.replay_monsterHotspotY(kind);
    finishCommand();

    return result;
}

bool GameplayReplay::actorTouchesPlayer(const Player& player, int ax, int ayCollide) const {
    auto target_player = targetOf(&player);
    beginCommand();
    auto result = session_.replay_actorTouchesPlayer(target_player, ax, ayCollide);
    finishCommand();

    return result;
}

uint16_t GameplayReplay::randomRangeValue(uint16_t base, uint16_t range) {

    beginCommand();
    auto result = session_.replay_randomRangeValue(base, range);
    finishCommand();

    return result;
}

int GameplayReplay::randomInclusive(int low, int high) {

    beginCommand();
    auto result = session_.replay_randomInclusive(low, high);
    finishCommand();

    return result;
}

int16_t GameplayReplay::groundWalkerSpeed8(const ActiveMonster& monster) const {
    auto target_monster = targetOf(&monster);
    beginCommand();
    auto result = session_.replay_groundWalkerSpeed8(target_monster);
    finishCommand();

    return result;
}

int16_t GameplayReplay::retargetSpeed8(const ActiveMonster& monster) const {
    auto target_monster = targetOf(&monster);
    beginCommand();
    auto result = session_.replay_retargetSpeed8(target_monster);
    finishCommand();

    return result;
}

void GameplayReplay::refreshMonsterAnimationProfile(ActiveMonster& monster) {
    auto target_monster = targetOf(&monster);
    beginCommand();
    session_.replay_refreshMonsterAnimationProfile(target_monster);
    finishCommand();
    if (target_monster.slot == ReplaySlot::Detached) monster = target_monster.value;
}

void GameplayReplay::reselectWalkerFacing(ActiveMonster& monster) {
    auto target_monster = targetOf(&monster);
    beginCommand();
    session_.replay_reselectWalkerFacing(target_monster);
    finishCommand();
    if (target_monster.slot == ReplaySlot::Detached) monster = target_monster.value;
}

void GameplayReplay::initializeMonsterMotion(ActiveMonster& monster) {
    auto target_monster = targetOf(&monster);
    beginCommand();
    session_.replay_initializeMonsterMotion(target_monster);
    finishCommand();
    if (target_monster.slot == ReplaySlot::Detached) monster = target_monster.value;
}

void GameplayReplay::retargetMonster(ActiveMonster& monster) {
    auto target_monster = targetOf(&monster);
    beginCommand();
    session_.replay_retargetMonster(target_monster);
    finishCommand();
    if (target_monster.slot == ReplaySlot::Detached) monster = target_monster.value;
}

const Player& GameplayReplay::nearestPlayer(float x, float y) const {

    beginCommand();
    auto result = session_.replay_nearestPlayer(x, y);
    finishCommand();

    return *resolvePointer(result);
}

void GameplayReplay::updateMonsterMotion(ActiveMonster& monster, float unused1) {
    auto target_monster = targetOf(&monster);
    beginCommand();
    session_.replay_updateMonsterMotion(target_monster, unused1);
    finishCommand();
    if (target_monster.slot == ReplaySlot::Detached) monster = target_monster.value;
}

void GameplayReplay::spawnLevel7Boss() {

    beginCommand();
    session_.replay_spawnLevel7Boss();
    finishCommand();

}

ActiveMonster* GameplayReplay::findBossActorByVisual(uint8_t visual) {

    beginCommand();
    auto result = session_.replay_findBossActorByVisual(visual);
    finishCommand();

    return resolvePointer(result);
}

void GameplayReplay::updateBossLinks() {

    beginCommand();
    session_.replay_updateBossLinks();
    finishCommand();

}

void GameplayReplay::applyBossSegmentLinks(ActiveMonster& monster) {
    auto target_monster = targetOf(&monster);
    beginCommand();
    session_.replay_applyBossSegmentLinks(target_monster);
    finishCommand();
    if (target_monster.slot == ReplaySlot::Detached) monster = target_monster.value;
}

bool GameplayReplay::isBossMotionBehavior(int behavior) {

    beginCommand();
    auto result = session_.replay_isBossMotionBehavior(behavior);
    finishCommand();

    return result;
}

bool GameplayReplay::bossScanTileSolid(int index, int upper) const {

    beginCommand();
    auto result = session_.replay_bossScanTileSolid(index, upper);
    finishCommand();

    return result;
}

BossHeadEdges GameplayReplay::scanBossHeadEdges(const ActiveMonster& monster) const {
    auto target_monster = targetOf(&monster);
    beginCommand();
    auto result = session_.replay_scanBossHeadEdges(target_monster);
    finishCommand();

    return result;
}

void GameplayReplay::updateBossHead(ActiveMonster& monster) {
    auto target_monster = targetOf(&monster);
    beginCommand();
    session_.replay_updateBossHead(target_monster);
    finishCommand();
    if (target_monster.slot == ReplaySlot::Detached) monster = target_monster.value;
}

void GameplayReplay::damageBossHeadFromFlames(ActiveMonster& monster) {
    auto target_monster = targetOf(&monster);
    beginCommand();
    session_.replay_damageBossHeadFromFlames(target_monster);
    finishCommand();
    if (target_monster.slot == ReplaySlot::Detached) monster = target_monster.value;
}

void GameplayReplay::bossDeathChain(ActiveMonster& head) {
    auto target_head = targetOf(&head);
    beginCommand();
    session_.replay_bossDeathChain(target_head);
    finishCommand();
    if (target_head.slot == ReplaySlot::Detached) head = target_head.value;
}

void GameplayReplay::updateMonsterSpawners() {

    beginCommand();
    session_.replay_updateMonsterSpawners();
    finishCommand();

}

void GameplayReplay::updateMonsters(float dt, uint64_t onlyOrder) {

    beginCommand();
    session_.replay_updateMonsters(dt, onlyOrder);
    finishCommand();

}

void GameplayReplay::releaseMonsterSlot(ActiveMonster& monster) {
    auto target_monster = targetOf(&monster);
    beginCommand();
    session_.replay_releaseMonsterSlot(target_monster);
    finishCommand();
    if (target_monster.slot == ReplaySlot::Detached) monster = target_monster.value;
}

void GameplayReplay::updateDamageCooldowns() {

    beginCommand();
    session_.replay_updateDamageCooldowns();
    finishCommand();

}

void GameplayReplay::queuePlayerDamage(uint8_t startMarker, uint8_t amount) {

    beginCommand();
    session_.replay_queuePlayerDamage(startMarker, amount);
    finishCommand();

}

void GameplayReplay::drainPlayerDamageCounters() {

    beginCommand();
    session_.replay_drainPlayerDamageCounters();
    finishCommand();

}

void GameplayReplay::drainPlayerDamageCounter(Player& player, int& energy, int& lives, bool& dead, int& timer, uint8_t& pending, uint8_t startMarker) {
    auto target_player = targetOf(&player);
    auto target_energy = targetOf(&energy);
    auto target_lives = targetOf(&lives);
    auto target_dead = targetOf(&dead);
    auto target_timer = targetOf(&timer);
    auto target_pending = targetOf(&pending);
    beginCommand();
    session_.replay_drainPlayerDamageCounter(target_player, target_energy, target_lives, target_dead, target_timer, target_pending, startMarker);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
    if (target_energy.slot == ReplaySlot::Detached) energy = target_energy.value;
    if (target_lives.slot == ReplaySlot::Detached) lives = target_lives.value;
    if (target_dead.slot == ReplaySlot::Detached) dead = target_dead.value;
    if (target_timer.slot == ReplaySlot::Detached) timer = target_timer.value;
    if (target_pending.slot == ReplaySlot::Detached) pending = target_pending.value;
}

void GameplayReplay::damagePlayer(Player& player, int& energy, int& lives, bool& dead, int& timer, int& damageCooldown, uint8_t startMarker) {
    auto target_player = targetOf(&player);
    auto target_energy = targetOf(&energy);
    auto target_lives = targetOf(&lives);
    auto target_dead = targetOf(&dead);
    auto target_timer = targetOf(&timer);
    auto target_damageCooldown = targetOf(&damageCooldown);
    beginCommand();
    session_.replay_damagePlayer(target_player, target_energy, target_lives, target_dead, target_timer, target_damageCooldown, startMarker);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
    if (target_energy.slot == ReplaySlot::Detached) energy = target_energy.value;
    if (target_lives.slot == ReplaySlot::Detached) lives = target_lives.value;
    if (target_dead.slot == ReplaySlot::Detached) dead = target_dead.value;
    if (target_timer.slot == ReplaySlot::Detached) timer = target_timer.value;
    if (target_damageCooldown.slot == ReplaySlot::Detached) damageCooldown = target_damageCooldown.value;
}

bool GameplayReplay::playerOverlapsTileArea(const Player& player, int tx0, int ty0, int tx1, int ty1) const {
    auto target_player = targetOf(&player);
    beginCommand();
    auto result = session_.replay_playerOverlapsTileArea(target_player, tx0, ty0, tx1, ty1);
    finishCommand();

    return result;
}

void GameplayReplay::damagePlayersInTileArea(int tx0, int ty0, int tx1, int ty1) {

    beginCommand();
    session_.replay_damagePlayersInTileArea(tx0, ty0, tx1, ty1);
    finishCommand();

}

void GameplayReplay::beginPlayerDeath(Player& player, int& energy, int& lives, bool& dead, int& timer, uint8_t startMarker) {
    auto target_player = targetOf(&player);
    auto target_energy = targetOf(&energy);
    auto target_lives = targetOf(&lives);
    auto target_dead = targetOf(&dead);
    auto target_timer = targetOf(&timer);
    beginCommand();
    session_.replay_beginPlayerDeath(target_player, target_energy, target_lives, target_dead, target_timer, startMarker);
    finishCommand();
    if (target_player.slot == ReplaySlot::Detached) player = target_player.value;
    if (target_energy.slot == ReplaySlot::Detached) energy = target_energy.value;
    if (target_lives.slot == ReplaySlot::Detached) lives = target_lives.value;
    if (target_dead.slot == ReplaySlot::Detached) dead = target_dead.value;
    if (target_timer.slot == ReplaySlot::Detached) timer = target_timer.value;
}

State2VisualCursor& GameplayReplay::state2VisualCursorFor(uint8_t startMarker) {

    beginCommand();
    auto result = session_.replay_state2VisualCursorFor(startMarker);
    finishCommand();

    return *resolvePointer(result);
}

State2EffectEntry& GameplayReplay::state2EffectEntryFor(uint8_t startMarker) {

    beginCommand();
    auto result = session_.replay_state2EffectEntryFor(startMarker);
    finishCommand();

    return *resolvePointer(result);
}
}
