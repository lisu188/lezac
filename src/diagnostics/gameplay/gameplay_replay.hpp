#pragma once
#include "gameplay/game_session.hpp"

namespace lezac::diagnostics {
using namespace gameplay;

// Owns diagnostic copies and translates references into explicit replay targets.
// Runtime play uses GameSession directly; this bridge is never a state owner for it.
class GameplayReplay {
public:
    explicit GameplayReplay(GameSession& session) : session_(session), fixture_(session.snapshot()) {}
    GameplayFixture& fixture() { return fixture_; }
    const GameplayFixture& fixture() const { return fixture_; }
    void refresh() const;
    void commit() const { session_.restoreFixture(fixture_); }
    void beginBoundary() const { ++boundaryDepth_; refresh(); }
    void endBoundary() const { --boundaryDepth_; }
    void resetLevel(int index);
    const LevelPortal* findStartPortal(uint8_t marker) const;
    void tryActivePlayerFireAt(const Player& player, int x, int y, uint8_t playerIndex);
    int tileAt(int tx, int ty) const;
    uint16_t wordAt(int tx, int ty) const;
    uint8_t& tileRef(int tx, int ty);
    uint16_t& wordRef(int tx, int ty);
    bool solidPixel(float px, float py) const;
    bool solidTileSide(uint8_t t);
    bool solidTileBottom(uint8_t t);
    ActiveMonster::EdgeFlags scanActorEdges(int x, int yCollide) const;
    bool scanActorStrongBottom(int x, int yCollide) const;
    bool collides(float x, float y) const;
    bool monsterCollides(float x, float y) const;
    bool playerOverlaps(const Player& player, float x, float y, float w, float h) const;
    int bombTypeIndex(BombType type) const;
    int explosionVisualType(BombType type) const;
    uint8_t explosionDispatcherState(int visualSelector) const;
    int explosionEffectTicks(int visualType) const;
    uint8_t explosionVariantByte(int visualType) const;
    uint16_t explosionSoundOffset(int visualType) const;
    uint8_t explosionSoundSelector(int visualType) const;
    bool hasBomb(const BombInventory& inventory, BombType type) const;
    void selectNextAvailableBomb(BombInventory& inventory);
    void updateWeaponSwitch(BombInventory& inventory, uint8_t& holdTicks, bool pressed);
    void updatePlayerReentryPrepass(const FrameControls& controls);
    void updateWithControls(const FrameControls& controls, float dt);
    bool activateLaunchPad(Player& player, bool down, int localY);
    void updateLaunchPadMarkers(uint64_t onlyOrder = 0);
    void selectPlayerPosture(Player& player, uint8_t spriteBase, bool dropping);
    void updatePlayerGravity(Player& player, bool bottom, uint8_t spriteBase, int& y);
    void updatePlayer(Player& player, bool left, bool right, bool jump, bool switchWeapon, uint8_t spriteBase, bool down = false);
    void applyPlayerTerrainDamage(Player& player, int& energy);
    void updateDyingPlayerMotion(Player& player);
    void integratePlayerMotion(Player& player, int x, int y, const ActiveMonster::EdgeFlags& edges);
    void syncPlayerVelocityMirror(Player& player);
    int16_t actorFloorFriction(int16_t velocity);
    int16_t playerWalkVelocity(int16_t velocity, bool left, bool right, bool bottom);
    std::vector<SharedActorEntry> sharedActorEntries() const;
    uint64_t sharedActorVisualKey(const SharedActorEntry& entry) const;
    void adoptUnorderedActors();
    uint64_t claimActorOrder();
    void updateOrderedActors(float dt);
    size_t sharedActorCount() const;
    void updateCameraShake();
    size_t pickupActorCount() const;
    TransientActor* spawnTransientActor(int x, int y, int16_t vy8, uint8_t sprite, uint8_t kind, uint8_t timer, ActorAnimation animation = {0, 0, 0, 0, 0, 0, 1});
    void updateTransientActor(TransientActor& actor);
    void updateTransientActors();
    void collectObjectiveTiles(const Player& player, uint8_t playerIndex);
    void updatePortalsAndTriggers(Player& player, int& portalCooldown, int& triggerCooldown, bool down);
    bool applyTileTrigger(uint16_t key);
    void accountTileRewrite(uint8_t from, uint8_t to);
    std::array<int, 2> monsterFrameRange(uint8_t kind) const;
    std::array<int, 2> monsterDirectionalFrameRange(uint8_t kind, int16_t vx8) const;
    uint8_t monsterHotspotY(uint8_t kind);
    bool actorTouchesPlayer(const Player& player, int ax, int ayCollide) const;
    uint16_t randomRangeValue(uint16_t base, uint16_t range);
    int randomInclusive(int low, int high);
    int16_t groundWalkerSpeed8(const ActiveMonster& monster) const;
    int16_t retargetSpeed8(const ActiveMonster& monster) const;
    void refreshMonsterAnimationProfile(ActiveMonster& monster);
    void reselectWalkerFacing(ActiveMonster& monster);
    void initializeMonsterMotion(ActiveMonster& monster);
    void retargetMonster(ActiveMonster& monster);
    const Player& nearestPlayer(float x, float y) const;
    void updateMonsterMotion(ActiveMonster& monster, float unused1);
    void spawnLevel7Boss();
    ActiveMonster* findBossActorByVisual(uint8_t visual);
    void updateBossLinks();
    void applyBossSegmentLinks(ActiveMonster& monster);
    bool isBossMotionBehavior(int behavior);
    bool bossScanTileSolid(int index, int upper) const;
    BossHeadEdges scanBossHeadEdges(const ActiveMonster& monster) const;
    void updateBossHead(ActiveMonster& monster);
    void damageBossHeadFromFlames(ActiveMonster& monster);
    void bossDeathChain(ActiveMonster& head);
    void updateMonsterSpawners();
    void updateMonsters(float dt, uint64_t onlyOrder = 0);
    void releaseMonsterSlot(ActiveMonster& monster);
    void updateDamageCooldowns();
    void queuePlayerDamage(uint8_t startMarker, uint8_t amount = 1);
    void drainPlayerDamageCounters();
    void drainPlayerDamageCounter(Player& player, int& energy, int& lives, bool& dead, int& timer, uint8_t& pending, uint8_t startMarker);
    void damagePlayer(Player& player, int& energy, int& lives, bool& dead, int& timer, int& damageCooldown, uint8_t startMarker);
    bool playerOverlapsTileArea(const Player& player, int tx0, int ty0, int tx1, int ty1) const;
    void damagePlayersInTileArea(int tx0, int ty0, int tx1, int ty1);
    void beginPlayerDeath(Player& player, int& energy, int& lives, bool& dead, int& timer, uint8_t startMarker);
    State2VisualCursor& state2VisualCursorFor(uint8_t startMarker);
    State2EffectEntry& state2EffectEntryFor(uint8_t startMarker);
    void refreshState2EffectEntry(const Player& player, const State2VisualCursor& cursor, State2EffectEntry& entry);
    void resetState2VisualCursor(State2VisualCursor& cursor);
    bool updateState2VisualCursor(State2VisualCursor& cursor);
    bool allPlayersOutOfLives() const;
    int& deathStateTimerFor(uint8_t startMarker);
    bool& pendingLifeLossFor(uint8_t startMarker);
    void finalizePendingLifeLoss(bool& dead, int& lives, int& timer, uint8_t startMarker);
    bool canReenterLevel() const;
    int remainingObjectiveTiles() const;
    void updateWaitingPlayerPlacement(Player& player);
    void updateReentry(Player& player, int& energy, int& lives, bool& dead, int& timer, uint8_t startMarker, bool allowLevelRestart);
    uint8_t originalPlayerState(uint8_t player) const;
    bool updateSharedReentryFallback();
    void tryReenterPlayer(Player& player, int& energy, int& lives, bool& dead, int& timer, int& damageCooldown, uint8_t startMarker);
    void respawnPlayerAtStart(Player& player, int& energy, uint8_t startMarker);
    void restartCurrentLevelAfterDeath();
    uint32_t& scoreForPlayer(uint8_t player);
    void addScore(uint8_t player, uint32_t amount);
    void clearRunScores();
    bool isFinalLevel() const;
    void placeBombAt(const Player& player, BombInventory& inventory, uint8_t owner);
    int bombHeightOffset(BombType type) const;
    void updateBombMotion(Bomb& bomb);
    void updateTimedActorMotion(int& x, int& y, int16_t& vx, int16_t& vy, uint8_t& fracX, uint8_t& fracY, const ActiveMonster::EdgeFlags& edges);
    void updateBombs(uint64_t onlyOrder = 0);
    std::vector<std::array<int, 2>> explosionTilesFor(const Bomb& bomb) const;
    void spawnExplosionEffect(const Bomb& bomb);
    void seedFlameRecords(int cell, int type);
    void updateFlameRecords();
    bool isBombObjectTile(uint8_t tile) const;
    bool isHighBombObjectSoundTile(uint8_t tile) const;
    bool isPassableObjectTile(uint8_t tile) const;
    bool isPassableObjectCell(int tx, int ty) const;
    bool requestBombObjectScoreSound(bool sawHighObjectTile);
    bool requestBombPlaceSound();
    bool requestMonsterDeathSound();
    bool requestWeaponSwitchSound();
    bool requestLaunchPadSound();
    bool requestPortalTeleportSound();
    bool requestTileTriggerSound();
    bool requestPlayerDamageSound();
    bool requestPlayerDeathSound();
    bool consumeBombObjectTile(int tx, int ty);
    bool markDamagedTile(int tx, int ty);
    void queueTileDamage(int tx, int ty, uint8_t forwardPhase = 0, uint8_t reversePhase = 0, bool preserveCollapseGlyphs = true);
    DamagePhaseLookup resolveDamagePhase(uint16_t flaggedWord, bool reverse) const;
    void blendDebrisImpactLane(int target, uint16_t word, int& velocity, bool reverse);
    void explode(const Bomb& bomb);
    int monsterDamageForBomb(BombType type) const;
    void damageMonstersInExplosion(const std::vector<std::array<int, 2>>& tiles, BombType type);
    bool monsterOverlapsExplosionTiles(const ActiveMonster& monster, const std::vector<std::array<int, 2>>& tiles) const;
    bool rectsOverlap(float ax, float ay, float aw, float ah, float bx, float by, float bw, float bh) const;
    void damageMonster(ActiveMonster& monster, int damage, bool updatedThisTick = false);
    bool playerOverlapsAnyExplosionTile(const Player& player, const std::vector<std::array<int, 2>>& tiles) const;
    void damagePlayersInExplosion(const std::vector<std::array<int, 2>>& tiles);
    int monsterCorpseSprite(const ActiveMonster& monster) const;
    void enterMonsterDeath(ActiveMonster& monster, bool updatedThisTick = false);
    void spawnBonusDrop(float x, float y, BonusType type);
    void finishMonsterDeathReward(ActiveMonster& monster);
    void spawnExpiryParticles(int x, int y, int count = 2);
    void updateBonusDrops(size_t initialDrops = std::numeric_limits<size_t>::max(), uint64_t onlyOrder = 0);
    float bonusDistanceSq(const Player& player, const BonusDrop& drop) const;
    void collectBonusDrop(BonusDrop& drop, const Player& collector, int& energy, BombInventory& inventory, uint8_t playerIndex);
    void applyBonus(BonusType type, const Player& collector, int& energy, BombInventory& inventory, uint8_t playerIndex = 1);
    void grantNormalBombSet(BombInventory& inventory);
    void grantSuperBombSet(BombInventory& inventory);
    void spawnBonusRain(const Player& collector);
    void updateDebrisRecords();
    void updateCollapseRecords();
    void updateFlashes();
    int destructionPercent() const;
    bool isComplete() const;
private:
    GameSession& session_;
    mutable GameplayFixture fixture_;
    mutable unsigned boundaryDepth_ = 0;
    void beginCommand() const { if (!boundaryDepth_) commit(); }
    void finishCommand() const { refresh(); }
    template<class T> ReplayTarget<T> targetOf(const T* value) const {
        if (!value) return {ReplaySlot::Null, 0, {}};
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.levelIndex_) return {ReplaySlot::levelIndex_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.playerCount_) return {ReplaySlot::playerCount_, 0, {}}; }
        if constexpr (std::is_same_v<T, Player>) { if (value == &fixture_.player_) return {ReplaySlot::player_, 0, {}}; }
        if constexpr (std::is_same_v<T, Player>) { if (value == &fixture_.player2_) return {ReplaySlot::player2_, 0, {}}; }
        if constexpr (std::is_same_v<T, SpawnerState>) { for (size_t i = 0; i < fixture_.spawnerStates_.size(); ++i) if (value == &fixture_.spawnerStates_[i]) return {ReplaySlot::spawnerStates_, i, {}}; }
        if constexpr (std::is_same_v<T, ActiveMonster>) { for (size_t i = 0; i < fixture_.monsters_.size(); ++i) if (value == &fixture_.monsters_[i]) return {ReplaySlot::monsters_, i, {}}; }
        if constexpr (std::is_same_v<T, BossMotionLink>) { for (size_t i = 0; i < fixture_.bossLinks_.size(); ++i) if (value == &fixture_.bossLinks_[i]) return {ReplaySlot::bossLinks_, i, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &fixture_.bossPresent_) return {ReplaySlot::bossPresent_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &fixture_.bossDefeated_) return {ReplaySlot::bossDefeated_, 0, {}}; }
        if constexpr (std::is_same_v<T, BonusDrop>) { for (size_t i = 0; i < fixture_.bonusDrops_.size(); ++i) if (value == &fixture_.bonusDrops_[i]) return {ReplaySlot::bonusDrops_, i, {}}; }
        if constexpr (std::is_same_v<T, Bomb>) { for (size_t i = 0; i < fixture_.bombs_.size(); ++i) if (value == &fixture_.bombs_[i]) return {ReplaySlot::bombs_, i, {}}; }
        if constexpr (std::is_same_v<T, Flash>) { for (size_t i = 0; i < fixture_.flashes_.size(); ++i) if (value == &fixture_.flashes_[i]) return {ReplaySlot::flashes_, i, {}}; }
        if constexpr (std::is_same_v<T, LaunchPadMarker>) { for (size_t i = 0; i < fixture_.launchPadMarkers_.size(); ++i) if (value == &fixture_.launchPadMarkers_[i]) return {ReplaySlot::launchPadMarkers_, i, {}}; }
        if constexpr (std::is_same_v<T, TransientActor>) { for (size_t i = 0; i < fixture_.transientActors_.size(); ++i) if (value == &fixture_.transientActors_[i]) return {ReplaySlot::transientActors_, i, {}}; }
        if constexpr (std::is_same_v<T, uint16_t>) { if (value == &fixture_.cameraShakeTicks_) return {ReplaySlot::cameraShakeTicks_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint16_t>) { if (value == &fixture_.cameraShakeOffset_) return {ReplaySlot::cameraShakeOffset_, 0, {}}; }
        if constexpr (std::is_same_v<T, ExplosionEffect>) { for (size_t i = 0; i < fixture_.explosionEffects_.size(); ++i) if (value == &fixture_.explosionEffects_[i]) return {ReplaySlot::explosionEffects_, i, {}}; }
        if constexpr (std::is_same_v<T, FlameRecord>) { for (size_t i = 0; i < fixture_.flameRecords_.size(); ++i) if (value == &fixture_.flameRecords_[i]) return {ReplaySlot::flameRecords_, i, {}}; }
        if constexpr (std::is_same_v<T, DebrisRecord>) { for (size_t i = 0; i < fixture_.debrisQueue_.size(); ++i) if (value == &fixture_.debrisQueue_[i]) return {ReplaySlot::debrisQueue_, i, {}}; }
        if constexpr (std::is_same_v<T, CollapseRecord>) { for (size_t i = 0; i < fixture_.collapseQueue_.size(); ++i) if (value == &fixture_.collapseQueue_[i]) return {ReplaySlot::collapseQueue_, i, {}}; }
        if constexpr (std::is_same_v<T, uint16_t>) { if (value == &fixture_.nextCollapseFragmentWord_) return {ReplaySlot::nextCollapseFragmentWord_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.collected_) return {ReplaySlot::collected_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.destroyed_) return {ReplaySlot::destroyed_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.completeTimer_) return {ReplaySlot::completeTimer_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.portalCooldown_) return {ReplaySlot::portalCooldown_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.triggerCooldown_) return {ReplaySlot::triggerCooldown_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.portalCooldown2_) return {ReplaySlot::portalCooldown2_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.triggerCooldown2_) return {ReplaySlot::triggerCooldown2_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.energy_) return {ReplaySlot::energy_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.energy2_) return {ReplaySlot::energy2_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.lives_) return {ReplaySlot::lives_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.lives2_) return {ReplaySlot::lives2_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &fixture_.playerDead_) return {ReplaySlot::playerDead_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &fixture_.player2Dead_) return {ReplaySlot::player2Dead_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.reentryTimer_) return {ReplaySlot::reentryTimer_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.reentryTimer2_) return {ReplaySlot::reentryTimer2_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &fixture_.reentryFire1_) return {ReplaySlot::reentryFire1_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &fixture_.reentryFire2_) return {ReplaySlot::reentryFire2_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &fixture_.reentryGate_) return {ReplaySlot::reentryGate_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (value == &fixture_.noActivePlayerTicks_) return {ReplaySlot::noActivePlayerTicks_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &fixture_.levelRestartPromoted_) return {ReplaySlot::levelRestartPromoted_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (value == &fixture_.levelIntroFrame_) return {ReplaySlot::levelIntroFrame_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.deathStateTimer_) return {ReplaySlot::deathStateTimer_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.deathStateTimer2_) return {ReplaySlot::deathStateTimer2_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &fixture_.pendingLifeLoss_) return {ReplaySlot::pendingLifeLoss_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &fixture_.pendingLifeLoss2_) return {ReplaySlot::pendingLifeLoss2_, 0, {}}; }
        if constexpr (std::is_same_v<T, State2VisualCursor>) { if (value == &fixture_.state2Visual_) return {ReplaySlot::state2Visual_, 0, {}}; }
        if constexpr (std::is_same_v<T, State2VisualCursor>) { if (value == &fixture_.state2Visual2_) return {ReplaySlot::state2Visual2_, 0, {}}; }
        if constexpr (std::is_same_v<T, State2EffectEntry>) { if (value == &fixture_.state2Effect_) return {ReplaySlot::state2Effect_, 0, {}}; }
        if constexpr (std::is_same_v<T, State2EffectEntry>) { if (value == &fixture_.state2Effect2_) return {ReplaySlot::state2Effect2_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &fixture_.state2VisualCursorPreview_) return {ReplaySlot::state2VisualCursorPreview_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &fixture_.state2VisualRowPreview_) return {ReplaySlot::state2VisualRowPreview_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.damageCooldown_) return {ReplaySlot::damageCooldown_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.damageCooldown2_) return {ReplaySlot::damageCooldown2_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (value == &fixture_.pendingDamage_) return {ReplaySlot::pendingDamage_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (value == &fixture_.pendingDamage2_) return {ReplaySlot::pendingDamage2_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &fixture_.levelResetGeneration_) return {ReplaySlot::levelResetGeneration_, 0, {}}; }
        if constexpr (std::is_same_v<T, BombInventory>) { if (value == &fixture_.bombInventory_) return {ReplaySlot::bombInventory_, 0, {}}; }
        if constexpr (std::is_same_v<T, BombInventory>) { if (value == &fixture_.bombInventory2_) return {ReplaySlot::bombInventory2_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (value == &fixture_.weaponSwitchHoldTicks_) return {ReplaySlot::weaponSwitchHoldTicks_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (value == &fixture_.weaponSwitchHoldTicks2_) return {ReplaySlot::weaponSwitchHoldTicks2_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (value == &fixture_.logicTick_) return {ReplaySlot::logicTick_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &fixture_.orderedActorPass_) return {ReplaySlot::orderedActorPass_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (value == &fixture_.score_) return {ReplaySlot::score_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (value == &fixture_.score2_) return {ReplaySlot::score2_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint8_t>) { for (size_t i = 0; i < fixture_.level_.tiles.size(); ++i) if (value == &fixture_.level_.tiles[i]) return {ReplaySlot::levelTiles, i, {}}; }
        if constexpr (std::is_same_v<T, uint16_t>) { for (size_t i = 0; i < fixture_.level_.wordLayer.size(); ++i) if (value == &fixture_.level_.wordLayer[i]) return {ReplaySlot::levelWords, i, {}}; }
        if constexpr (std::is_same_v<T, LevelPortal>) { for (size_t i = 0; i < fixture_.level_.portals.size(); ++i) if (value == &fixture_.level_.portals[i]) return {ReplaySlot::levelPortals, i, {}}; }
        return {ReplaySlot::Detached, 0, *value};
    }
    template<class T> T* resolvePointer(ReplayTarget<T>& target) const {
        if (target.slot == ReplaySlot::Null) return nullptr;
        if (target.slot == ReplaySlot::Detached) throw std::runtime_error("replay result is not an owned fixture slot");
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::levelIndex_) return &fixture_.levelIndex_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::playerCount_) return &fixture_.playerCount_; }
        if constexpr (std::is_same_v<T, Player>) { if (target.slot == ReplaySlot::player_) return &fixture_.player_; }
        if constexpr (std::is_same_v<T, Player>) { if (target.slot == ReplaySlot::player2_) return &fixture_.player2_; }
        if constexpr (std::is_same_v<T, SpawnerState>) { if (target.slot == ReplaySlot::spawnerStates_) return &fixture_.spawnerStates_.at(target.index); }
        if constexpr (std::is_same_v<T, ActiveMonster>) { if (target.slot == ReplaySlot::monsters_) return &fixture_.monsters_.at(target.index); }
        if constexpr (std::is_same_v<T, BossMotionLink>) { if (target.slot == ReplaySlot::bossLinks_) return &fixture_.bossLinks_.at(target.index); }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::bossPresent_) return &fixture_.bossPresent_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::bossDefeated_) return &fixture_.bossDefeated_; }
        if constexpr (std::is_same_v<T, BonusDrop>) { if (target.slot == ReplaySlot::bonusDrops_) return &fixture_.bonusDrops_.at(target.index); }
        if constexpr (std::is_same_v<T, Bomb>) { if (target.slot == ReplaySlot::bombs_) return &fixture_.bombs_.at(target.index); }
        if constexpr (std::is_same_v<T, Flash>) { if (target.slot == ReplaySlot::flashes_) return &fixture_.flashes_.at(target.index); }
        if constexpr (std::is_same_v<T, LaunchPadMarker>) { if (target.slot == ReplaySlot::launchPadMarkers_) return &fixture_.launchPadMarkers_.at(target.index); }
        if constexpr (std::is_same_v<T, TransientActor>) { if (target.slot == ReplaySlot::transientActors_) return &fixture_.transientActors_.at(target.index); }
        if constexpr (std::is_same_v<T, uint16_t>) { if (target.slot == ReplaySlot::cameraShakeTicks_) return &fixture_.cameraShakeTicks_; }
        if constexpr (std::is_same_v<T, uint16_t>) { if (target.slot == ReplaySlot::cameraShakeOffset_) return &fixture_.cameraShakeOffset_; }
        if constexpr (std::is_same_v<T, ExplosionEffect>) { if (target.slot == ReplaySlot::explosionEffects_) return &fixture_.explosionEffects_.at(target.index); }
        if constexpr (std::is_same_v<T, FlameRecord>) { if (target.slot == ReplaySlot::flameRecords_) return &fixture_.flameRecords_.at(target.index); }
        if constexpr (std::is_same_v<T, DebrisRecord>) { if (target.slot == ReplaySlot::debrisQueue_) return &fixture_.debrisQueue_.at(target.index); }
        if constexpr (std::is_same_v<T, CollapseRecord>) { if (target.slot == ReplaySlot::collapseQueue_) return &fixture_.collapseQueue_.at(target.index); }
        if constexpr (std::is_same_v<T, uint16_t>) { if (target.slot == ReplaySlot::nextCollapseFragmentWord_) return &fixture_.nextCollapseFragmentWord_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::collected_) return &fixture_.collected_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::destroyed_) return &fixture_.destroyed_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::completeTimer_) return &fixture_.completeTimer_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::portalCooldown_) return &fixture_.portalCooldown_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::triggerCooldown_) return &fixture_.triggerCooldown_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::portalCooldown2_) return &fixture_.portalCooldown2_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::triggerCooldown2_) return &fixture_.triggerCooldown2_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::energy_) return &fixture_.energy_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::energy2_) return &fixture_.energy2_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::lives_) return &fixture_.lives_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::lives2_) return &fixture_.lives2_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::playerDead_) return &fixture_.playerDead_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::player2Dead_) return &fixture_.player2Dead_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::reentryTimer_) return &fixture_.reentryTimer_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::reentryTimer2_) return &fixture_.reentryTimer2_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::reentryFire1_) return &fixture_.reentryFire1_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::reentryFire2_) return &fixture_.reentryFire2_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::reentryGate_) return &fixture_.reentryGate_; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (target.slot == ReplaySlot::noActivePlayerTicks_) return &fixture_.noActivePlayerTicks_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::levelRestartPromoted_) return &fixture_.levelRestartPromoted_; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (target.slot == ReplaySlot::levelIntroFrame_) return &fixture_.levelIntroFrame_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::deathStateTimer_) return &fixture_.deathStateTimer_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::deathStateTimer2_) return &fixture_.deathStateTimer2_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::pendingLifeLoss_) return &fixture_.pendingLifeLoss_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::pendingLifeLoss2_) return &fixture_.pendingLifeLoss2_; }
        if constexpr (std::is_same_v<T, State2VisualCursor>) { if (target.slot == ReplaySlot::state2Visual_) return &fixture_.state2Visual_; }
        if constexpr (std::is_same_v<T, State2VisualCursor>) { if (target.slot == ReplaySlot::state2Visual2_) return &fixture_.state2Visual2_; }
        if constexpr (std::is_same_v<T, State2EffectEntry>) { if (target.slot == ReplaySlot::state2Effect_) return &fixture_.state2Effect_; }
        if constexpr (std::is_same_v<T, State2EffectEntry>) { if (target.slot == ReplaySlot::state2Effect2_) return &fixture_.state2Effect2_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::state2VisualCursorPreview_) return &fixture_.state2VisualCursorPreview_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::state2VisualRowPreview_) return &fixture_.state2VisualRowPreview_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::damageCooldown_) return &fixture_.damageCooldown_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::damageCooldown2_) return &fixture_.damageCooldown2_; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (target.slot == ReplaySlot::pendingDamage_) return &fixture_.pendingDamage_; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (target.slot == ReplaySlot::pendingDamage2_) return &fixture_.pendingDamage2_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::levelResetGeneration_) return &fixture_.levelResetGeneration_; }
        if constexpr (std::is_same_v<T, BombInventory>) { if (target.slot == ReplaySlot::bombInventory_) return &fixture_.bombInventory_; }
        if constexpr (std::is_same_v<T, BombInventory>) { if (target.slot == ReplaySlot::bombInventory2_) return &fixture_.bombInventory2_; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (target.slot == ReplaySlot::weaponSwitchHoldTicks_) return &fixture_.weaponSwitchHoldTicks_; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (target.slot == ReplaySlot::weaponSwitchHoldTicks2_) return &fixture_.weaponSwitchHoldTicks2_; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (target.slot == ReplaySlot::logicTick_) return &fixture_.logicTick_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::orderedActorPass_) return &fixture_.orderedActorPass_; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (target.slot == ReplaySlot::score_) return &fixture_.score_; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (target.slot == ReplaySlot::score2_) return &fixture_.score2_; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (target.slot == ReplaySlot::levelTiles) return &fixture_.level_.tiles.at(target.index); }
        if constexpr (std::is_same_v<T, uint16_t>) { if (target.slot == ReplaySlot::levelWords) return &fixture_.level_.wordLayer.at(target.index); }
        if constexpr (std::is_same_v<T, LevelPortal>) { if (target.slot == ReplaySlot::levelPortals) return &fixture_.level_.portals.at(target.index); }
        throw std::runtime_error("invalid gameplay replay target");
    }
};
}
