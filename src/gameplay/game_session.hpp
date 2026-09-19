#pragma once
#include <functional>
#include <stdexcept>
#include <type_traits>
#include "gameplay/gameplay_fixture.hpp"
#include "gameplay/replay_target.hpp"
#include "core/random.hpp"
#include "resources/asset_catalog.hpp"
#include "sound/sound_engine.hpp"

namespace lezac::gameplay {

struct GameplayHooks {
    std::function<bool()> menuActive;
    std::function<bool()> tickBlocked;
    std::function<bool()> reentryBlocked;
    std::function<void()> beforeReset;
    std::function<void(size_t)> mapSizeChanged;
    std::function<void(int)> beginLevel;
    std::function<void()> gameOver;
    std::function<void()> levelCompletion;
    std::function<void()> pumpSound;
    std::function<void(uint16_t)> updateRedPalette;
    std::function<void(const GameplayView&)> actorPassObserver;
    std::function<void(const char*, const GameplayView&)> reentryBoundaryObserver;
};

struct AfterActorPassAction {
    std::vector<TransientActor> appendActors;
};

enum class CompletionAction { None, UpdateOutro, NextLevel, EndRun };

class GameSession {
public:
    GameSession(const AssetCatalog& assets, sound::SoundEngine& sound, core::TurboRandom& random);
    GameSession(const GameSession&) = delete;
    GameSession& operator=(const GameSession&) = delete;
    void setHooks(GameplayHooks hooks) { hooks_ = std::move(hooks); }
    GameplayView view() const;
    GameplayFixture snapshot() const;
    void restoreFixture(const GameplayFixture& fixture);
    void scheduleAfterActorPass(AfterActorPassAction action) { afterActorPassActions_.push_back(std::move(action)); }
    void tick(const FrameControls& controls, float dt) { updateWithControls(controls, dt); }
    void prepareRenderState() { adoptUnorderedActors(); }
    void reset(int index) { resetLevel(index); }
    void fireAtPlayer(uint8_t index, int x, int y);
    void setFireLatch(uint8_t index, bool held);
    void startRun(int playerCount);
    void prepareNewGame(int playerCount) { playerCount_ = playerCount; resetReserveLives(); }
    void clearScores() { clearRunScores(); }
    void awardScore(uint8_t player, uint32_t amount) { addScore(player, amount); }
    void notifyReentryBoundary(const char* phase) const;
    using DecodeLevelPlane = std::function<std::vector<uint8_t>(const std::vector<uint8_t>&, size_t)>;
    void beginLevelSelection(int index, bool fromMenu, const DecodeLevelPlane& decodePlane);
    void finishLevelSetup(int index);
    void resetReserveLives() { lives_ = lives2_ = 3; }
    CompletionAction advanceCompletionState(bool interactive);
    std::vector<SharedActorEntry> renderActorOrder();
    int destructionPercentage() const { return destructionPercent(); }
    bool complete() const { return isComplete(); }
    bool finalLevel() const { return isFinalLevel(); }

