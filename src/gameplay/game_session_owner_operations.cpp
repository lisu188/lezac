#include "gameplay/game_session.hpp"
#include "core/fixed_point.hpp"
#include "core/progress.hpp"
#include <cmath>

namespace lezac::gameplay {
using namespace lezac::core;
namespace {
int16_t clampI16(int value) { return static_cast<int16_t>(std::clamp(value, -32768, 32767)); }
void integrateAxis8_8(int& pos, uint8_t& frac, int16_t velocity) {
    core::Fixed8_8Axis axis{pos, frac};
    core::integrateFixed8_8(axis, velocity);
    pos = axis.position; frac = axis.fraction;
}
}

const LevelPortal* GameSession::findStartPortal(uint8_t marker) const { return level_world_.findStartPortal(marker); }

int GameSession::tileAt(int tx, int ty) const { return level_world_.tileAt(tx, ty); }

uint16_t GameSession::wordAt(int tx, int ty) const { return level_world_.wordAt(tx, ty); }

uint8_t& GameSession::tileRef(int tx, int ty) { return level_world_.tileRef(tx, ty); }

uint16_t& GameSession::wordRef(int tx, int ty) { return level_world_.wordRef(tx, ty); }

bool GameSession::solidPixel(float px, float py) const { return level_world_.solidPixel(px, py); }

bool GameSession::solidTileSide(uint8_t t) { return LevelWorld::solidTileSide(t); }

bool GameSession::solidTileBottom(uint8_t t) { return LevelWorld::solidTileBottom(t); }

ActiveMonster::EdgeFlags GameSession::scanActorEdges(int x, int yCollide) const { return level_world_.scanActorEdges(x, yCollide); }

bool GameSession::scanActorStrongBottom(int x, int yCollide) const { return level_world_.scanActorStrongBottom(x, yCollide); }

bool GameSession::collides(float x, float y) const { return level_world_.collides(x, y); }

bool GameSession::monsterCollides(float x, float y) const { return level_world_.monsterCollides(x, y); }

uint8_t GameSession::explosionDispatcherState(int visualSelector) const { return terrain_effects_.explosionDispatcherState(visualSelector); }

int GameSession::explosionEffectTicks(int visualType) const { return terrain_effects_.explosionEffectTicks(visualType); }

uint8_t GameSession::explosionVariantByte(int visualType) const { return terrain_effects_.explosionVariantByte(visualType); }

uint16_t GameSession::explosionSoundOffset(int visualType) const { return terrain_effects_.explosionSoundOffset(visualType); }

uint8_t GameSession::explosionSoundSelector(int visualType) const { return terrain_effects_.explosionSoundSelector(visualType); }

void GameSession::selectPlayerPosture(Player& player, uint8_t spriteBase, bool dropping) { PlayerRoster::selectPlayerPosture(player, spriteBase, dropping); }

void GameSession::updatePlayerGravity(Player& player, bool bottom, uint8_t spriteBase, int& y) { PlayerRoster::updatePlayerGravity(player, bottom, spriteBase, y); }

void GameSession::integratePlayerMotion(Player& player, int x, int y, const ActiveMonster::EdgeFlags& edges) { PlayerRoster::integratePlayerMotion(player, x, y, edges); }

void GameSession::syncPlayerVelocityMirror(Player& player) { PlayerRoster::syncPlayerVelocityMirror(player); }

int16_t GameSession::actorFloorFriction(int16_t velocity) { return PlayerRoster::actorFloorFriction(velocity); }

int16_t GameSession::playerWalkVelocity(int16_t velocity, bool left, bool right, bool bottom) { return PlayerRoster::playerWalkVelocity(velocity, left, right, bottom); }

std::vector<SharedActorEntry> GameSession::sharedActorEntries() const { return actor_system_.sharedActorEntries(); }

uint64_t GameSession::sharedActorVisualKey(const SharedActorEntry& entry) const { return actor_system_.sharedActorVisualKey(entry); }

void GameSession::adoptUnorderedActors() { actor_system_.adoptUnorderedActors(); }

uint64_t GameSession::claimActorOrder() { return actor_system_.claimActorOrder(); }

size_t GameSession::sharedActorCount() const { return actor_system_.sharedActorCount(); }

void GameSession::updateCameraShake() { terrain_effects_.updateCameraShake(random_); }

size_t GameSession::pickupActorCount() const { return actor_system_.pickupActorCount(); }

bool GameSession::bossScanTileSolid(int index, int upper) const { return level_world_.bossScanTileSolid(index, upper); }

BossHeadEdges GameSession::scanBossHeadEdges(const ActiveMonster& monster) const { return level_world_.scanBossHeadEdges(monster); }

void GameSession::updateDamageCooldowns() { player_roster_.updateDamageCooldowns(); }

void GameSession::queuePlayerDamage(uint8_t startMarker, uint8_t amount) { player_roster_.queuePlayerDamage(startMarker, amount); }

State2VisualCursor& GameSession::state2VisualCursorFor(uint8_t startMarker) { return player_roster_.state2VisualCursorFor(startMarker); }

State2EffectEntry& GameSession::state2EffectEntryFor(uint8_t startMarker) { return player_roster_.state2EffectEntryFor(startMarker); }

void GameSession::refreshState2EffectEntry(const Player& player, const State2VisualCursor& cursor, State2EffectEntry& entry) { player_roster_.refreshState2EffectEntry(player, cursor, entry); }

void GameSession::resetState2VisualCursor(State2VisualCursor& cursor) { player_roster_.resetState2VisualCursor(cursor); }

bool GameSession::updateState2VisualCursor(State2VisualCursor& cursor) { return player_roster_.updateState2VisualCursor(cursor); }

bool GameSession::allPlayersOutOfLives() const { return player_roster_.allPlayersOutOfLives(); }

int& GameSession::deathStateTimerFor(uint8_t startMarker) { return player_roster_.deathStateTimerFor(startMarker); }

bool& GameSession::pendingLifeLossFor(uint8_t startMarker) { return player_roster_.pendingLifeLossFor(startMarker); }

bool GameSession::canReenterLevel() const { return level_world_.canReenterLevel(); }

int GameSession::remainingObjectiveTiles() const { return level_world_.remainingObjectiveTiles(); }

uint8_t GameSession::originalPlayerState(uint8_t player) const { return player_roster_.originalPlayerState(player); }

uint32_t& GameSession::scoreForPlayer(uint8_t player) { return player_roster_.scoreForPlayer(player); }

void GameSession::addScore(uint8_t player, uint32_t amount) { player_roster_.addScore(player, amount); }

void GameSession::clearRunScores() { player_roster_.clearRunScores(); }

bool GameSession::isBombObjectTile(uint8_t tile) const { return level_world_.isBombObjectTile(tile); }

bool GameSession::isHighBombObjectSoundTile(uint8_t tile) const { return level_world_.isHighBombObjectSoundTile(tile); }

bool GameSession::isPassableObjectTile(uint8_t tile) const { return level_world_.isPassableObjectTile(tile); }

bool GameSession::isPassableObjectCell(int tx, int ty) const { return level_world_.isPassableObjectCell(tx, ty); }

bool GameSession::consumeBombObjectTile(int tx, int ty) { return level_world_.consumeBombObjectTile(tx, ty); }

bool GameSession::markDamagedTile(int tx, int ty) { return level_world_.markDamagedTile(tx, ty); }

void GameSession::queueTileDamage(int tx, int ty, uint8_t forwardPhase, uint8_t reversePhase, bool preserveCollapseGlyphs) { terrain_effects_.queueTileDamage(level_, tx, ty, forwardPhase, reversePhase, preserveCollapseGlyphs); }

DamagePhaseLookup GameSession::resolveDamagePhase(uint16_t flaggedWord, bool reverse) const { return terrain_effects_.resolveDamagePhase(flaggedWord, reverse); }

int GameSession::destructionPercent() const { return level_world_.destructionPercent(); }

bool GameSession::isComplete() const { return level_world_.isComplete(); }
}
