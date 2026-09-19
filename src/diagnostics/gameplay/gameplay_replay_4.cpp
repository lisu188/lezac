#include "diagnostics/gameplay/gameplay_replay.hpp"
namespace lezac::diagnostics {
DamagePhaseLookup GameplayReplay::resolveDamagePhase(uint16_t flaggedWord, bool reverse) const {

    beginCommand();
    auto result = session_.replay_resolveDamagePhase(flaggedWord, reverse);
    finishCommand();

    return result;
}

void GameplayReplay::blendDebrisImpactLane(int target, uint16_t word, int& velocity, bool reverse) {
    auto target_velocity = targetOf(&velocity);
    beginCommand();
    session_.replay_blendDebrisImpactLane(target, word, target_velocity, reverse);
    finishCommand();
    if (target_velocity.slot == ReplaySlot::Detached) velocity = target_velocity.value;
}

void GameplayReplay::explode(const Bomb& bomb) {
    auto target_bomb = targetOf(&bomb);
    beginCommand();
    session_.replay_explode(target_bomb);
    finishCommand();

}

int GameplayReplay::monsterDamageForBomb(BombType type) const {

    beginCommand();
    auto result = session_.replay_monsterDamageForBomb(type);
    finishCommand();

    return result;
}

void GameplayReplay::damageMonstersInExplosion(const std::vector<std::array<int, 2>>& tiles, BombType type) {

    beginCommand();
    session_.replay_damageMonstersInExplosion(tiles, type);
    finishCommand();

}

bool GameplayReplay::monsterOverlapsExplosionTiles(const ActiveMonster& monster, const std::vector<std::array<int, 2>>& tiles) const {
    auto target_monster = targetOf(&monster);
    beginCommand();
    auto result = session_.replay_monsterOverlapsExplosionTiles(target_monster, tiles);
    finishCommand();

    return result;
}

bool GameplayReplay::rectsOverlap(float ax, float ay, float aw, float ah, float bx, float by, float bw, float bh) const {

    beginCommand();
    auto result = session_.replay_rectsOverlap(ax, ay, aw, ah, bx, by, bw, bh);
    finishCommand();

    return result;
}

void GameplayReplay::damageMonster(ActiveMonster& monster, int damage, bool updatedThisTick) {
    auto target_monster = targetOf(&monster);
    beginCommand();
    session_.replay_damageMonster(target_monster, damage, updatedThisTick);
    finishCommand();
    if (target_monster.slot == ReplaySlot::Detached) monster = target_monster.value;
}

bool GameplayReplay::playerOverlapsAnyExplosionTile(const Player& player, const std::vector<std::array<int, 2>>& tiles) const {
    auto target_player = targetOf(&player);
    beginCommand();
    auto result = session_.replay_playerOverlapsAnyExplosionTile(target_player, tiles);
    finishCommand();

    return result;
}

void GameplayReplay::damagePlayersInExplosion(const std::vector<std::array<int, 2>>& tiles) {

    beginCommand();
    session_.replay_damagePlayersInExplosion(tiles);
    finishCommand();

}

int GameplayReplay::monsterCorpseSprite(const ActiveMonster& monster) const {
    auto target_monster = targetOf(&monster);
    beginCommand();
    auto result = session_.replay_monsterCorpseSprite(target_monster);
    finishCommand();

    return result;
}

void GameplayReplay::enterMonsterDeath(ActiveMonster& monster, bool updatedThisTick) {
    auto target_monster = targetOf(&monster);
    beginCommand();
    session_.replay_enterMonsterDeath(target_monster, updatedThisTick);
    finishCommand();
    if (target_monster.slot == ReplaySlot::Detached) monster = target_monster.value;
}

void GameplayReplay::spawnBonusDrop(float x, float y, BonusType type) {

    beginCommand();
    session_.replay_spawnBonusDrop(x, y, type);
    finishCommand();

}

void GameplayReplay::finishMonsterDeathReward(ActiveMonster& monster) {
    auto target_monster = targetOf(&monster);
    beginCommand();
    session_.replay_finishMonsterDeathReward(target_monster);
    finishCommand();
    if (target_monster.slot == ReplaySlot::Detached) monster = target_monster.value;
}

void GameplayReplay::spawnExpiryParticles(int x, int y, int count) {

    beginCommand();
    session_.replay_spawnExpiryParticles(x, y, count);
    finishCommand();

}

void GameplayReplay::updateBonusDrops(size_t initialDrops, uint64_t onlyOrder) {

    beginCommand();
    session_.replay_updateBonusDrops(initialDrops, onlyOrder);
    finishCommand();

}

float GameplayReplay::bonusDistanceSq(const Player& player, const BonusDrop& drop) const {
    auto target_player = targetOf(&player);
    auto target_drop = targetOf(&drop);
    beginCommand();
    auto result = session_.replay_bonusDistanceSq(target_player, target_drop);
    finishCommand();

    return result;
}

void GameplayReplay::collectBonusDrop(BonusDrop& drop, const Player& collector, int& energy, BombInventory& inventory, uint8_t playerIndex) {
    auto target_drop = targetOf(&drop);
    auto target_collector = targetOf(&collector);
    auto target_energy = targetOf(&energy);
    auto target_inventory = targetOf(&inventory);
    beginCommand();
    session_.replay_collectBonusDrop(target_drop, target_collector, target_energy, target_inventory, playerIndex);
    finishCommand();
    if (target_drop.slot == ReplaySlot::Detached) drop = target_drop.value;
    if (target_energy.slot == ReplaySlot::Detached) energy = target_energy.value;
    if (target_inventory.slot == ReplaySlot::Detached) inventory = target_inventory.value;
}

void GameplayReplay::applyBonus(BonusType type, const Player& collector, int& energy, BombInventory& inventory, uint8_t playerIndex) {
    auto target_collector = targetOf(&collector);
    auto target_energy = targetOf(&energy);
    auto target_inventory = targetOf(&inventory);
    beginCommand();
    session_.replay_applyBonus(type, target_collector, target_energy, target_inventory, playerIndex);
    finishCommand();
    if (target_energy.slot == ReplaySlot::Detached) energy = target_energy.value;
    if (target_inventory.slot == ReplaySlot::Detached) inventory = target_inventory.value;
}

void GameplayReplay::grantNormalBombSet(BombInventory& inventory) {
    auto target_inventory = targetOf(&inventory);
    beginCommand();
    session_.replay_grantNormalBombSet(target_inventory);
    finishCommand();
    if (target_inventory.slot == ReplaySlot::Detached) inventory = target_inventory.value;
}

void GameplayReplay::grantSuperBombSet(BombInventory& inventory) {
    auto target_inventory = targetOf(&inventory);
    beginCommand();
    session_.replay_grantSuperBombSet(target_inventory);
    finishCommand();
    if (target_inventory.slot == ReplaySlot::Detached) inventory = target_inventory.value;
}

void GameplayReplay::spawnBonusRain(const Player& collector) {
    auto target_collector = targetOf(&collector);
    beginCommand();
    session_.replay_spawnBonusRain(target_collector);
    finishCommand();

}

void GameplayReplay::updateDebrisRecords() {

    beginCommand();
    session_.replay_updateDebrisRecords();
    finishCommand();

}

void GameplayReplay::updateCollapseRecords() {

    beginCommand();
    session_.replay_updateCollapseRecords();
    finishCommand();

}

void GameplayReplay::updateFlashes() {

    beginCommand();
    session_.replay_updateFlashes();
    finishCommand();

}

int GameplayReplay::destructionPercent() const {

    beginCommand();
    auto result = session_.replay_destructionPercent();
    finishCommand();

    return result;
}

bool GameplayReplay::isComplete() const {

    beginCommand();
    auto result = session_.replay_isComplete();
    finishCommand();

    return result;
}
}