    // Typed replay operations execute the same private helpers as the live tick.
    // Slot targets and detached values never expose mutable session references.
    void replay_resetLevel(int index);
    ReplayTarget<LevelPortal> replay_findStartPortal(uint8_t marker);
    void replay_tryActivePlayerFireAt(ReplayTarget<Player>& player, int x, int y, uint8_t playerIndex);
    int replay_tileAt(int tx, int ty);
    uint16_t replay_wordAt(int tx, int ty);
    ReplayTarget<uint8_t> replay_tileRef(int tx, int ty);
    ReplayTarget<uint16_t> replay_wordRef(int tx, int ty);
    bool replay_solidPixel(float px, float py);
    bool replay_solidTileSide(uint8_t t);
    bool replay_solidTileBottom(uint8_t t);
    ActiveMonster::EdgeFlags replay_scanActorEdges(int x, int yCollide);
    bool replay_scanActorStrongBottom(int x, int yCollide);
    bool replay_collides(float x, float y);
    bool replay_monsterCollides(float x, float y);
    bool replay_playerOverlaps(ReplayTarget<Player>& player, float x, float y, float w, float h);
    int replay_bombTypeIndex(BombType type);
    int replay_explosionVisualType(BombType type);
    uint8_t replay_explosionDispatcherState(int visualSelector);
    int replay_explosionEffectTicks(int visualType);
    uint8_t replay_explosionVariantByte(int visualType);
    uint16_t replay_explosionSoundOffset(int visualType);
    uint8_t replay_explosionSoundSelector(int visualType);
    bool replay_hasBomb(ReplayTarget<BombInventory>& inventory, BombType type);
    void replay_selectNextAvailableBomb(ReplayTarget<BombInventory>& inventory);
    void replay_updateWeaponSwitch(ReplayTarget<BombInventory>& inventory, ReplayTarget<uint8_t>& holdTicks, bool pressed);
    void replay_updatePlayerReentryPrepass(const FrameControls& controls);
    void replay_updateWithControls(const FrameControls& controls, float dt);
    bool replay_activateLaunchPad(ReplayTarget<Player>& player, bool down, int localY);
    void replay_updateLaunchPadMarkers(uint64_t onlyOrder);
    void replay_selectPlayerPosture(ReplayTarget<Player>& player, uint8_t spriteBase, bool dropping);
    void replay_updatePlayerGravity(ReplayTarget<Player>& player, bool bottom, uint8_t spriteBase, ReplayTarget<int>& y);
    void replay_updatePlayer(ReplayTarget<Player>& player, bool left, bool right, bool jump, bool switchWeapon, uint8_t spriteBase, bool down);
    void replay_applyPlayerTerrainDamage(ReplayTarget<Player>& player, ReplayTarget<int>& energy);
    void replay_updateDyingPlayerMotion(ReplayTarget<Player>& player);
    void replay_integratePlayerMotion(ReplayTarget<Player>& player, int x, int y, const ActiveMonster::EdgeFlags& edges);
    void replay_syncPlayerVelocityMirror(ReplayTarget<Player>& player);
    int16_t replay_actorFloorFriction(int16_t velocity);
    int16_t replay_playerWalkVelocity(int16_t velocity, bool left, bool right, bool bottom);
    std::vector<SharedActorEntry> replay_sharedActorEntries();
    uint64_t replay_sharedActorVisualKey(const SharedActorEntry& entry);
    void replay_adoptUnorderedActors();
    uint64_t replay_claimActorOrder();
    void replay_updateOrderedActors(float dt);
    size_t replay_sharedActorCount();
    void replay_updateCameraShake();
    size_t replay_pickupActorCount();
    ReplayTarget<TransientActor> replay_spawnTransientActor(int x, int y, int16_t vy8, uint8_t sprite, uint8_t kind, uint8_t timer, ActorAnimation animation);
    void replay_updateTransientActor(ReplayTarget<TransientActor>& actor);
    void replay_updateTransientActors();
    void replay_collectObjectiveTiles(ReplayTarget<Player>& player, uint8_t playerIndex);
    void replay_updatePortalsAndTriggers(ReplayTarget<Player>& player, ReplayTarget<int>& portalCooldown, ReplayTarget<int>& triggerCooldown, bool down);
    bool replay_applyTileTrigger(uint16_t key);
    void replay_accountTileRewrite(uint8_t from, uint8_t to);
    std::array<int, 2> replay_monsterFrameRange(uint8_t kind);
    std::array<int, 2> replay_monsterDirectionalFrameRange(uint8_t kind, int16_t vx8);
    uint8_t replay_monsterHotspotY(uint8_t kind);
    bool replay_actorTouchesPlayer(ReplayTarget<Player>& player, int ax, int ayCollide);
    uint16_t replay_randomRangeValue(uint16_t base, uint16_t range);
    int replay_randomInclusive(int low, int high);
    int16_t replay_groundWalkerSpeed8(ReplayTarget<ActiveMonster>& monster);
    int16_t replay_retargetSpeed8(ReplayTarget<ActiveMonster>& monster);
    void replay_refreshMonsterAnimationProfile(ReplayTarget<ActiveMonster>& monster);
    void replay_reselectWalkerFacing(ReplayTarget<ActiveMonster>& monster);
    void replay_initializeMonsterMotion(ReplayTarget<ActiveMonster>& monster);
    void replay_retargetMonster(ReplayTarget<ActiveMonster>& monster);
    ReplayTarget<Player> replay_nearestPlayer(float x, float y);
    void replay_updateMonsterMotion(ReplayTarget<ActiveMonster>& monster, float unused1);
    void replay_spawnLevel7Boss();
    ReplayTarget<ActiveMonster> replay_findBossActorByVisual(uint8_t visual);
    void replay_updateBossLinks();
    void replay_applyBossSegmentLinks(ReplayTarget<ActiveMonster>& monster);
    bool replay_isBossMotionBehavior(int behavior);
    bool replay_bossScanTileSolid(int index, int upper);
    BossHeadEdges replay_scanBossHeadEdges(ReplayTarget<ActiveMonster>& monster);
    void replay_updateBossHead(ReplayTarget<ActiveMonster>& monster);
    void replay_damageBossHeadFromFlames(ReplayTarget<ActiveMonster>& monster);
    void replay_bossDeathChain(ReplayTarget<ActiveMonster>& head);
    void replay_updateMonsterSpawners();
    void replay_updateMonsters(float dt, uint64_t onlyOrder);
    void replay_releaseMonsterSlot(ReplayTarget<ActiveMonster>& monster);
    void replay_updateDamageCooldowns();
    void replay_queuePlayerDamage(uint8_t startMarker, uint8_t amount);
    void replay_drainPlayerDamageCounters();
    void replay_drainPlayerDamageCounter(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, ReplayTarget<uint8_t>& pending, uint8_t startMarker);
    void replay_damagePlayer(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, ReplayTarget<int>& damageCooldown, uint8_t startMarker);
    bool replay_playerOverlapsTileArea(ReplayTarget<Player>& player, int tx0, int ty0, int tx1, int ty1);
    void replay_damagePlayersInTileArea(int tx0, int ty0, int tx1, int ty1);
    void replay_beginPlayerDeath(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, uint8_t startMarker);
    ReplayTarget<State2VisualCursor> replay_state2VisualCursorFor(uint8_t startMarker);
    ReplayTarget<State2EffectEntry> replay_state2EffectEntryFor(uint8_t startMarker);
    void replay_refreshState2EffectEntry(ReplayTarget<Player>& player, ReplayTarget<State2VisualCursor>& cursor, ReplayTarget<State2EffectEntry>& entry);
    void replay_resetState2VisualCursor(ReplayTarget<State2VisualCursor>& cursor);
    bool replay_updateState2VisualCursor(ReplayTarget<State2VisualCursor>& cursor);
    bool replay_allPlayersOutOfLives();
    ReplayTarget<int> replay_deathStateTimerFor(uint8_t startMarker);
    ReplayTarget<bool> replay_pendingLifeLossFor(uint8_t startMarker);
    void replay_finalizePendingLifeLoss(ReplayTarget<bool>& dead, ReplayTarget<int>& lives, ReplayTarget<int>& timer, uint8_t startMarker);
    bool replay_canReenterLevel();
    int replay_remainingObjectiveTiles();
    void replay_updateWaitingPlayerPlacement(ReplayTarget<Player>& player);
    void replay_updateReentry(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, uint8_t startMarker, bool allowLevelRestart);
    uint8_t replay_originalPlayerState(uint8_t player);
    bool replay_updateSharedReentryFallback();
    void replay_tryReenterPlayer(ReplayTarget<Player>& player, ReplayTarget<int>& energy, ReplayTarget<int>& lives, ReplayTarget<bool>& dead, ReplayTarget<int>& timer, ReplayTarget<int>& damageCooldown, uint8_t startMarker);
    void replay_respawnPlayerAtStart(ReplayTarget<Player>& player, ReplayTarget<int>& energy, uint8_t startMarker);
    void replay_restartCurrentLevelAfterDeath();
    ReplayTarget<uint32_t> replay_scoreForPlayer(uint8_t player);
    void replay_addScore(uint8_t player, uint32_t amount);
    void replay_clearRunScores();
    bool replay_isFinalLevel();
    void replay_placeBombAt(ReplayTarget<Player>& player, ReplayTarget<BombInventory>& inventory, uint8_t owner);
    int replay_bombHeightOffset(BombType type);
    void replay_updateBombMotion(ReplayTarget<Bomb>& bomb);
    void replay_updateTimedActorMotion(ReplayTarget<int>& x, ReplayTarget<int>& y, ReplayTarget<int16_t>& vx, ReplayTarget<int16_t>& vy, ReplayTarget<uint8_t>& fracX, ReplayTarget<uint8_t>& fracY, const ActiveMonster::EdgeFlags& edges);
    void replay_updateBombs(uint64_t onlyOrder);
    std::vector<std::array<int, 2>> replay_explosionTilesFor(ReplayTarget<Bomb>& bomb);
    void replay_spawnExplosionEffect(ReplayTarget<Bomb>& bomb);
    void replay_seedFlameRecords(int cell, int type);
    void replay_updateFlameRecords();
    bool replay_isBombObjectTile(uint8_t tile);
    bool replay_isHighBombObjectSoundTile(uint8_t tile);
    bool replay_isPassableObjectTile(uint8_t tile);
    bool replay_isPassableObjectCell(int tx, int ty);
    bool replay_requestBombObjectScoreSound(bool sawHighObjectTile);
    bool replay_requestBombPlaceSound();
    bool replay_requestMonsterDeathSound();
    bool replay_requestWeaponSwitchSound();
    bool replay_requestLaunchPadSound();
    bool replay_requestPortalTeleportSound();
    bool replay_requestTileTriggerSound();
    bool replay_requestPlayerDamageSound();
    bool replay_requestPlayerDeathSound();
    bool replay_consumeBombObjectTile(int tx, int ty);
    bool replay_markDamagedTile(int tx, int ty);
    void replay_queueTileDamage(int tx, int ty, uint8_t forwardPhase, uint8_t reversePhase, bool preserveCollapseGlyphs);
    DamagePhaseLookup replay_resolveDamagePhase(uint16_t flaggedWord, bool reverse);
    void replay_blendDebrisImpactLane(int target, uint16_t word, ReplayTarget<int>& velocity, bool reverse);
    void replay_explode(ReplayTarget<Bomb>& bomb);
    int replay_monsterDamageForBomb(BombType type);
    void replay_damageMonstersInExplosion(const std::vector<std::array<int, 2>>& tiles, BombType type);
    bool replay_monsterOverlapsExplosionTiles(ReplayTarget<ActiveMonster>& monster, const std::vector<std::array<int, 2>>& tiles);
    bool replay_rectsOverlap(float ax, float ay, float aw, float ah, float bx, float by, float bw, float bh);
    void replay_damageMonster(ReplayTarget<ActiveMonster>& monster, int damage, bool updatedThisTick);
    bool replay_playerOverlapsAnyExplosionTile(ReplayTarget<Player>& player, const std::vector<std::array<int, 2>>& tiles);
    void replay_damagePlayersInExplosion(const std::vector<std::array<int, 2>>& tiles);
    int replay_monsterCorpseSprite(ReplayTarget<ActiveMonster>& monster);
    void replay_enterMonsterDeath(ReplayTarget<ActiveMonster>& monster, bool updatedThisTick);
    void replay_spawnBonusDrop(float x, float y, BonusType type);
    void replay_finishMonsterDeathReward(ReplayTarget<ActiveMonster>& monster);
    void replay_spawnExpiryParticles(int x, int y, int count);
    void replay_updateBonusDrops(size_t initialDrops, uint64_t onlyOrder);
    float replay_bonusDistanceSq(ReplayTarget<Player>& player, ReplayTarget<BonusDrop>& drop);
    void replay_collectBonusDrop(ReplayTarget<BonusDrop>& drop, ReplayTarget<Player>& collector, ReplayTarget<int>& energy, ReplayTarget<BombInventory>& inventory, uint8_t playerIndex);
    void replay_applyBonus(BonusType type, ReplayTarget<Player>& collector, ReplayTarget<int>& energy, ReplayTarget<BombInventory>& inventory, uint8_t playerIndex);
    void replay_grantNormalBombSet(ReplayTarget<BombInventory>& inventory);
    void replay_grantSuperBombSet(ReplayTarget<BombInventory>& inventory);
    void replay_spawnBonusRain(ReplayTarget<Player>& collector);
    void replay_updateDebrisRecords();
    void replay_updateCollapseRecords();
    void replay_updateFlashes();
    int replay_destructionPercent();
    bool replay_isComplete();

private:
    LevelWorld level_world_;
    PlayerRoster player_roster_;
    ActorSystem actor_system_;
    TerrainEffects terrain_effects_;
    const AssetCatalog& assets_;
    sound::SoundEngine& sound_;
    core::TurboRandom& random_;
    GameplayHooks hooks_;
    std::vector<AfterActorPassAction> afterActorPassActions_;
    const std::vector<Level>& levels_;
    const SpriteBank& sprites_;
    const SpriteBank& altSprites_;
    const GranBank& gran_;
    Level& level_ = level_world_.state_.level_;
    int& levelIndex_ = level_world_.state_.levelIndex_;
    int& collected_ = level_world_.state_.collected_;
    int& destroyed_ = level_world_.state_.destroyed_;
    int& completeTimer_ = level_world_.state_.completeTimer_;
    int& levelResetGeneration_ = level_world_.state_.levelResetGeneration_;
    uint32_t& levelIntroFrame_ = level_world_.state_.levelIntroFrame_;
    uint32_t& logicTick_ = level_world_.state_.logicTick_;
    int& playerCount_ = player_roster_.state_.playerCount_;
    Player& player_ = player_roster_.state_.player_;
    Player& player2_ = player_roster_.state_.player2_;
    int& portalCooldown_ = player_roster_.state_.portalCooldown_;
    int& triggerCooldown_ = player_roster_.state_.triggerCooldown_;
    int& portalCooldown2_ = player_roster_.state_.portalCooldown2_;
    int& triggerCooldown2_ = player_roster_.state_.triggerCooldown2_;
    int& energy_ = player_roster_.state_.energy_;
    int& energy2_ = player_roster_.state_.energy2_;
    int& lives_ = player_roster_.state_.lives_;
    int& lives2_ = player_roster_.state_.lives2_;
    bool& playerDead_ = player_roster_.state_.playerDead_;
    bool& player2Dead_ = player_roster_.state_.player2Dead_;
    int& reentryTimer_ = player_roster_.state_.reentryTimer_;
    int& reentryTimer2_ = player_roster_.state_.reentryTimer2_;
    bool& reentryFire1_ = player_roster_.state_.reentryFire1_;
    bool& reentryFire2_ = player_roster_.state_.reentryFire2_;
    bool& reentryGate_ = player_roster_.state_.reentryGate_;
    uint8_t& noActivePlayerTicks_ = player_roster_.state_.noActivePlayerTicks_;
    bool& levelRestartPromoted_ = player_roster_.state_.levelRestartPromoted_;
    int& deathStateTimer_ = player_roster_.state_.deathStateTimer_;
    int& deathStateTimer2_ = player_roster_.state_.deathStateTimer2_;
    bool& pendingLifeLoss_ = player_roster_.state_.pendingLifeLoss_;
    bool& pendingLifeLoss2_ = player_roster_.state_.pendingLifeLoss2_;
    State2VisualCursor& state2Visual_ = player_roster_.state_.state2Visual_;
    State2VisualCursor& state2Visual2_ = player_roster_.state_.state2Visual2_;
    State2EffectEntry& state2Effect_ = player_roster_.state_.state2Effect_;
    State2EffectEntry& state2Effect2_ = player_roster_.state_.state2Effect2_;
    bool& state2VisualCursorPreview_ = player_roster_.state_.state2VisualCursorPreview_;
    bool& state2VisualRowPreview_ = player_roster_.state_.state2VisualRowPreview_;
    int& damageCooldown_ = player_roster_.state_.damageCooldown_;
    int& damageCooldown2_ = player_roster_.state_.damageCooldown2_;
    uint8_t& pendingDamage_ = player_roster_.state_.pendingDamage_;
    uint8_t& pendingDamage2_ = player_roster_.state_.pendingDamage2_;
    BombInventory& bombInventory_ = player_roster_.state_.bombInventory_;
    BombInventory& bombInventory2_ = player_roster_.state_.bombInventory2_;
    uint8_t& weaponSwitchHoldTicks_ = player_roster_.state_.weaponSwitchHoldTicks_;
    uint8_t& weaponSwitchHoldTicks2_ = player_roster_.state_.weaponSwitchHoldTicks2_;
    uint32_t& score_ = player_roster_.state_.score_;
    uint32_t& score2_ = player_roster_.state_.score2_;
    std::vector<SpawnerState>& spawnerStates_ = actor_system_.state_.spawnerStates_;
    std::vector<ActiveMonster>& monsters_ = actor_system_.state_.monsters_;
    std::vector<BossMotionLink>& bossLinks_ = actor_system_.state_.bossLinks_;
    std::array<float, 128>& bossSinTable_ = actor_system_.state_.bossSinTable_;
    bool& bossPresent_ = actor_system_.state_.bossPresent_;
    bool& bossDefeated_ = actor_system_.state_.bossDefeated_;
    std::vector<BonusDrop>& bonusDrops_ = actor_system_.state_.bonusDrops_;
    std::vector<Bomb>& bombs_ = actor_system_.state_.bombs_;
    std::vector<LaunchPadMarker>& launchPadMarkers_ = actor_system_.state_.launchPadMarkers_;
    std::vector<TransientActor>& transientActors_ = actor_system_.state_.transientActors_;
    uint64_t& nextActorOrder_ = actor_system_.state_.nextActorOrder_;
    bool& orderedActorPass_ = actor_system_.state_.orderedActorPass_;
    std::vector<Flash>& flashes_ = terrain_effects_.state_.flashes_;
    uint16_t& cameraShakeTicks_ = terrain_effects_.state_.cameraShakeTicks_;
    uint16_t& cameraShakeOffset_ = terrain_effects_.state_.cameraShakeOffset_;
    std::vector<ExplosionEffect>& explosionEffects_ = terrain_effects_.state_.explosionEffects_;
    std::vector<FlameRecord>& flameRecords_ = terrain_effects_.state_.flameRecords_;
    std::vector<DebrisRecord>& debrisQueue_ = terrain_effects_.state_.debrisQueue_;
    std::vector<CollapseRecord>& collapseQueue_ = terrain_effects_.state_.collapseQueue_;
    uint16_t& nextCollapseFragmentWord_ = terrain_effects_.state_.nextCollapseFragmentWord_;

