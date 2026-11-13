#pragma once
#include "gameplay/gameplay_fixture.hpp"
#include <memory>

namespace lezac::gameplay {
struct GameplayServices {
    const AssetCatalog& assets;
    sound::SoundEngine& sound;
    sound::SdlAudioOutput& audio;
    rendering::PresentationState& presentation;
    ui::UiController& ui;
    ui::RecordStore& records;
    ui::LevelFlow& flow;
    ui::LevelIntroPattern& endPattern;
    rendering::Canvas& canvas;
    rendering::GameRenderer& renderer;
    rendering::ViewportLayout& viewport;
    int& viewWidth;
    int& configuredPlayers;
    std::function<uint32_t()> milliseconds;
    std::function<void()> flushMenuKeys;
    std::function<void()>& present;
    std::function<void()>& presentPalette;
    std::function<void(size_t)>& resultReelObserver;
    std::function<void(size_t, uint32_t, uint32_t)>& resultTypingObserver;
    std::function<void()>& actorPassObserver;
    std::function<void(const Bomb&, const char*)>& bombExpiryObserver;
    std::function<void(const ActiveMonster&, bool)>& animationObserver;
    std::function<void(uint8_t)>& deathGateObserver;
    std::function<void(uint8_t, uint8_t)>& healthWriteObserver;
    std::function<void(const char*)>& reentryObserver;
};
namespace detail {
class GameplayOperations {
protected:
    explicit GameplayOperations(GameplayServices services);
    GameplayOperations(const GameplayOperations&) = delete;
    GameplayOperations& operator=(const GameplayOperations&) = delete;
    GameplayOperations(GameplayOperations&&) = delete;
    GameplayOperations& operator=(GameplayOperations&&) = delete;
    std::unique_ptr<GameplayFixture> ownedFixture_ = std::make_unique<GameplayFixture>();
    GameplayFixture& fixture_ = *ownedFixture_;
    GameplayServices services_;
    const AssetCatalog& assets_;
    const SpriteBank& sprites_;
    const SpriteBank& altSprites_;
    const GranBank& gran_;
    const std::vector<Level>& levels_;
    sound::SoundEngine& sound_;
    sound::SdlAudioOutput& audioOutput_;
    rendering::PresentationState& presentation_;
    ui::UiController& ui_;
    ui::RecordStore& recordStore_;
    ui::LevelFlow& levelFlow_;
    ui::LevelIntroPattern& endScreenPattern_;
    rendering::Canvas& canvas_;
    rendering::GameRenderer& gameRenderer_;
    rendering::ViewportLayout& viewportLayout_;
    int& gameplayViewWidth_;
    int& playfieldConfiguredCount_;
    std::function<void()>& gameplayPresentation_;
    std::function<void()>& gameplayPalettePresentation_;
    std::function<void(size_t)>& debugResultReelObserver_;
    std::function<void(size_t, uint32_t, uint32_t)>& debugResultTypingObserver_;
    std::function<void()>& debugActorPassObserver_;
    std::function<void(const Bomb&, const char*)>& debugBombExpiryObserver_;
    std::function<void(const ActiveMonster&, bool)>& debugMonsterAnimationObserver_;
    std::function<void(uint8_t)>& debugDeathGateObserver_;
    std::function<void(uint8_t, uint8_t)>& debugPlayerHealthWriteObserver_;
    std::function<void(const char*)>& debugReentryBoundaryObserver_;
    uint32_t presentationMilliseconds() const { return services_.milliseconds(); }
    void flushBufferedMenuKeys() { services_.flushMenuKeys(); }
    decltype(fixture_.clockedSoundEnabled_)& clockedSoundEnabled_ = fixture_.clockedSoundEnabled_;
    decltype(fixture_.soundClockMilliseconds_)& soundClockMilliseconds_ = fixture_.soundClockMilliseconds_;
    decltype(fixture_.soundSampleRemainder_)& soundSampleRemainder_ = fixture_.soundSampleRemainder_;
    decltype(fixture_.level_)& level_ = fixture_.level_;
    decltype(fixture_.levelIndex_)& levelIndex_ = fixture_.levelIndex_;
    decltype(fixture_.playerCount_)& playerCount_ = fixture_.playerCount_;
    decltype(fixture_.player_)& player_ = fixture_.player_;
    decltype(fixture_.player2_)& player2_ = fixture_.player2_;
    decltype(fixture_.spawnerStates_)& spawnerStates_ = fixture_.spawnerStates_;
    decltype(fixture_.spawnerStorage_)& spawnerStorage_ = fixture_.spawnerStorage_;
    decltype(fixture_.monsters_)& monsters_ = fixture_.monsters_;
    decltype(fixture_.bossLinks_)& bossLinks_ = fixture_.bossLinks_;
    decltype(fixture_.bossSinTable_)& bossSinTable_ = fixture_.bossSinTable_;
    decltype(fixture_.bossPresent_)& bossPresent_ = fixture_.bossPresent_;
    decltype(fixture_.bossDefeated_)& bossDefeated_ = fixture_.bossDefeated_;
    decltype(fixture_.bonusDrops_)& bonusDrops_ = fixture_.bonusDrops_;
    decltype(fixture_.pendingBonuses_)& pendingBonuses_ = fixture_.pendingBonuses_;
    decltype(fixture_.bombs_)& bombs_ = fixture_.bombs_;
    decltype(fixture_.flashes_)& flashes_ = fixture_.flashes_;
    decltype(fixture_.launchPadMarkers_)& launchPadMarkers_ = fixture_.launchPadMarkers_;
    decltype(fixture_.transientActors_)& transientActors_ = fixture_.transientActors_;
    decltype(fixture_.cameraShakeTicks_)& cameraShakeTicks_ = fixture_.cameraShakeTicks_;
    decltype(fixture_.cameraShakeOffset_)& cameraShakeOffset_ = fixture_.cameraShakeOffset_;
    decltype(fixture_.explosionEffects_)& explosionEffects_ = fixture_.explosionEffects_;
    decltype(fixture_.flameRecords_)& flameRecords_ = fixture_.flameRecords_;
    decltype(fixture_.debrisQueue_)& debrisQueue_ = fixture_.debrisQueue_;
    decltype(fixture_.collapseQueue_)& collapseQueue_ = fixture_.collapseQueue_;
    decltype(fixture_.damageLaneData_)& damageLaneData_ = fixture_.damageLaneData_;
    decltype(fixture_.mapPlaneMemory_)& mapPlaneMemory_ = fixture_.mapPlaneMemory_;
    decltype(fixture_.nextCollapseFragmentWord_)& nextCollapseFragmentWord_ = fixture_.nextCollapseFragmentWord_;
    decltype(fixture_.bonusRainTicks_)& bonusRainTicks_ = fixture_.bonusRainTicks_;
    decltype(fixture_.collected_)& collected_ = fixture_.collected_;
    decltype(fixture_.destroyed_)& destroyed_ = fixture_.destroyed_;
    decltype(fixture_.completeTimer_)& completeTimer_ = fixture_.completeTimer_;
    decltype(fixture_.portalCooldown_)& portalCooldown_ = fixture_.portalCooldown_;
    decltype(fixture_.triggerCooldown_)& triggerCooldown_ = fixture_.triggerCooldown_;
    decltype(fixture_.portalCooldown2_)& portalCooldown2_ = fixture_.portalCooldown2_;
    decltype(fixture_.triggerCooldown2_)& triggerCooldown2_ = fixture_.triggerCooldown2_;
    decltype(fixture_.portalDownConsumed_)& portalDownConsumed_ = fixture_.portalDownConsumed_;
    decltype(fixture_.energy_)& energy_ = fixture_.energy_;
    decltype(fixture_.energy2_)& energy2_ = fixture_.energy2_;
    decltype(fixture_.lives_)& lives_ = fixture_.lives_;
    decltype(fixture_.lives2_)& lives2_ = fixture_.lives2_;
    decltype(fixture_.playerDead_)& playerDead_ = fixture_.playerDead_;
    decltype(fixture_.player2Dead_)& player2Dead_ = fixture_.player2Dead_;
    decltype(fixture_.reentryTimer_)& reentryTimer_ = fixture_.reentryTimer_;
    decltype(fixture_.reentryTimer2_)& reentryTimer2_ = fixture_.reentryTimer2_;
    decltype(fixture_.reentryFire1_)& reentryFire1_ = fixture_.reentryFire1_;
    decltype(fixture_.reentryFire2_)& reentryFire2_ = fixture_.reentryFire2_;
    decltype(fixture_.reentryGate_)& reentryGate_ = fixture_.reentryGate_;
    decltype(fixture_.noActivePlayerTicks_)& noActivePlayerTicks_ = fixture_.noActivePlayerTicks_;
    decltype(fixture_.levelRestartPromoted_)& levelRestartPromoted_ = fixture_.levelRestartPromoted_;
    decltype(fixture_.levelIntroFrame_)& levelIntroFrame_ = fixture_.levelIntroFrame_;
    decltype(fixture_.deathStateTimer_)& deathStateTimer_ = fixture_.deathStateTimer_;
    decltype(fixture_.deathStateTimer2_)& deathStateTimer2_ = fixture_.deathStateTimer2_;
    decltype(fixture_.pendingLifeLoss_)& pendingLifeLoss_ = fixture_.pendingLifeLoss_;
    decltype(fixture_.pendingLifeLoss2_)& pendingLifeLoss2_ = fixture_.pendingLifeLoss2_;
    decltype(fixture_.state2Visual_)& state2Visual_ = fixture_.state2Visual_;
    decltype(fixture_.state2Visual2_)& state2Visual2_ = fixture_.state2Visual2_;
    decltype(fixture_.state2Effect_)& state2Effect_ = fixture_.state2Effect_;
    decltype(fixture_.state2Effect2_)& state2Effect2_ = fixture_.state2Effect2_;
    decltype(fixture_.state2VisualCursorPreview_)& state2VisualCursorPreview_ = fixture_.state2VisualCursorPreview_;
    decltype(fixture_.state2VisualRowPreview_)& state2VisualRowPreview_ = fixture_.state2VisualRowPreview_;
    decltype(fixture_.damageCooldown_)& damageCooldown_ = fixture_.damageCooldown_;
    decltype(fixture_.damageCooldown2_)& damageCooldown2_ = fixture_.damageCooldown2_;
    decltype(fixture_.pendingDamage_)& pendingDamage_ = fixture_.pendingDamage_;
    decltype(fixture_.pendingDamage2_)& pendingDamage2_ = fixture_.pendingDamage2_;
    decltype(fixture_.levelResetGeneration_)& levelResetGeneration_ = fixture_.levelResetGeneration_;
    decltype(fixture_.bombInventory_)& bombInventory_ = fixture_.bombInventory_;
    decltype(fixture_.bombInventory2_)& bombInventory2_ = fixture_.bombInventory2_;
    decltype(fixture_.weaponSwitchHoldTicks_)& weaponSwitchHoldTicks_ = fixture_.weaponSwitchHoldTicks_;
    decltype(fixture_.weaponSwitchHoldTicks2_)& weaponSwitchHoldTicks2_ = fixture_.weaponSwitchHoldTicks2_;
    decltype(fixture_.logicTick_)& logicTick_ = fixture_.logicTick_;
    decltype(fixture_.nextActorOrder_)& nextActorOrder_ = fixture_.nextActorOrder_;
    decltype(fixture_.actorSlots_)& actorSlots_ = fixture_.actorSlots_;
    decltype(fixture_.monsterTileDamageDelta_)& monsterTileDamageDelta_ = fixture_.monsterTileDamageDelta_;
    decltype(fixture_.tileSeederResult_)& tileSeederResult_ = fixture_.tileSeederResult_;
    decltype(fixture_.legacyActorSeedsEnabled_)& legacyActorSeedsEnabled_ = fixture_.legacyActorSeedsEnabled_;
    decltype(fixture_.legacyActorAdoptions_)& legacyActorAdoptions_ = fixture_.legacyActorAdoptions_;
    decltype(fixture_.legacyActorRetirements_)& legacyActorRetirements_ = fixture_.legacyActorRetirements_;
    decltype(fixture_.pendingActorConversions_)& pendingActorConversions_ = fixture_.pendingActorConversions_;
    decltype(fixture_.orderedActorPass_)& orderedActorPass_ = fixture_.orderedActorPass_;
    decltype(fixture_.randomSeed_)& randomSeed_ = fixture_.randomSeed_;
    decltype(fixture_.corpseRewardRoll_)& corpseRewardRoll_ = fixture_.corpseRewardRoll_;
    decltype(fixture_.score_)& score_ = fixture_.score_;
    decltype(fixture_.score2_)& score2_ = fixture_.score2_;
    GameplayView currentView() const { return {fixture_.clockedSoundEnabled_, fixture_.soundClockMilliseconds_, fixture_.soundSampleRemainder_, fixture_.level_, fixture_.levelIndex_, fixture_.playerCount_, fixture_.player_, fixture_.player2_, fixture_.spawnerStates_, fixture_.spawnerStorage_, fixture_.monsters_, fixture_.bossLinks_, fixture_.bossSinTable_, fixture_.bossPresent_, fixture_.bossDefeated_, fixture_.bonusDrops_, fixture_.pendingBonuses_, fixture_.bombs_, fixture_.flashes_, fixture_.launchPadMarkers_, fixture_.transientActors_, fixture_.cameraShakeTicks_, fixture_.cameraShakeOffset_, fixture_.explosionEffects_, fixture_.flameRecords_, fixture_.debrisQueue_, fixture_.collapseQueue_, fixture_.damageLaneData_, fixture_.mapPlaneMemory_, fixture_.nextCollapseFragmentWord_, fixture_.bonusRainTicks_, fixture_.collected_, fixture_.destroyed_, fixture_.completeTimer_, fixture_.portalCooldown_, fixture_.triggerCooldown_, fixture_.portalCooldown2_, fixture_.triggerCooldown2_, fixture_.portalDownConsumed_, fixture_.energy_, fixture_.energy2_, fixture_.lives_, fixture_.lives2_, fixture_.playerDead_, fixture_.player2Dead_, fixture_.reentryTimer_, fixture_.reentryTimer2_, fixture_.reentryFire1_, fixture_.reentryFire2_, fixture_.reentryGate_, fixture_.noActivePlayerTicks_, fixture_.levelRestartPromoted_, fixture_.levelIntroFrame_, fixture_.deathStateTimer_, fixture_.deathStateTimer2_, fixture_.pendingLifeLoss_, fixture_.pendingLifeLoss2_, fixture_.state2Visual_, fixture_.state2Visual2_, fixture_.state2Effect_, fixture_.state2Effect2_, fixture_.state2VisualCursorPreview_, fixture_.state2VisualRowPreview_, fixture_.damageCooldown_, fixture_.damageCooldown2_, fixture_.pendingDamage_, fixture_.pendingDamage2_, fixture_.levelResetGeneration_, fixture_.bombInventory_, fixture_.bombInventory2_, fixture_.weaponSwitchHoldTicks_, fixture_.weaponSwitchHoldTicks2_, fixture_.logicTick_, fixture_.nextActorOrder_, fixture_.actorSlots_, fixture_.monsterTileDamageDelta_, fixture_.tileSeederResult_, fixture_.legacyActorSeedsEnabled_, fixture_.legacyActorAdoptions_, fixture_.legacyActorRetirements_, fixture_.pendingActorConversions_, fixture_.orderedActorPass_, fixture_.randomSeed_, fixture_.corpseRewardRoll_, fixture_.score_, fixture_.score2_}; }
    void resetLevel(int index, bool replaceMapAllocation = true);
    LevelIntroPattern makeLevelIntroPattern();
    LevelIntroPattern capturedLevelIntroPattern() const;
    void beginLevelForPlay(int index);
    void finishLevelIntro();
    size_t visibleLevelIntroCharacters(uint32_t now) const;
    void updateLevelIntro(uint32_t now);
    std::optional<size_t> ownedPlayerIndex(const Player& player) const;
    void writePlayerHealth(uint8_t marker, int health);
    void writePlayerAnimation(const Player& player, bool backup = false);
    void writeState2Animation(const State2VisualCursor& cursor);
    void updatePlayerHudEnergy(uint8_t marker, uint16_t value, uint8_t globalState);
    void writePlayerPosition(const Player& player);
    void writePlayerSprite(const Player& player, bool fullDescriptor = false);
    void placePlayerAtStart(Player& player, uint8_t marker);
    UiActions uiActions();
    void onUiKey(Key domainKey, bool& running);
    void tryActivePlayerFireAt(const Player& player, int x, int y, uint8_t playerIndex);
    void startClockedSound();
    void serviceSoundClock();
    bool latchSoundRequest(uint16_t cursor, uint8_t selector);
    bool requestSoundCursor(uint16_t cursor, uint8_t selector);
    bool requestSoundOffset(uint16_t offset, uint8_t selector);
    void clearSoundLatch();
    void pumpSoundLatch();
    bool playCompatibilitySound(size_t hookSlot);
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
    void updateWeaponSwitch(BombInventory& inventory, uint8_t& holdTicks,
                            bool pressed);
    bool portalDownControl(const FrameControls& controls, bool second = false) const;
    void sampleHudInventory(size_t player, BombInventory& inventory, uint8_t globalState);
    void updatePlayerReentryPrepass(const FrameControls& controls);
    void updateWithControls(const FrameControls& controls, float dt);
    void prepareHudObjectives();
    void updateHudScores();
    bool activateLaunchPad(Player& player, bool down, int localY);
    void spawnLaunchPadMarker(int playerX, int localY);
    void spawnPortalMarker(int x, int y);
    void updateLaunchPadMarkers(uint64_t onlyOrder = 0);
    std::vector<OutroLine> levelOutroLines() const;
    std::vector<OutroSegment> levelOutroSchedule() const;
    void beginLevelOutro();
    void updateLevelOutro(uint32_t now);
    void finishLevelOutro();
    void updateLevelCompletion();
    void selectPlayerPosture(Player& player, uint8_t spriteBase, bool dropping);
    void updatePlayerGravity(Player& player, bool bottom, uint8_t spriteBase, int& y);
    void updatePlayer(Player& player, bool left, bool right, bool jump, bool switchWeapon,
                      uint8_t spriteBase, bool down = false);
    void applyPlayerTerrainDamage(Player& player, int& energy);
    void updateDyingPlayerMotion(Player& player);
    void integratePlayerMotion(Player& player, int x, int y,
                                      const ActiveMonster::EdgeFlags& edges);
    static void syncPlayerVelocityMirror(Player& player);
    static int16_t actorFloorFriction(int16_t velocity);
    static int16_t playerWalkVelocity(int16_t velocity, bool left, bool right, bool bottom);
    std::vector<SharedActorEntry> sharedActorEntries() const;
    uint64_t sharedActorVisualKey(const SharedActorEntry& entry) const;
    lezac::gameplay::ActorSlots::Descriptor actorSpriteDescriptor(uint16_t sprite) const;
    void adoptUnorderedActors();
    uint64_t claimActorOrder();
    uint64_t allocateActor(const lezac::gameplay::ActorSlots::Construction& input);
    void retireActor(uint64_t order);
    ActorAnimation conversionBackup(uint64_t order, ActorAnimation legacy = {0, 0, 0, 0, 0, 0, 0}) const;
    void updateOrderedActors(float dt);
    size_t sharedActorCount();
    void updateCameraShake();
    size_t pickupActorCount() const;
    TransientActor* spawnTransientActor(int x, int y, int16_t vy8, uint8_t sprite,
                             uint8_t kind, uint8_t timer,
                             ActorAnimation animation = {0, 0, 0, 0, 0, 0, 1});
    void updateTransientActor(TransientActor& actor);
    void updateTransientActors();
    void collectObjectiveTiles(const Player& player, uint8_t playerIndex);
    void initializePickupTailAnimation();
    void collectObjectiveTiles(const Player& player, uint8_t playerIndex, int originX, int originY);
    bool activatePortal(int& x, int& y, bool down);
    void updatePortalsAndTriggers(Player& player, int& portalCooldown,
                                  int& triggerCooldown, bool down);
    bool applyTileTrigger(uint16_t key);
    void accountTileRewrite(uint8_t from, uint8_t to);
    std::array<int, 2> monsterFrameRange(uint8_t kind) const;
    std::array<int, 2> monsterDirectionalFrameRange(uint8_t kind, int16_t vx8) const;
    static uint8_t monsterHotspotY(uint8_t kind);
    bool actorTouchesPlayer(const Player& player, int ax, int ayCollide) const;
    uint16_t randomRangeValue(uint16_t base, uint16_t range);
    int randomInclusive(int low, int high);
    int16_t groundWalkerSpeed8(const ActiveMonster& monster) const;
    void refreshMonsterAnimationProfile(ActiveMonster& monster);
    void reselectWalkerFacing(ActiveMonster& monster);
    void initializeMonsterMotion(ActiveMonster& monster);
    std::array<int16_t,2> monsterTargetDelta(const ActiveMonster& monster) const;
    const Player& nearestPlayer(float x, float y) const;
    lezac::core::ActorMotionPrefixResult runActorMotionPrefix(lezac::core::ActorMotionPrefixInput input);
    static void requireMotionTerrain(const lezac::core::ActorMotionPrefixResult& result);
    void updateMonsterMotion(ActiveMonster& monster, float argument1);
    void spawnLevel7Boss();
    void spawnLevel7BossFromBank(const GranBank& bank);
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
    void applyGroundMonsterGravity(ActiveMonster& monster);
    void consumeMonsterObjectTiles(uint16_t footprint);
    void updateMonsters(float dt, uint64_t onlyOrder = 0);
    void releaseMonsterSlot(ActiveMonster& monster);
    void updateDamageCooldowns();
    void queuePlayerDamage(uint8_t startMarker, uint8_t amount = 1);
    void drainPlayerDamageCounters();
    void drainPlayerDamageCounter(Player& player, int& energy, int& lives,
                                  bool& dead, int& timer, uint8_t& pending,
                                  uint8_t startMarker);
    void damagePlayer(Player& player, int& energy, int& lives, bool& dead,
                      int& timer, int& damageCooldown, uint8_t startMarker);
    bool playerOverlapsTileArea(const Player& player, int tx0, int ty0,
                                int tx1, int ty1) const;
    void damagePlayersInTileArea(int tx0, int ty0, int tx1, int ty1);
    void beginPlayerDeath(Player& player, int& energy, int& lives, bool& dead,
                          int& timer, uint8_t startMarker);
    State2VisualCursor& state2VisualCursorFor(uint8_t startMarker);
    State2EffectEntry& state2EffectEntryFor(uint8_t startMarker);
    void refreshState2EffectEntry(const Player& player,
                                  const State2VisualCursor& cursor,
                                  State2EffectEntry& entry);
    void resetState2VisualCursor(State2VisualCursor& cursor);
    bool updateState2VisualCursor(State2VisualCursor& cursor);
    bool allPlayersOutOfLives() const;
    int& deathStateTimerFor(uint8_t startMarker);
    bool& pendingLifeLossFor(uint8_t startMarker);
    void finalizePendingLifeLoss(bool& dead, int& lives, int& timer,
                                 uint8_t startMarker);
    bool canReenterLevel() const;
    int remainingObjectiveTiles() const;
    void updateWaitingPlayerPlacement(Player& player);
    void updateReentry(Player& player, int& energy, int& lives, bool& dead,
                       int& timer, uint8_t startMarker, bool allowLevelRestart);
    uint8_t originalPlayerState(uint8_t player) const;
    bool updateSharedReentryFallback();
    void tryReenterPlayer(Player& player, int& energy, int& lives, bool& dead,
                          int& timer, int& damageCooldown, uint8_t startMarker);
    void respawnPlayerAtStart(Player& player, int& energy, uint8_t startMarker);
    void restartCurrentLevelAfterDeath();
    bool scoreQualifies(uint32_t score) const;
    uint32_t& scoreForPlayer(uint8_t player);
    void addScore(uint8_t player, uint32_t amount);
    void clearRunScores();
    bool isFinalLevel() const;
    MenuPage endMenuPage(EndReason reason) const;
    void beginGameOver();
    void abortRun();
    void beginEndRun(EndReason reason);
    void finalizePendingRecord();
    void cancelPendingRecord();
    void clearPendingRecord();
    bool startNextPendingRecord();
    void placeBombAt(const Player& player, BombInventory& inventory, uint8_t owner);
    int bombHeightOffset(BombType type) const;
    void updateBombMotion(Bomb& bomb);
    void updateTimedActorMotion(int& x, int& y, int16_t& vx, int16_t& vy,
            uint8_t& fracX, uint8_t& fracY, const ActiveMonster::EdgeFlags& edges);
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
    bool requestRecordNamePromptSound();
    bool requestRecordNameCommitSound();
    bool requestRecordsPageSound();
    bool requestWeaponSwitchSound();
    bool requestLaunchPadSound();
    bool requestPortalTeleportSound();
    bool requestTileTriggerSound();
    bool requestPlayerDamageSound();
    bool requestPlayerDeathSound();
    bool consumeBombObjectTile(int tx, int ty);
    bool markDamagedTile(int tx, int ty);
    void queueTileDamage(int tx, int ty, uint8_t forwardPhase = 0, uint8_t reversePhase = 0,
                         bool preserveCollapseGlyphs = true, uint8_t* seededClass = nullptr);
    void queuePhysicalTileDamage(uint16_t cell, uint8_t forwardPhase = 0, uint8_t reversePhase = 0,
                                 bool preserveCollapseGlyphs = true, uint8_t* seededClass = nullptr);
    DamagePhaseLookup resolveDamagePhase(uint16_t flaggedWord, bool reverse) const;
    void writeContactWordGuardAlias(size_t index, uint16_t word);
    lezac::gameplay::DamageLaneMemory<lezac::sound::SoundEngine>
    damageLaneMemory(std::array<int*, 4> lanes = {});
    lezac::gameplay::DamageLaneSeed seedDamageLaneContact(uint16_t cell, uint8_t& seededClass);
    void blendDebrisImpactLane(int target, uint16_t word, int& vx, int& subX,
                               int& vy, int& subY, bool reverse);
    void explode(const Bomb& bomb);
    int monsterDamageForBomb(BombType type) const;
    void damageMonstersInExplosion(const std::vector<std::array<int, 2>>& tiles,
                                   BombType type);
    bool monsterOverlapsExplosionTiles(const ActiveMonster& monster,
                                       const std::vector<std::array<int, 2>>& tiles) const;
    bool rectsOverlap(float ax, float ay, float aw, float ah,
                      float bx, float by, float bw, float bh) const;
    void damageMonster(ActiveMonster& monster, int damage, bool updatedThisTick = false);
    bool playerOverlapsAnyExplosionTile(const Player& player,
                                        const std::vector<std::array<int, 2>>& tiles) const;
    void damagePlayersInExplosion(const std::vector<std::array<int, 2>>& tiles);
    int monsterCorpseSprite(const ActiveMonster& monster) const;
    void enterMonsterDeath(ActiveMonster& monster, bool updatedThisTick = false);
    void spawnBonusDrop(float x, float y, BonusType type);
    void finishMonsterDeathReward(ActiveMonster& monster);
    void spawnExpiryParticles(int x, int y, int count = 2);
    void updateBonusDrops(size_t initialDrops = std::numeric_limits<size_t>::max(), uint64_t onlyOrder = 0);
    void applyPendingBonus(const Player& collector, int& energy,
                           BombInventory& inventory, uint8_t playerIndex);
    void applyBonus(BonusType type, const Player& argument1, int& energy,
                    BombInventory& inventory, uint8_t playerIndex = 1);
    void grantNormalBombSet(BombInventory& inventory);
    void grantSuperBombSet(BombInventory& inventory);
    void updateBonusRain();
    void updateDebrisRecords();
    void blendCollapseContacts(const std::vector<DamageContact>& contacts, int& velocity,
                               uint8_t ownWeight, bool reverse);
    void updateCollapseRecords();
    void updateFlashes();
    int destructionPercent() const;
    bool isComplete() const;
    void adjustGameplayViewWidth(int delta);
    int remainingPlayerCount() const;
    void writeViewportDestinations();
    void initializeGameplayView();
    void buildBackdropBuffer();
    std::vector<SharedActorEntry> prepareRenderState();
    lezac::rendering::WorldRenderView worldRenderView(const std::vector<SharedActorEntry>& order) const;
    lezac::rendering::HudView hudView() const;
    lezac::rendering::MenuView menuRenderView() const;
};
}
}