    void applyAfterActorPassActions();
    bool requestSoundCursor(uint16_t cursor, uint8_t priority) { return sound_.requestSoundCursor(cursor, priority); }
    bool requestSoundOffset(uint16_t offset, uint8_t priority) { return sound_.requestSoundOffset(offset, priority); }
    bool playCompatibilitySound(size_t slot) { return sound_.playCompatibilitySound(slot); }
    void resetLevel(int index);
    const LevelPortal* findStartPortal(uint8_t marker) const;
    void tryActivePlayerFireAt(const Player& player, int x, int y, uint8_t playerIndex);
    int tileAt(int tx, int ty) const;
    uint16_t wordAt(int tx, int ty) const;
    uint8_t& tileRef(int tx, int ty);
    uint16_t& wordRef(int tx, int ty);
    bool solidPixel(float px, float py) const;
    static bool solidTileSide(uint8_t t);
    static bool solidTileBottom(uint8_t t);
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
    static void selectPlayerPosture(Player& player, uint8_t spriteBase, bool dropping);
    static void updatePlayerGravity(Player& player, bool bottom, uint8_t spriteBase, int& y);
    void updatePlayer(Player& player, bool left, bool right, bool jump, bool switchWeapon, uint8_t spriteBase, bool down = false);
    void applyPlayerTerrainDamage(Player& player, int& energy);
    void updateDyingPlayerMotion(Player& player);
    static void integratePlayerMotion(Player& player, int x, int y, const ActiveMonster::EdgeFlags& edges);
    static void syncPlayerVelocityMirror(Player& player);
    static int16_t actorFloorFriction(int16_t velocity);
    static int16_t playerWalkVelocity(int16_t velocity, bool left, bool right, bool bottom);
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
    static uint8_t monsterHotspotY(uint8_t kind);
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
    static bool isBossMotionBehavior(int behavior);
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
    template<class T> ReplayTarget<T> targetOf(const T* value) const {
        if (!value) return {ReplaySlot::Null, 0, {}};
        if constexpr (std::is_same_v<T, int>) { if (value == &levelIndex_) return {ReplaySlot::levelIndex_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &playerCount_) return {ReplaySlot::playerCount_, 0, {}}; }
        if constexpr (std::is_same_v<T, Player>) { if (value == &player_) return {ReplaySlot::player_, 0, {}}; }
        if constexpr (std::is_same_v<T, Player>) { if (value == &player2_) return {ReplaySlot::player2_, 0, {}}; }
        if constexpr (std::is_same_v<T, SpawnerState>) { for (size_t i = 0; i < spawnerStates_.size(); ++i) if (value == &spawnerStates_[i]) return {ReplaySlot::spawnerStates_, i, {}}; }
        if constexpr (std::is_same_v<T, ActiveMonster>) { for (size_t i = 0; i < monsters_.size(); ++i) if (value == &monsters_[i]) return {ReplaySlot::monsters_, i, {}}; }
        if constexpr (std::is_same_v<T, BossMotionLink>) { for (size_t i = 0; i < bossLinks_.size(); ++i) if (value == &bossLinks_[i]) return {ReplaySlot::bossLinks_, i, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &bossPresent_) return {ReplaySlot::bossPresent_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &bossDefeated_) return {ReplaySlot::bossDefeated_, 0, {}}; }
        if constexpr (std::is_same_v<T, BonusDrop>) { for (size_t i = 0; i < bonusDrops_.size(); ++i) if (value == &bonusDrops_[i]) return {ReplaySlot::bonusDrops_, i, {}}; }
        if constexpr (std::is_same_v<T, Bomb>) { for (size_t i = 0; i < bombs_.size(); ++i) if (value == &bombs_[i]) return {ReplaySlot::bombs_, i, {}}; }
        if constexpr (std::is_same_v<T, Flash>) { for (size_t i = 0; i < flashes_.size(); ++i) if (value == &flashes_[i]) return {ReplaySlot::flashes_, i, {}}; }
        if constexpr (std::is_same_v<T, LaunchPadMarker>) { for (size_t i = 0; i < launchPadMarkers_.size(); ++i) if (value == &launchPadMarkers_[i]) return {ReplaySlot::launchPadMarkers_, i, {}}; }
        if constexpr (std::is_same_v<T, TransientActor>) { for (size_t i = 0; i < transientActors_.size(); ++i) if (value == &transientActors_[i]) return {ReplaySlot::transientActors_, i, {}}; }
        if constexpr (std::is_same_v<T, uint16_t>) { if (value == &cameraShakeTicks_) return {ReplaySlot::cameraShakeTicks_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint16_t>) { if (value == &cameraShakeOffset_) return {ReplaySlot::cameraShakeOffset_, 0, {}}; }
        if constexpr (std::is_same_v<T, ExplosionEffect>) { for (size_t i = 0; i < explosionEffects_.size(); ++i) if (value == &explosionEffects_[i]) return {ReplaySlot::explosionEffects_, i, {}}; }
        if constexpr (std::is_same_v<T, FlameRecord>) { for (size_t i = 0; i < flameRecords_.size(); ++i) if (value == &flameRecords_[i]) return {ReplaySlot::flameRecords_, i, {}}; }
        if constexpr (std::is_same_v<T, DebrisRecord>) { for (size_t i = 0; i < debrisQueue_.size(); ++i) if (value == &debrisQueue_[i]) return {ReplaySlot::debrisQueue_, i, {}}; }
        if constexpr (std::is_same_v<T, CollapseRecord>) { for (size_t i = 0; i < collapseQueue_.size(); ++i) if (value == &collapseQueue_[i]) return {ReplaySlot::collapseQueue_, i, {}}; }
        if constexpr (std::is_same_v<T, uint16_t>) { if (value == &nextCollapseFragmentWord_) return {ReplaySlot::nextCollapseFragmentWord_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &collected_) return {ReplaySlot::collected_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &destroyed_) return {ReplaySlot::destroyed_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &completeTimer_) return {ReplaySlot::completeTimer_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &portalCooldown_) return {ReplaySlot::portalCooldown_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &triggerCooldown_) return {ReplaySlot::triggerCooldown_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &portalCooldown2_) return {ReplaySlot::portalCooldown2_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &triggerCooldown2_) return {ReplaySlot::triggerCooldown2_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &energy_) return {ReplaySlot::energy_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &energy2_) return {ReplaySlot::energy2_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &lives_) return {ReplaySlot::lives_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &lives2_) return {ReplaySlot::lives2_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &playerDead_) return {ReplaySlot::playerDead_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &player2Dead_) return {ReplaySlot::player2Dead_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &reentryTimer_) return {ReplaySlot::reentryTimer_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &reentryTimer2_) return {ReplaySlot::reentryTimer2_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &reentryFire1_) return {ReplaySlot::reentryFire1_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &reentryFire2_) return {ReplaySlot::reentryFire2_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &reentryGate_) return {ReplaySlot::reentryGate_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (value == &noActivePlayerTicks_) return {ReplaySlot::noActivePlayerTicks_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &levelRestartPromoted_) return {ReplaySlot::levelRestartPromoted_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (value == &levelIntroFrame_) return {ReplaySlot::levelIntroFrame_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &deathStateTimer_) return {ReplaySlot::deathStateTimer_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &deathStateTimer2_) return {ReplaySlot::deathStateTimer2_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &pendingLifeLoss_) return {ReplaySlot::pendingLifeLoss_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &pendingLifeLoss2_) return {ReplaySlot::pendingLifeLoss2_, 0, {}}; }
        if constexpr (std::is_same_v<T, State2VisualCursor>) { if (value == &state2Visual_) return {ReplaySlot::state2Visual_, 0, {}}; }
        if constexpr (std::is_same_v<T, State2VisualCursor>) { if (value == &state2Visual2_) return {ReplaySlot::state2Visual2_, 0, {}}; }
        if constexpr (std::is_same_v<T, State2EffectEntry>) { if (value == &state2Effect_) return {ReplaySlot::state2Effect_, 0, {}}; }
        if constexpr (std::is_same_v<T, State2EffectEntry>) { if (value == &state2Effect2_) return {ReplaySlot::state2Effect2_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &state2VisualCursorPreview_) return {ReplaySlot::state2VisualCursorPreview_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &state2VisualRowPreview_) return {ReplaySlot::state2VisualRowPreview_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &damageCooldown_) return {ReplaySlot::damageCooldown_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &damageCooldown2_) return {ReplaySlot::damageCooldown2_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (value == &pendingDamage_) return {ReplaySlot::pendingDamage_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (value == &pendingDamage2_) return {ReplaySlot::pendingDamage2_, 0, {}}; }
        if constexpr (std::is_same_v<T, int>) { if (value == &levelResetGeneration_) return {ReplaySlot::levelResetGeneration_, 0, {}}; }
        if constexpr (std::is_same_v<T, BombInventory>) { if (value == &bombInventory_) return {ReplaySlot::bombInventory_, 0, {}}; }
        if constexpr (std::is_same_v<T, BombInventory>) { if (value == &bombInventory2_) return {ReplaySlot::bombInventory2_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (value == &weaponSwitchHoldTicks_) return {ReplaySlot::weaponSwitchHoldTicks_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (value == &weaponSwitchHoldTicks2_) return {ReplaySlot::weaponSwitchHoldTicks2_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (value == &logicTick_) return {ReplaySlot::logicTick_, 0, {}}; }
        if constexpr (std::is_same_v<T, bool>) { if (value == &orderedActorPass_) return {ReplaySlot::orderedActorPass_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (value == &score_) return {ReplaySlot::score_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (value == &score2_) return {ReplaySlot::score2_, 0, {}}; }
        if constexpr (std::is_same_v<T, uint8_t>) { for (size_t i = 0; i < level_.tiles.size(); ++i) if (value == &level_.tiles[i]) return {ReplaySlot::levelTiles, i, {}}; }
        if constexpr (std::is_same_v<T, uint16_t>) { for (size_t i = 0; i < level_.wordLayer.size(); ++i) if (value == &level_.wordLayer[i]) return {ReplaySlot::levelWords, i, {}}; }
        if constexpr (std::is_same_v<T, LevelPortal>) { for (size_t i = 0; i < level_.portals.size(); ++i) if (value == &level_.portals[i]) return {ReplaySlot::levelPortals, i, {}}; }
        return {ReplaySlot::Detached, 0, *value};
    }
    template<class T> T& resolve(ReplayTarget<T>& target) {
        if (target.slot == ReplaySlot::Detached) return target.value;
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::levelIndex_) return levelIndex_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::playerCount_) return playerCount_; }
        if constexpr (std::is_same_v<T, Player>) { if (target.slot == ReplaySlot::player_) return player_; }
        if constexpr (std::is_same_v<T, Player>) { if (target.slot == ReplaySlot::player2_) return player2_; }
        if constexpr (std::is_same_v<T, SpawnerState>) { if (target.slot == ReplaySlot::spawnerStates_) return spawnerStates_.at(target.index); }
        if constexpr (std::is_same_v<T, ActiveMonster>) { if (target.slot == ReplaySlot::monsters_) return monsters_.at(target.index); }
        if constexpr (std::is_same_v<T, BossMotionLink>) { if (target.slot == ReplaySlot::bossLinks_) return bossLinks_.at(target.index); }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::bossPresent_) return bossPresent_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::bossDefeated_) return bossDefeated_; }
        if constexpr (std::is_same_v<T, BonusDrop>) { if (target.slot == ReplaySlot::bonusDrops_) return bonusDrops_.at(target.index); }
        if constexpr (std::is_same_v<T, Bomb>) { if (target.slot == ReplaySlot::bombs_) return bombs_.at(target.index); }
        if constexpr (std::is_same_v<T, Flash>) { if (target.slot == ReplaySlot::flashes_) return flashes_.at(target.index); }
        if constexpr (std::is_same_v<T, LaunchPadMarker>) { if (target.slot == ReplaySlot::launchPadMarkers_) return launchPadMarkers_.at(target.index); }
        if constexpr (std::is_same_v<T, TransientActor>) { if (target.slot == ReplaySlot::transientActors_) return transientActors_.at(target.index); }
        if constexpr (std::is_same_v<T, uint16_t>) { if (target.slot == ReplaySlot::cameraShakeTicks_) return cameraShakeTicks_; }
        if constexpr (std::is_same_v<T, uint16_t>) { if (target.slot == ReplaySlot::cameraShakeOffset_) return cameraShakeOffset_; }
        if constexpr (std::is_same_v<T, ExplosionEffect>) { if (target.slot == ReplaySlot::explosionEffects_) return explosionEffects_.at(target.index); }
        if constexpr (std::is_same_v<T, FlameRecord>) { if (target.slot == ReplaySlot::flameRecords_) return flameRecords_.at(target.index); }
        if constexpr (std::is_same_v<T, DebrisRecord>) { if (target.slot == ReplaySlot::debrisQueue_) return debrisQueue_.at(target.index); }
        if constexpr (std::is_same_v<T, CollapseRecord>) { if (target.slot == ReplaySlot::collapseQueue_) return collapseQueue_.at(target.index); }
        if constexpr (std::is_same_v<T, uint16_t>) { if (target.slot == ReplaySlot::nextCollapseFragmentWord_) return nextCollapseFragmentWord_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::collected_) return collected_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::destroyed_) return destroyed_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::completeTimer_) return completeTimer_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::portalCooldown_) return portalCooldown_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::triggerCooldown_) return triggerCooldown_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::portalCooldown2_) return portalCooldown2_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::triggerCooldown2_) return triggerCooldown2_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::energy_) return energy_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::energy2_) return energy2_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::lives_) return lives_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::lives2_) return lives2_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::playerDead_) return playerDead_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::player2Dead_) return player2Dead_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::reentryTimer_) return reentryTimer_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::reentryTimer2_) return reentryTimer2_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::reentryFire1_) return reentryFire1_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::reentryFire2_) return reentryFire2_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::reentryGate_) return reentryGate_; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (target.slot == ReplaySlot::noActivePlayerTicks_) return noActivePlayerTicks_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::levelRestartPromoted_) return levelRestartPromoted_; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (target.slot == ReplaySlot::levelIntroFrame_) return levelIntroFrame_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::deathStateTimer_) return deathStateTimer_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::deathStateTimer2_) return deathStateTimer2_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::pendingLifeLoss_) return pendingLifeLoss_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::pendingLifeLoss2_) return pendingLifeLoss2_; }
        if constexpr (std::is_same_v<T, State2VisualCursor>) { if (target.slot == ReplaySlot::state2Visual_) return state2Visual_; }
        if constexpr (std::is_same_v<T, State2VisualCursor>) { if (target.slot == ReplaySlot::state2Visual2_) return state2Visual2_; }
        if constexpr (std::is_same_v<T, State2EffectEntry>) { if (target.slot == ReplaySlot::state2Effect_) return state2Effect_; }
        if constexpr (std::is_same_v<T, State2EffectEntry>) { if (target.slot == ReplaySlot::state2Effect2_) return state2Effect2_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::state2VisualCursorPreview_) return state2VisualCursorPreview_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::state2VisualRowPreview_) return state2VisualRowPreview_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::damageCooldown_) return damageCooldown_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::damageCooldown2_) return damageCooldown2_; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (target.slot == ReplaySlot::pendingDamage_) return pendingDamage_; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (target.slot == ReplaySlot::pendingDamage2_) return pendingDamage2_; }
        if constexpr (std::is_same_v<T, int>) { if (target.slot == ReplaySlot::levelResetGeneration_) return levelResetGeneration_; }
        if constexpr (std::is_same_v<T, BombInventory>) { if (target.slot == ReplaySlot::bombInventory_) return bombInventory_; }
        if constexpr (std::is_same_v<T, BombInventory>) { if (target.slot == ReplaySlot::bombInventory2_) return bombInventory2_; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (target.slot == ReplaySlot::weaponSwitchHoldTicks_) return weaponSwitchHoldTicks_; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (target.slot == ReplaySlot::weaponSwitchHoldTicks2_) return weaponSwitchHoldTicks2_; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (target.slot == ReplaySlot::logicTick_) return logicTick_; }
        if constexpr (std::is_same_v<T, bool>) { if (target.slot == ReplaySlot::orderedActorPass_) return orderedActorPass_; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (target.slot == ReplaySlot::score_) return score_; }
        if constexpr (std::is_same_v<T, uint32_t>) { if (target.slot == ReplaySlot::score2_) return score2_; }
        if constexpr (std::is_same_v<T, uint8_t>) { if (target.slot == ReplaySlot::levelTiles) return level_.tiles.at(target.index); }
        if constexpr (std::is_same_v<T, uint16_t>) { if (target.slot == ReplaySlot::levelWords) return level_.wordLayer.at(target.index); }
        if constexpr (std::is_same_v<T, LevelPortal>) { if (target.slot == ReplaySlot::levelPortals) return level_.portals.at(target.index); }
        throw std::runtime_error("invalid gameplay replay target");
    }
};
}
