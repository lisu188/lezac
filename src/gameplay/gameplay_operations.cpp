#include "gameplay/gameplay_operations.hpp"

namespace lezac::gameplay::detail {

void GameplayOperations::resetLevel(int index, bool replaceMapAllocation ) {
        levelFlow_.restoreIntro({});
        levelFlow_.restoreOutro({});
        ++levelResetGeneration_;
        // FreeMem leaves the previous map's rounded size in its alignment gap.
        // The word plane is freed first, so both frees retract the heap top.
        levelIndex_ = (index + static_cast<int>(levels_.size())) % static_cast<int>(levels_.size());
        if (replaceMapAllocation) {
            const auto& next = levels_[levelIndex_];
            mapPlaneMemory_.beginLevel(level_.tiles, level_.wordLayer,
                                      static_cast<size_t>(next.width) * next.height);
        }
        level_ = levels_[levelIndex_];
        presentation_.beginLevel(static_cast<size_t>(level_.width) * level_.height);
        actorSlots_.resetHudDestinations();  // 2B85..2B90, before actor-pool reset.
        player_ = {};
        player2_ = {};
        player2_.animation = ActorAnimation::initialize(21, 28, 1, 1);
        spawnerStates_.clear();
        monsters_.clear();
        bonusDrops_.clear();
        pendingBonuses_.fill(0);
        bombs_.clear();
        flashes_.clear();
        launchPadMarkers_.clear();
        transientActors_.clear();
        cameraShakeTicks_ = cameraShakeOffset_ = 0;
        nextActorOrder_ = 1;
        pendingActorConversions_.clear();
        actorSlots_.resetForLevel(actorSpriteDescriptor(1));
        explosionEffects_.clear();
        flameRecords_.clear();
        debrisQueue_.clear();
        collapseQueue_.clear();
        ui_.setPaused(false);
        nextCollapseFragmentWord_ = level_.fieldA;
        bonusRainTicks_ = 0;
        collected_ = 0;
        destroyed_ = 0;
        presentation_.resetHudForLevel();
        actorSlots_.setSpriteBankTag(2);
        actorSlots_.hudEnergyCache(0) = actorSlots_.hudEnergyCache(1) = 255;
        completeTimer_ = 0;
        portalCooldown_ = 0;
        triggerCooldown_ = 0;
        portalCooldown2_ = 0;
        triggerCooldown2_ = 0;
        portalDownConsumed_.fill(false);
        energy_ = 100;
        energy2_ = 100;
        playerDead_ = false;
        player2Dead_ = false;
        reentryTimer_ = 0;
        reentryTimer2_ = 0;
        reentryFire1_ = reentryFire2_ = false;
        reentryGate_ = true;
        noActivePlayerTicks_ = 0;
        levelRestartPromoted_ = false;
        deathStateTimer_ = 0;
        deathStateTimer2_ = 0;
        pendingLifeLoss_ = false;
        pendingLifeLoss2_ = false;
        state2Visual_ = {};
        state2Visual2_ = {};
        state2Effect_ = {};
        state2Effect2_ = {};
        damageCooldown_ = 0;
        damageCooldown2_ = 0;
        pendingDamage_ = 0;
        pendingDamage2_ = 0;
        bombInventory_ = {};
        bombInventory2_ = {};
        weaponSwitchHoldTicks_ = 0;
        weaponSwitchHoldTicks2_ = 0;
        logicTick_ = 0;
        for (size_t index = 0; index < level_.monsterSpawners.size(); ++index) {
            const MonsterSpawner& spawner = level_.monsterSpawners[index];
            spawnerStorage_.loadRecord(static_cast<uint8_t>(index + 1),
                lezac::resources::packMonsterSpawner(spawner));
            SpawnerState state;
            state.remaining = spawner.spawnBudget;
            state.availableSlots = spawner.liveAllowance;
            state.cooldown = spawner.cooldown;
            spawnerStates_.push_back(state);
        }
        if (playerCount_ > 1) {
            playerDead_ = lives_ < 0;
            player2Dead_ = lives2_ < 0;
        }
        for (uint8_t marker : {uint8_t{1}, uint8_t{2}}) {
            Player& player = marker == 1 ? player_ : player2_;
            if (originalPlayerState(marker) == 1) placePlayerAtStart(player, marker);
            else {
                // 2E1E/2E3D: inactive setup writes both coordinates, unlike elimination.
                player.x = 10000; player.y = 6000;
                writePlayerPosition(player);
            }
        }
        bossLinks_.clear();
        bossPresent_ = false;
        bossDefeated_ = false;
        // The original loads gran.mst at the end of level setup only when the
        // current-level byte DS:0x79B7 equals 7 (callsite 1000:2E78).
        if (levelIndex_ == 6) spawnLevel7Boss();
        initializeGameplayView();
        writeViewportDestinations();
    }

LevelIntroPattern GameplayOperations::makeLevelIntroPattern() {
        return LevelFlow::makeLevelIntroPattern([this](int low, int high) { return randomInclusive(low, high); });
    }

LevelIntroPattern GameplayOperations::capturedLevelIntroPattern() const {
        return LevelFlow::capturedLevelIntroPattern();
    }

void GameplayOperations::beginLevelForPlay(int index) {
        // Original level advance jumps to file 0x7f4c, past the new-game clock reset.
        levelIntroFrame_ = ui_.snapshot().menu ? 0 : logicTick_;
        presentation_.beginOriginalPlay(ui_.snapshot().menu);
        if (ui_.snapshot().menu) {
            bombInventory_ = {};
            bombInventory2_ = {};
            // 2F30/2F35 refill energy only on the new-game path.
            energy_ = energy2_ = 100;
            writePlayerHealth(1, energy_);
            writePlayerHealth(2, energy2_);
            actorSlots_.setPlayerReserve(0, static_cast<uint8_t>(lives_));
            actorSlots_.setPlayerReserve(1, static_cast<uint8_t>(lives2_));
        }
        // 1000:2AF2 resets selection on reload; 2F69 initializes counts only for a new game.
        bombInventory_.selected = bombInventory2_.selected = BombType::Small;
        if (levelRestartPromoted_ && debugReentryBoundaryObserver_) debugReentryBoundaryObserver_("level_init");
        levelIndex_ = (index + static_cast<int>(levels_.size())) % static_cast<int>(levels_.size());
        const auto& next = levels_[levelIndex_];
        mapPlaneMemory_.beginLevel(level_.tiles, level_.wordLayer,
                                  static_cast<size_t>(next.width) * next.height);
        level_ = levels_[levelIndex_];
        // 1000:0E34/0E90 read both compressed planes into DS:C498, the
        // background buffer. Decoder 082D:0000 continues through its retained
        // tail until the requested output length, ignoring compressed length.
        // JSON assets already contain decoded maps, without original input bytes.
        if (!level_.encodedTiles.empty()) {
            auto tiles = presentation_.decodeLevelPlaneWithTail(level_.encodedTiles, level_.tiles.size());
            level_.tiles = std::move(tiles.bytes);
            // Preserve decoder order where an object tail aliases the word allocation.
            mapPlaneMemory_.retainObjectDecoderTail(tiles.tail, level_.tiles, level_.wordLayer);
            const auto words = presentation_.decodeLevelPlaneWithTail(level_.encodedWords, level_.wordLayer.size() * 2);
            for (size_t i = 0; i < level_.wordLayer.size(); ++i) level_.wordLayer[i] = le16(words.bytes, i * 2);
            mapPlaneMemory_.retainWordDecoderTail(words.tail, level_.tiles, level_.wordLayer);
        }
        collected_ = destroyed_ = 0;
        presentation_.resetHudObjectivesForLevel();
        // 1000:2BF9 reloads all of BOMPAL before generating the intro, without resetting DS:79AD.
        presentation_.setPalette(assets_.palette());
        actorSlots_.setSpriteBankTag(1);
        LevelIntroPattern pattern = makeLevelIntroPattern();
        levelFlow_.beginIntro(levelIndex_, std::move(pattern), presentationMilliseconds());
        if (levelRestartPromoted_ && debugReentryBoundaryObserver_) debugReentryBoundaryObserver_("intro_wait");
        if (!levelFlow_.interactiveEnabled()) finishLevelIntro();
    }

void GameplayOperations::finishLevelIntro() {
        if (!levelFlow_.intro().active) return;
        if (levelRestartPromoted_ && debugReentryBoundaryObserver_) debugReentryBoundaryObserver_("intro_ack");
        const int index = levelFlow_.intro().levelIndex;
        const uint32_t frame = levelIntroFrame_;
        const int countdown1 = reentryTimer_, countdown2 = reentryTimer2_;
        const uint8_t fallback = noActivePlayerTicks_;
        const auto counts1 = bombInventory_.counts, counts2 = bombInventory2_.counts;
        const int carriedEnergy1 = energy_, carriedEnergy2 = energy2_;
        Level decodedLevel = std::move(level_);
        resetLevel(index, false);
        level_ = std::move(decodedLevel);
        bombInventory_.counts = counts1;
        bombInventory2_.counts = counts2;
        energy_ = carriedEnergy1;
        energy2_ = carriedEnergy2;
        logicTick_ = frame;
        reentryTimer_ = countdown1;
        reentryTimer2_ = countdown2;
        noActivePlayerTicks_ = fallback;
        player_.animation = ActorAnimation::initialize(2, 9, 1, 1);
        buildBackdropBuffer();
    }

size_t GameplayOperations::visibleLevelIntroCharacters(uint32_t now) const {
        return levelFlow_.visibleLevelIntroCharacters(now);
    }

void GameplayOperations::updateLevelIntro(uint32_t now) {
        levelFlow_.updateLevelIntro(now);
    }

std::optional<size_t> GameplayOperations::ownedPlayerIndex(const Player& player) const {
        if (&player == &player_) return 0;
        if (&player == &player2_) return 1;
        return std::nullopt; // Value-only fragment probes have no physical owner.
    }

void GameplayOperations::writePlayerHealth(uint8_t marker, int health) {
        actorSlots_.setPlayerHealth(marker - 1, static_cast<uint8_t>(health));
        if (debugPlayerHealthWriteObserver_) debugPlayerHealthWriteObserver_(marker, static_cast<uint8_t>(health));
    }

void GameplayOperations::writePlayerAnimation(const Player& player, bool backup ) {
        if (const auto index = ownedPlayerIndex(player))
            actorSlots_.setPlayerAnimation(*index, backup ? player.animationBackup : player.animation, backup);
    }

void GameplayOperations::writeState2Animation(const State2VisualCursor& cursor) {
        const size_t index = &cursor == &state2Visual_ ? 0 : 1;
        if (&cursor != &state2Visual_ && &cursor != &state2Visual2_) return;
        actorSlots_.setPlayerAnimation(index, ActorAnimation{cursor.current, cursor.first, cursor.last,
            cursor.counter, cursor.delay, cursor.mode, cursor.step});
    }

void GameplayOperations::updatePlayerHudEnergy(uint8_t marker, uint16_t value, uint8_t globalState) {
        presentation_.updateHudEnergy(marker - 1, value, globalState, actorSlots_.hudEnergyCache(marker - 1));
    }

void GameplayOperations::writePlayerPosition(const Player& player) {
        if (const auto index = ownedPlayerIndex(player))
            actorSlots_.setPlayerPosition(*index, static_cast<uint16_t>(static_cast<int>(player.x)),
                static_cast<uint16_t>(static_cast<int>(player.y)));
    }

void GameplayOperations::writePlayerSprite(const Player& player, bool fullDescriptor ) {
        if (const auto index = ownedPlayerIndex(player)) {
            const auto descriptor = actorSpriteDescriptor(player.spriteIndex + 1);
            if (fullDescriptor) actorSlots_.setPlayerDescriptor(*index, descriptor);
            else actorSlots_.setPlayerSpriteOffset(*index, descriptor);
        }
    }

void GameplayOperations::placePlayerAtStart(Player& player, uint8_t marker) {
        const auto [x, y] = lezac::gameplay::playerStart(level_.portals, marker);
        player.x = static_cast<float>(x);
        player.y = static_cast<float>(y);
        player.idleTicks = 0;
        if (const auto index = ownedPlayerIndex(player)) actorSlots_.setPlayerIdle(*index, 0);
        writePlayerPosition(player);
    }

UiActions GameplayOperations::uiActions() {
        return {
            [this] { clearRunScores(); },
            [this](int players) {
                playerCount_ = players;
                lives_ = kInitialReserveLives;
                lives2_ = kInitialReserveLives;
            },
            [this](int index) { beginLevelForPlay(index); },
            [this] {
                lives_ = kInitialReserveLives;
                lives2_ = kInitialReserveLives;
                resetLevel(0);
                actorSlots_.setSpriteBankTag(1);
            },
            [this] { requestRecordNamePromptSound(); },
            [this] { requestRecordNameCommitSound(); },
            [this] { requestRecordsPageSound(); },
            [this](int player) {
                (player == 2 ? reentryFire2_ : reentryFire1_) = true;
            },
            [this](int delta) { adjustGameplayViewWidth(delta); },
            [this] { abortRun(); },
            [this] {
                presentation_.setPalette(assets_.backgroundPalette());
                endScreenPattern_ = makeLevelIntroPattern();
            },
            [this] {
                presentation_.setPalette(assets_.palette());
                endScreenPattern_ = makeLevelIntroPattern();
            },
            [this] { return remainingPlayerCount() == 1; },
        };
    }

void GameplayOperations::onUiKey(Key domainKey, bool& running) {
        if (levelFlow_.intro().active) {
            if (levelFlow_.introWaitingForKey(presentationMilliseconds())) finishLevelIntro();
            else {
                levelFlow_.skipIntroTyping();
                flushBufferedMenuKeys();
            }
            return;
        }
        if (levelFlow_.outro().active) {
            if (levelFlow_.outro().awaitKey) finishLevelOutro();
            else levelFlow_.skipOutroTyping(presentationMilliseconds(), ui_.snapshot().italian);
            return;
        }
        const uint32_t now = presentationMilliseconds();
        const bool menuSkip = ui_.snapshot().menu && ui_.snapshot().page == MenuPage::Main &&
                              !ui_.mainMenuProgress(now).waitingForKey;
        ui_.onKey(domainKey, running, levelIndex_, playerCount_, recordStore_, uiActions(), now);
        if (menuSkip) flushBufferedMenuKeys();
    }

void GameplayOperations::tryActivePlayerFireAt(const Player& player, int x, int y, uint8_t playerIndex) {
        if (!(playerIndex == 2 ? reentryFire2_ : reentryFire1_)) return;
        Player launch = player;
        launch.x = static_cast<float>(x);
        launch.y = static_cast<float>(y);
        placeBombAt(launch, playerIndex == 2 ? bombInventory2_ : bombInventory_, playerIndex);
    }

void GameplayOperations::startClockedSound() {
        clockedSoundEnabled_ = true;
        soundClockMilliseconds_ = presentationMilliseconds();
        soundSampleRemainder_ = 0;
    }

void GameplayOperations::serviceSoundClock() {
        if (!clockedSoundEnabled_) return;
        const uint32_t now = presentationMilliseconds();
        const uint32_t elapsed = now - soundClockMilliseconds_;
        soundClockMilliseconds_ = now;
        const uint64_t scaled = uint64_t{elapsed} * kAudioSampleRate + soundSampleRemainder_;
        soundSampleRemainder_ = static_cast<uint32_t>(scaled % 1000);
        const uint64_t remaining = scaled / 1000;
        if (remaining > lezac::sound::kMaximumClockedTailSamples) {
            audioOutput_.discardClockedSamples();
        }
        audioOutput_.playClockedSamples(sound_.renderClockedTail(remaining));
    }

bool GameplayOperations::latchSoundRequest(uint16_t cursor, uint8_t selector) {
        serviceSoundClock();
        return sound_.latchSoundRequest(cursor, selector);
    }

bool GameplayOperations::requestSoundCursor(uint16_t cursor, uint8_t selector) {
        serviceSoundClock();
        return sound_.requestSoundCursor(cursor, selector);
    }

bool GameplayOperations::requestSoundOffset(uint16_t offset, uint8_t selector) {
        serviceSoundClock();
        return sound_.requestSoundOffset(offset, selector);
    }

void GameplayOperations::clearSoundLatch() {
        serviceSoundClock();
        sound_.clearSoundLatch(true);
    }

void GameplayOperations::pumpSoundLatch() {
        if (clockedSoundEnabled_) {
            serviceSoundClock();
            return;
        }
        audioOutput_.playSamples(sound_.pumpSoundLatch());
    }

bool GameplayOperations::playCompatibilitySound(size_t hookSlot) {
        serviceSoundClock();
        return sound_.playCompatibilitySound(hookSlot);
    }

int GameplayOperations::tileAt(int tx, int ty) const {
        if (tx < 0 || ty < 0 || tx >= level_.width || ty >= level_.height) return 0;
        return level_.tiles[static_cast<size_t>(ty) * level_.width + tx];
    }

uint16_t GameplayOperations::wordAt(int tx, int ty) const {
        if (tx < 0 || ty < 0 || tx >= level_.width || ty >= level_.height) return 0;
        size_t index = static_cast<size_t>(ty) * level_.width + tx;
        return index < level_.wordLayer.size() ? level_.wordLayer[index] : 0;
    }

uint8_t& GameplayOperations::tileRef(int tx, int ty) {
        return level_.tiles[static_cast<size_t>(ty) * level_.width + tx];
    }

uint16_t& GameplayOperations::wordRef(int tx, int ty) {
        return level_.wordLayer[static_cast<size_t>(ty) * level_.width + tx];
    }

bool GameplayOperations::solidPixel(float px, float py) const {
        int tx = static_cast<int>(px) / kTileSize;
        int ty = static_cast<int>(py) / kTileSize;
        uint8_t tileByte = static_cast<uint8_t>(tileAt(tx, ty));
        return countsForDestructionProgress(tileByte, level_.objectiveTile) &&
               !isPassableObjectCell(tx, ty);
    }

bool GameplayOperations::solidTileSide(uint8_t t) { return t >= 1 && t <= 0x4c; }

bool GameplayOperations::solidTileBottom(uint8_t t) { return t >= 1 && t <= 0x52; }

ActiveMonster::EdgeFlags GameplayOperations::scanActorEdges(int x, int yCollide) const {
        const int C = (x + 4) >> 3;
        const int R = yCollide >> 3;
        auto side = [&](int c, int r) { return solidTileSide(static_cast<uint8_t>(tileAt(c, r))); };
        auto bot = [&](int c, int r) { return solidTileBottom(static_cast<uint8_t>(tileAt(c, r))); };
        ActiveMonster::EdgeFlags e;
        e.top = side(C, R - 1) || side(C + 1, R - 1);
        e.bottom = bot(C, R + 2) || bot(C + 1, R + 2);
        e.left = side(C - 1, R) || side(C - 1, R + 1);
        e.right = side(C + 2, R) || side(C + 2, R + 1);
        return e;
    }

bool GameplayOperations::scanActorStrongBottom(int x, int yCollide) const {
        const int column = (x + 4) >> 3;
        const int row = yCollide >> 3;
        return solidTileSide(
                   static_cast<uint8_t>(tileAt(column, row + 2))) ||
               solidTileSide(
                   static_cast<uint8_t>(tileAt(column + 1, row + 2)));
    }

bool GameplayOperations::collides(float x, float y) const {
        return solidPixel(x, y) || solidPixel(x + 11.0f, y) ||
               solidPixel(x, y + 15.0f) || solidPixel(x + 11.0f, y + 15.0f);
    }

bool GameplayOperations::monsterCollides(float x, float y) const {
        return solidPixel(x, y) || solidPixel(x + 13.0f, y) ||
               solidPixel(x, y + 15.0f) || solidPixel(x + 13.0f, y + 15.0f);
    }

bool GameplayOperations::playerOverlaps(const Player& player, float x, float y, float w, float h) const {
        return player.x < x + w && player.x + 12.0f > x &&
               player.y < y + h && player.y + 16.0f > y;
    }

int GameplayOperations::bombTypeIndex(BombType type) const {
        return static_cast<int>(type);
    }

int GameplayOperations::explosionVisualType(BombType type) const {
        return std::clamp(bombTypeIndex(type) + 1, 1, 4);
    }

uint8_t GameplayOperations::explosionDispatcherState(int visualSelector) const {
        return static_cast<uint8_t>(std::clamp(visualSelector + 3, 4, 7));
    }

int GameplayOperations::explosionEffectTicks(int visualType) const {
        switch (visualType) {
            case 1: return 8;
            case 2: return 9;
            case 3: return 9;
            case 4: return 0x3a;
        }
        return 8;
    }

uint8_t GameplayOperations::explosionVariantByte(int visualType) const {
        switch (visualType) {
            case 1: return 5;
            case 2: return 5;
            case 3: return 3;
            case 4: return 0x0a;
        }
        return 5;
    }

uint16_t GameplayOperations::explosionSoundOffset(int visualType) const {
        if (visualType >= 1 &&
            visualType <= static_cast<int>(kExplosionDirectSweepSoundOffsets.size())) {
            return kExplosionDirectSweepSoundOffsets[static_cast<size_t>(visualType - 1)];
        }
        return kExplosionDirectSweepSoundOffsets[0];
    }

uint8_t GameplayOperations::explosionSoundSelector(int visualType) const {
        if (visualType >= 1 &&
            visualType <= static_cast<int>(kExplosionSoundSelectors.size())) {
            return kExplosionSoundSelectors[static_cast<size_t>(visualType - 1)];
        }
        return kExplosionSoundSelectors[0];
    }

bool GameplayOperations::hasBomb(const BombInventory& inventory, BombType type) const {
        return inventory.counts[static_cast<size_t>(bombTypeIndex(type))] > 0;
    }

void GameplayOperations::selectNextAvailableBomb(BombInventory& inventory) {
        // 6859 dirties the icon even when the cycle returns to the same type.
        inventory.hudDirty = 2;
        int start = bombTypeIndex(inventory.selected);
        for (int step = 1; step <= 4; ++step) {
            int idx = (start + step) % 4;
            if (inventory.counts[static_cast<size_t>(idx)] > 0) {
                inventory.selected = static_cast<BombType>(idx);
                return;
            }
        }
    }

void GameplayOperations::updateWeaponSwitch(BombInventory& inventory, uint8_t& holdTicks,
                            bool pressed) {
        if (pressed) {
            ++holdTicks;
            return;
        }
        if (holdTicks >= kWeaponSwitchHoldTicks) {
            requestWeaponSwitchSound();
            selectNextAvailableBomb(inventory);
        }
        holdTicks = 0;
    }

bool GameplayOperations::portalDownControl(const FrameControls& controls, bool second ) const {
        const bool c = controls.hasPhysicalDownBanks ? controls.physicalCDown : controls.p1Down;
        const bool arrow = controls.hasPhysicalDownBanks ? controls.physicalArrowDown : controls.p2Down;
        if (second) return arrow && !portalDownConsumed_[1];
        return (c && !portalDownConsumed_[0]) ||
               (playerCount_ == 1 && arrow && !portalDownConsumed_[1]);
    }

void GameplayOperations::sampleHudInventory(size_t player, BombInventory& inventory, uint8_t globalState) {
        // 326E writes DS:79A3 when repainting the icon, before clearing its dirty byte.
        if (globalState == 1 && inventory.hudDirty > 1) corpseRewardRoll_ = 18;
        presentation_.sampleHudInventory(player, inventory, globalState);
    }

void GameplayOperations::updatePlayerReentryPrepass(const FrameControls& controls) {
        // State-2 countdown precedes both actor passes (1000:7C89).
        // 1000:7E9D/7EA2 clear BOTH latches on the first successful reentry.
        if (!reentryGate_) noActivePlayerTicks_ = kSharedReentryTicks - 1;
        reentryFire1_ = reentryFire1_ || controls.p1Reenter;
        reentryFire2_ = reentryFire2_ || controls.p2Reenter;
        sampleHudInventory(0, bombInventory_, originalPlayerState(1));
        if (playerDead_) {
            updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                          playerCount_ == 1 || player2Dead_);
        }
        // 7DB5 samples each latch into DS:79A3 before reentry clears both.
        corpseRewardRoll_ = static_cast<uint8_t>(reentryGate_ && reentryFire1_);
        if (playerDead_ && reentryFire1_)
            tryReenterPlayer(player_, energy_, lives_, playerDead_, reentryTimer_, damageCooldown_, 1);
        if (playerCount_ > 1) sampleHudInventory(1, bombInventory2_, originalPlayerState(2));
        if (playerCount_ > 1 && player2Dead_) {
            updateReentry(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_, 2,
                          playerDead_);
        }
        corpseRewardRoll_ = static_cast<uint8_t>(reentryGate_ && reentryFire2_);
        if (playerCount_ > 1 && player2Dead_ && reentryFire2_)
            tryReenterPlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_, damageCooldown2_, 2);
    }

void GameplayOperations::updateWithControls(const FrameControls& controls, float dt) {
        if (ui_.snapshot().menu || ui_.snapshot().paused || levelFlow_.intro().active) return;
        if (levelFlow_.outro().active) {
            updateLevelOutro(presentationMilliseconds());
            pumpSoundLatch();
            return;
        }
        ++logicTick_;
        prepareHudObjectives();
        if (gameplayPresentation_) gameplayPresentation_();
        // 1000:7A6B precedes state-2 and both actor passes. An effect that
        // expires later this frame still occupies its slot during spawning.
        updateMonsterSpawners();
        updatePlayerReentryPrepass(controls);
        if (ui_.snapshot().menu || levelFlow_.intro().active) return;
        // 1000:7ECB..7EE8 precedes the player calls at 7F59. New pickup
        // and collapse-fracture actors therefore start on the next frame.
        updateDamageCooldowns();
        bool p1Switch = controls.p1Left && controls.p1Right;
        bool p2Switch = controls.p2Left && controls.p2Right;
        if (!(controls.hasPhysicalDownBanks ? controls.physicalCDown : controls.p1Down)) portalDownConsumed_[0] = false;
        if (!(controls.hasPhysicalDownBanks ? controls.physicalArrowDown : controls.p2Down)) portalDownConsumed_[1] = false;
        bool p1Jump = controls.p1Jump && !portalDownControl(controls);
        bool p1Down = portalDownControl(controls) && !controls.p1Jump;
        bool p2Jump = controls.p2Jump && !controls.p2Down;
        bool p2Down = controls.p2Down && !controls.p2Jump;
        updateWeaponSwitch(bombInventory_, weaponSwitchHoldTicks_, p1Switch);
        if (playerCount_ > 1) {
            updateWeaponSwitch(bombInventory2_, weaponSwitchHoldTicks2_, p2Switch);
        } else {
            weaponSwitchHoldTicks2_ = 0;
        }
        if (portalCooldown_ > 0) --portalCooldown_;
        if (triggerCooldown_ > 0) --triggerCooldown_;
        if (portalCooldown2_ > 0) --portalCooldown2_;
        if (triggerCooldown2_ > 0) --triggerCooldown2_;

        // 1000:7ECB..7EE8 dispatches non-player actors before the players
        // at 7F4E..7F5B. Both precede flame/debris 805D and collapse 8067.
        updateBossLinks();
        pendingBonuses_.fill(0);
        updateOrderedActors(dt);
        if (debugActorPassObserver_) debugActorPassObserver_();
        if (updateSharedReentryFallback()) return;

        if (playerDead_) {
            if (deathStateTimer_ > 0) {
                if (updateState2VisualCursor(state2Visual_)) {
                    player_.spriteIndex = state2Visual_.current - 1;
                    player_.singlePixelSprite = false;
                    writePlayerSprite(player_);
                }
                updateDyingPlayerMotion(player_);
            }
            refreshState2EffectEntry(player_, state2Visual_, state2Effect_);
        } else {
            updatePlayer(player_, controls.p1Left, controls.p1Right, p1Jump, p1Switch, 0, p1Down);
            updatePortalsAndTriggers(player_, portalCooldown_, triggerCooldown_, false);
        }
        if (playerCount_ > 1) {
            if (player2Dead_) {
                if (deathStateTimer2_ > 0) {
                    if (updateState2VisualCursor(state2Visual2_)) {
                        player2_.spriteIndex = state2Visual2_.current - 1;
                        player2_.singlePixelSprite = false;
                        writePlayerSprite(player2_);
                    }
                    updateDyingPlayerMotion(player2_);
                }
                refreshState2EffectEntry(player2_, state2Visual2_, state2Effect2_);
            } else {
                p2Jump = controls.p2Jump && !portalDownControl(controls, true);
                p2Down = portalDownControl(controls, true) && !controls.p2Jump;
                updatePlayer(player2_, controls.p2Left, controls.p2Right, p2Jump, p2Switch, 19, p2Down);
                updatePortalsAndTriggers(player2_, portalCooldown2_, triggerCooldown2_,
                                         false);
            }
        }
        drainPlayerDamageCounters();
        updateHudScores();
        updateFlashes();
        updateCameraShake();
        updateBonusRain();
        presentation_.advanceHudPalette();
        presentation_.updateRedPalette(static_cast<uint16_t>(logicTick_));
        // DAC writes recolor the already-painted VGA frame without an actor redraw.
        if (gameplayPalettePresentation_) gameplayPalettePresentation_();
        updateLevelCompletion();
        pumpSoundLatch();
    }

void GameplayOperations::prepareHudObjectives() {
        presentation_.prepareHudObjectives(static_cast<uint16_t>(logicTick_), collected_, destructionPercent(),
                                           level_.requiredBonus, level_.requiredDestruction,
                                           [this](uint16_t value) { actorSlots_.setSharedResult(value); });
    }

void GameplayOperations::updateHudScores() {
        const auto& aliases = actorSlots_.state().links[0];
        const auto destination = [&](size_t at) {
            return static_cast<uint16_t>(aliases[at] | (uint16_t{aliases[at + 1]} << 8));
        };
        presentation_.updateHudScores(playerCount_, {{score_, score2_}}, {{playerDead_, player2Dead_}},
                                      {{deathStateTimer_, deathStateTimer2_}},
                                      [this](uint16_t value) { actorSlots_.setSharedResult(value); },
                                      {{destination(10), destination(12)}});
    }

bool GameplayOperations::activateLaunchPad(Player& player, bool down, int localY) {
        if (!down) return false;
        int tx = (static_cast<int>(player.x) + 4) >> 3;
        int ty = (static_cast<int>(player.y) >> 3) + 2;
        if (tileAt(tx, ty) != kLaunchPadTile ||
            scanActorEdges(static_cast<int>(player.x), static_cast<int>(player.y)).top) {
            return false;
        }

        // The original's launch-pad impulse is -2000 in 8.8 (byte-cited as
        // kOriginalLaunchPadVelocity). With the player on the fixed-point
        // model it is used directly instead of through a px/s conversion.
        player.vy8 = kOriginalLaunchPadVelocity;
        syncPlayerVelocityMirror(player);
        player.grounded = false;
        requestLaunchPadSound();
        // 1000:691F..6950 launches and requests sound before the shared
        // constructor can reject the cosmetic marker at its 30-slot limit.
        spawnLaunchPadMarker(static_cast<int>(player.x), localY);
        return true;
    }

void GameplayOperations::spawnLaunchPadMarker(int playerX, int localY) {
        LaunchPadMarker marker;
        marker.x = static_cast<int16_t>(playerX + 4);
        marker.y = static_cast<int16_t>(localY + 13);
        marker.actorOrder = allocateActor({marker.kind, marker.timer, marker.mode, marker.frame,
            marker.velocityX8, marker.velocityY8, static_cast<int16_t>(marker.x), static_cast<int16_t>(marker.y)});
        if (!marker.actorOrder) return;
        // 1000:695F clears only mode; the other active/backup bytes survive reuse.
        actorSlots_.disableAnimation(marker.actorOrder);
        marker.animation = actorSlots_.activeAnimation(marker.actorOrder);
        launchPadMarkers_.push_back(marker);
    }

void GameplayOperations::spawnPortalMarker(int x, int y) {
        LaunchPadMarker marker;
        marker.x = static_cast<int16_t>(x);
        marker.y = static_cast<int16_t>(y);
        marker.velocityY8 = 0;
        marker.timer = kPortalMarkerTimer;
        marker.frame = kPortalMarkerFirstFrame;
        marker.animation = ActorAnimation::initialize(kPortalMarkerFirstFrame,
            kPortalMarkerLastFrame, kPortalMarkerDelay, 1);
        marker.actorOrder = allocateActor({marker.kind, marker.timer, marker.mode, marker.frame,
            marker.velocityX8, marker.velocityY8, static_cast<int16_t>(marker.x), static_cast<int16_t>(marker.y)});
        if (!marker.actorOrder) return;
        actorSlots_.setActiveAnimation(marker.actorOrder, marker.animation);
        launchPadMarkers_.push_back(marker);
    }

void GameplayOperations::updateLaunchPadMarkers(uint64_t onlyOrder ) {
        adoptUnorderedActors();
        for (LaunchPadMarker& marker : launchPadMarkers_) {
            if (onlyOrder && marker.actorOrder != onlyOrder) continue;
            const bool advanced = lezac::gameplay::advanceLaunchPadMarker(marker,
                actorSlots_.animationBackup(marker.actorOrder), logicTick_);
            const auto descriptor = advanced ? actorSpriteDescriptor(marker.frame) : lezac::gameplay::ActorSlots::Descriptor{};
            actorSlots_.writeMarker(marker.actorOrder, marker, advanced, descriptor);
        }
        for (const auto& marker : launchPadMarkers_)
            if ((!onlyOrder || marker.actorOrder == onlyOrder) && marker.timer == 0) retireActor(marker.actorOrder);
        launchPadMarkers_.erase(
            std::remove_if(launchPadMarkers_.begin(), launchPadMarkers_.end(),
                           [onlyOrder](const LaunchPadMarker& marker) {
                               return (!onlyOrder || marker.actorOrder == onlyOrder) && marker.timer == 0;
                           }),
            launchPadMarkers_.end());
    }

std::vector<OutroLine> GameplayOperations::levelOutroLines() const {
        return levelFlow_.levelOutroLines(ui_.snapshot().italian);
    }

std::vector<OutroSegment> GameplayOperations::levelOutroSchedule() const {
        return levelFlow_.levelOutroSchedule(ui_.snapshot().italian);
    }

void GameplayOperations::beginLevelOutro() {
        presentation_.freezeOutroBackdrop(canvas_);
        levelFlow_.beginOutro(presentationMilliseconds(), destroyed_,
            {{!playerDead_ || lives_ >= 0, playerCount_ > 1 && (!player2Dead_ || lives2_ >= 0)}},
            {{bombInventory_.counts, bombInventory2_.counts}}, {{score_, score2_}}, presentation_.hudScores());
    }

void GameplayOperations::updateLevelOutro(uint32_t now) {
        levelFlow_.updateOutro(now, ui_.snapshot().italian,
            [this] {
                auto palette = presentation_.palette();
                palette[255] = {vga6To8(31), vga6To8(31), vga6To8(31)};
                presentation_.setPalette(palette);
                requestSoundCursor(0x3d, 10);
            },
            [this](size_t p, uint32_t delta) {
                auto& score = p == 0 ? score_ : score2_;
                score += delta;
                presentation_.beginResultScore(p, score);
                if (debugResultReelObserver_) debugResultReelObserver_(p);
            },
            [this](size_t p) { presentation_.advanceResultScore(p); },
            [this](size_t p) {
                if (randomRangeValue(0, 4) > 2) requestSoundCursor(0x21, 10);
                if (debugResultReelObserver_) debugResultReelObserver_(p);
            }, debugResultTypingObserver_);
    }

void GameplayOperations::finishLevelOutro() {
        levelFlow_.finishOutro([this](size_t p, uint32_t delta) { (p == 0 ? score_ : score2_) += delta; });
        if (isFinalLevel()) beginEndRun(EndReason::CompletedGame);
        else beginLevelForPlay(levelIndex_ + 1);
    }

void GameplayOperations::updateLevelCompletion() {
        const bool ready = levelFlow_.interactiveEnabled()
            ? presentation_.hudBonusComplete() && presentation_.hudDestructionComplete() && collapseQueue_.empty()
            : isComplete();
        if (ready) {
            // Interactive play runs the recovered original completion-banner
            // sequence (typed lines, score count-up, key wait). The
            // deterministic test/autoplayer path keeps the immediate timed
            // advance.
            if (levelFlow_.interactiveEnabled()) {
                if (!levelFlow_.outro().active) beginLevelOutro();
                updateLevelOutro(presentationMilliseconds());
                return;
            }
            if (completeTimer_ == 0) {
                playCompatibilitySound(kLevelCompleteCompatibilityHookSlot);
            }
            if (++completeTimer_ > 100) {
                if (isFinalLevel()) {
                    beginEndRun(EndReason::CompletedGame);
                } else {
                    beginLevelForPlay(levelIndex_ + 1);
                }
            }
        } else {
            completeTimer_ = 0;
        }
    }

void GameplayOperations::selectPlayerPosture(Player& player, uint8_t spriteBase, bool dropping) {
        // 1000:6772..67FE and 69BB..6A43 preserve the running cursor, or
        // initialize an idle backup, before selecting the temporary pose.
        if (player.animation.first == spriteBase + 18) return;
        player.animationBackup = player.animation.mode == 0 ?
            ActorAnimation::initialize(spriteBase + 1, spriteBase + 1, 2, 3) : player.animation;
        writePlayerAnimation(player, true);
        player.animation = ActorAnimation::initialize(spriteBase + 17,
                                                       spriteBase + (dropping ? 19 : 18), 3, 3);
        writePlayerAnimation(player);
        player.spriteIndex = spriteBase + 17;
        player.singlePixelSprite = false;
        writePlayerSprite(player, true);
    }

void GameplayOperations::updatePlayerGravity(Player& player, bool bottom, uint8_t spriteBase, int& y) {
        // 1000:6743..6813 precedes input; a new jump does not add gravity.
        if (!bottom || player.vy8 < 0) {
            const int16_t accelerated = static_cast<int16_t>(player.vy8 + kPlayerGravity8);
            player.vy8 = std::min<int16_t>(kPlayerTerminalVelocity8, accelerated);
        } else if (player.vy8 > 0) {
            y &= ~7;
            if (player.vy8 > 1600) {
                selectPlayerPosture(player, spriteBase, false);
                player.vy8 = static_cast<int16_t>(-player.vy8 / 4);
            } else {
                player.vy8 = 0;
            }
        }
    }

void GameplayOperations::updatePlayer(Player& player, bool left, bool right, bool jump, bool switchWeapon,
                      uint8_t spriteBase, bool down ) {
        const bool animationEnabled = player.animation.mode != 0;
        const bool animationAdvanced = player.animation.advance(player.animationBackup);
        if (animationEnabled) writePlayerAnimation(player);
        if (animationAdvanced) {
            player.spriteIndex = static_cast<uint8_t>(player.animation.current - 1);
            player.singlePixelSprite = false;
            writePlayerSprite(player);
        }
        const uint8_t inputFrame = player.animation.current;
        int x = static_cast<int>(player.x);
        int y = static_cast<int>(player.y);
        auto edges = scanActorEdges(x, y);
        const int column = (x + 4) >> 3;
        const int row = y >> 3;
        const bool stepLeft = edges.left && !solidTileSide(static_cast<uint8_t>(tileAt(column - 1, row)));
        const bool stepRight = edges.right && !solidTileSide(static_cast<uint8_t>(tileAt(column + 2, row)));
        left = left && !switchWeapon;
        right = right && !switchWeapon;

        updatePlayerGravity(player, edges.bottom, spriteBase, y);
        if (!switchWeapon) {
            activateLaunchPad(player, down, y);
            activatePortal(x, y, down);
            const int bottomLeft = tileAt(column, row + 2);
            const bool specialDown = bottomLeft == 0x45 ||
                (bottomLeft == kLaunchPadTile && !edges.top);
            if (down && !specialDown) {
                if (!edges.bottom || player.vy8 != 0 || player.dropTicks != 0 ||
                    scanActorStrongBottom(x, static_cast<int>(player.y))) {
                    down = false;
                } else {
                    selectPlayerPosture(player, spriteBase, true);
                    player.dropTicks = 4;
                    if (const auto index = ownedPlayerIndex(player)) actorSlots_.setPlayerDropTicks(*index, 4);
                }
            }
            if (player.dropTicks != 0) {
                // 1000:6A5E..6A76 lowers the local Y before integration.
                y += 2;
                --player.dropTicks;
                if (const auto index = ownedPlayerIndex(player)) actorSlots_.setPlayerDropTicks(*index, player.dropTicks);
                player.idleTicks = 0xF8;
                if (const auto index = ownedPlayerIndex(player)) actorSlots_.setPlayerIdle(*index, player.idleTicks);
            }
        }
        if (left) {
            if (stepLeft) {
                player.vy8 = -500;
                player.vx8 = -250;
                edges.left = false;
            }
            // DS:0065 is 17, but DS:0069 ends P2's shorter band at 35.
            const uint8_t lastLeft = spriteBase == 19 ? 35 : 17;
            if (inputFrame < spriteBase + 10 || inputFrame > lastLeft) {
                player.animation = ActorAnimation::initialize(spriteBase + 10, lastLeft, 0, 1);
                writePlayerAnimation(player);
                player.idleTicks = 0;
                if (const auto index = ownedPlayerIndex(player)) actorSlots_.setPlayerIdle(*index, 0);
            }
        }
        if (right) {
            if (stepRight) {
                player.vy8 = -500;
                player.vx8 = 250;
                edges.right = false;
            }
            if (inputFrame < spriteBase + 2 || inputFrame > spriteBase + 9) {
                player.animation = ActorAnimation::initialize(spriteBase + 2, spriteBase + 9, 0, 1);
                writePlayerAnimation(player);
                player.idleTicks = 0;
                if (const auto index = ownedPlayerIndex(player)) actorSlots_.setPlayerIdle(*index, 0);
            }
        }
        player.vx8 = playerWalkVelocity(player.vx8, left, right, edges.bottom);
        player.animation.delay = static_cast<uint8_t>(4 - std::abs(player.vx8) / 256);
        writePlayerAnimation(player);
        if (!left && !right && !down) {
            ++player.idleTicks;
            if (const auto index = ownedPlayerIndex(player)) actorSlots_.setPlayerIdle(*index, player.idleTicks);
            if (player.idleTicks == 5) {
                player.animation.mode = 0;
                // The cursor becomes 1 even for player 2; its displayed idle
                // descriptor is independently selected as 20 (1000:6BAD..6BD1).
                player.animation.current = 1;
                writePlayerAnimation(player);
                player.spriteIndex = spriteBase;
                player.singlePixelSprite = false;
                writePlayerSprite(player, true);
            }
        }
        if (jump && edges.bottom && player.vy8 == 0) {
            player.vy8 = kPlayerJumpVelocity8;
        }
        // 1000:6BD5 uses the updated velocity and local drop/ground Y, before
        // terrain damage and integration. The non-player pass is already over.
        tryActivePlayerFireAt(player, x, y, spriteBase == 19 ? 2 : 1);
        // 1000:6D98/6DAB use these locals after ground snap/drop, not the
        // still-unmodified visual position. The four-cell scan stays cached.
        collectObjectiveTiles(player, spriteBase == 19 ? 2 : 1, x, y);
        applyPendingBonus(player, spriteBase == 19 ? energy2_ : energy_,
                          spriteBase == 19 ? bombInventory2_ : bombInventory_,
                          spriteBase == 19 ? 2 : 1);
        applyPlayerTerrainDamage(player, spriteBase == 19 ? energy2_ : energy_);
        integratePlayerMotion(player, x, y, edges);
    }

void GameplayOperations::applyPlayerTerrainDamage(Player& player, int& energy) {
        // 1000:6F90..7011 scans TL, TR, BR, BL before integration. Only
        // the last flame cell supplies impulse, using its highest pool slot.
        const int x = (static_cast<int>(player.x) + 4) >> 3;
        const int y = static_cast<int>(player.y) >> 3;
        const std::array<std::array<int, 2>, 4> cells{{{x,y}, {x+1,y}, {x+1,y+1}, {x,y+1}}};
        // 6F98..56C2 passes cutoff 2, then clears the shared query outputs.
        sound_.writeSharedCursor(static_cast<uint16_t>(y * level_.width + x));
        actorSlots_.setSharedResult(2);
        monsterTileDamageDelta_ = 0;
        actorSlots_.setSharedResult(0);
        int damage = 0, flameCell = 0;
        for (size_t i = 0; i < cells.size(); ++i) {
            const auto& cell = cells[i];
            const int glyph = tileAt(cell[0], cell[1]);
            if (glyph == 0x75) {
                damage += 2;
                flameCell = cell[1] * level_.width + cell[0];
                actorSlots_.setSharedResult(static_cast<uint16_t>(flameCell));
            } else if (i < 2 && glyph >= 1 && glyph <= 0x4c) {
                damage += 2;
            }
            monsterTileDamageDelta_ = static_cast<int8_t>(-damage);
        }
        if (flameCell != 0) {
            const auto ray = std::find_if(flameRecords_.rbegin(), flameRecords_.rend(),
                [flameCell](const FlameRecord& item) { return item.cell == flameCell; });
            if (ray != flameRecords_.rend()) {
                // 3A56 searches backward and replaces the cell cursor with a one-based slot.
                sound_.writeSharedCursor(static_cast<uint16_t>(std::distance(ray, flameRecords_.rend())));
                player.vx8 = static_cast<int16_t>(ray->vx * 8);
                player.vy8 = static_cast<int16_t>(ray->vy * 8);
                if (ray->mass > 1) damage += ray->mass / 10;
                monsterTileDamageDelta_ = static_cast<int8_t>(-damage);
            }
        }
        energy = static_cast<uint8_t>(energy - damage);
        if (const auto index = ownedPlayerIndex(player))
            writePlayerHealth(static_cast<uint8_t>(*index + 1), energy);
    }

void GameplayOperations::updateDyingPlayerMotion(Player& player) {
        // Behavior 2 (1000:7018) preserves velocity and fractional carries.
        int x = static_cast<int>(player.x), y = static_cast<int>(player.y);
        const auto edges = scanActorEdges(x, y);
        if (!edges.bottom || player.vy8 < 0) {
            // 1000:7028 wraps the word addition before the signed limit.
            const int16_t accelerated = static_cast<int16_t>(player.vy8 + 0x40);
            player.vy8 = std::min<int16_t>(0x07ff, accelerated);
        } else if (player.vy8 > 0) {
            player.vy8 = 0;
            y &= ~7;
        }
        if (edges.bottom) player.vx8 = actorFloorFriction(player.vx8);
        integratePlayerMotion(player, x, y, edges);
    }

void GameplayOperations::integratePlayerMotion(Player& player, int x, int y,
                                      const ActiveMonster::EdgeFlags& edges) {
        if (edges.top && player.vy8 < 0) player.vy8 = 1;
        if (edges.left && edges.right) {
            player.vx8 = 0;
        } else if ((edges.left && player.vx8 < 0) || (edges.right && player.vx8 > 0)) {
            player.vx8 = static_cast<int16_t>(-player.vx8 / 2);
            x += player.vx8 < 0 ? -1 : 1;
        }
        integrateAxis8_8(y, player.fracY, player.vy8);
        integrateAxis8_8(x, player.fracX, player.vx8);
        player.x = static_cast<float>(x);
        player.y = static_cast<float>(y);
        writePlayerPosition(player);
        if (const auto index = ownedPlayerIndex(player)) actorSlots_.writePlayerMotion(*index, player);
        player.grounded = edges.bottom && player.vy8 == 0;
        syncPlayerVelocityMirror(player);
    }

void GameplayOperations::syncPlayerVelocityMirror(Player& player) {
        player.vx = player.vx8 / 256.0f;
        player.vy = player.vy8 / 256.0f;
    }

int16_t GameplayOperations::actorFloorFriction(int16_t velocity) {
        // Original shared helper 1000:5B86, called by players and bombs.
        // Its word-sized absolute value leaves -32768 negative.
        const int16_t magnitude = static_cast<int16_t>(std::abs(velocity));
        return static_cast<int16_t>(magnitude < 43 ? 0 :
                                    velocity + (velocity < 0 ? 42 : -42));
    }

int16_t GameplayOperations::playerWalkVelocity(int16_t velocity, bool left, bool right, bool bottom) {
        // 1000:6AC6/6B1C test before adding. Reaccelerating after friction
        // can cross +/-1024; clamping the result would change the original.
        if (left && velocity > -kPlayerWalkVelocity8) velocity -= kPlayerWalkAcceleration8;
        if (right && velocity < kPlayerWalkVelocity8) velocity += kPlayerWalkAcceleration8;
        if (bottom && !left && !right) velocity = actorFloorFriction(velocity);
        return velocity;
    }

std::vector<SharedActorEntry> GameplayOperations::sharedActorEntries() const {
        std::vector<SharedActorEntry> result;
        for (size_t i = 0; i < transientActors_.size(); ++i) result.push_back({transientActors_[i].actorOrder, SharedActorKind::Effect, i});
        for (size_t i = 0; i < launchPadMarkers_.size(); ++i) result.push_back({launchPadMarkers_[i].actorOrder, SharedActorKind::Marker, i});
        for (size_t i = 0; i < bombs_.size(); ++i) result.push_back({bombs_[i].actorOrder, SharedActorKind::Bomb, i});
        for (size_t i = 0; i < monsters_.size(); ++i) if (monsters_[i].alive) result.push_back({monsters_[i].actorOrder, SharedActorKind::Monster, i});
        for (size_t i = 0; i < bonusDrops_.size(); ++i) if (!bonusDrops_[i].collected) result.push_back({bonusDrops_[i].actorOrder, SharedActorKind::Reward, i});
        std::stable_sort(result.begin(), result.end(), [](const SharedActorEntry& a, const SharedActorEntry& b) { return a.order < b.order; });
        return result;
    }

uint64_t GameplayOperations::sharedActorVisualKey(const SharedActorEntry& entry) const {
        if (entry.kind == SharedActorKind::Monster && monsters_[entry.index].bossVisualOrder)
            return monsters_[entry.index].bossVisualOrder;
        if (entry.kind == SharedActorKind::Effect && transientActors_[entry.index].bossVisualOrder)
            return transientActors_[entry.index].bossVisualOrder;
        return entry.order;
    }

lezac::gameplay::ActorSlots::Descriptor GameplayOperations::actorSpriteDescriptor(uint16_t sprite) const {
        const auto& bank = levelIndex_ == 6 ? altSprites_ : sprites_;
        if (sprite == 0 || sprite > bank.sprites.size()) {
            if (legacyActorSeedsEnabled_) return {};
            throw std::out_of_range("actor constructor sprite descriptor");
        }
        uint16_t offset = 0;
        for (size_t index = 0; index + 1 < sprite; ++index) {
            const auto& previous = bank.sprites[index];
            offset = static_cast<uint16_t>(offset + previous.width * previous.height);
        }
        const auto& image = bank.sprites[sprite - 1];
        return {static_cast<uint8_t>(image.width), static_cast<uint8_t>(image.height),
                static_cast<uint8_t>(offset), static_cast<uint8_t>(offset >> 8)};
    }

void GameplayOperations::adoptUnorderedActors() {
        // This adapter exists only for older explicitly seeded diagnostics.
        // Interactive play never reconciles physical slots from typed vectors.
        if (!legacyActorSeedsEnabled_) return;
        auto entries = sharedActorEntries();
        for (const auto& entry : entries) nextActorOrder_ = std::max(nextActorOrder_, entry.order + 1);
        for (const auto& entry : entries) {
            if (entry.order) continue;
            const uint64_t order = nextActorOrder_++;
            switch (entry.kind) {
                case SharedActorKind::Effect: transientActors_[entry.index].actorOrder = order; break;
                case SharedActorKind::Marker: launchPadMarkers_[entry.index].actorOrder = order; break;
                case SharedActorKind::Bomb: bombs_[entry.index].actorOrder = order; break;
                case SharedActorKind::Monster: monsters_[entry.index].actorOrder = order; break;
                case SharedActorKind::Reward: bonusDrops_[entry.index].actorOrder = order; break;
            }
        }
        entries = sharedActorEntries();
        for (size_t slot = actorSlots_.count(); slot > 0; --slot) {
            const uint64_t order = actorSlots_.order(slot);
            const bool pending = std::find(pendingActorConversions_.begin(), pendingActorConversions_.end(), order) != pendingActorConversions_.end();
            const bool present = std::any_of(entries.begin(), entries.end(), [order](const SharedActorEntry& entry) { return entry.order == order; });
            if (!present && !pending) { actorSlots_.retire(order); ++legacyActorRetirements_; }
        }
        uint64_t previous = 0;
        for (const auto& entry : entries) {
            if (entry.order == previous) throw std::runtime_error("duplicate diagnostic actor identity");
            previous = entry.order;
            lezac::gameplay::ActorSlots::Construction input{};
            ActorAnimation backup{0, 0, 0, 0, 0, 0, 0};
            bool typedBackup = false;
            switch (entry.kind) {
                case SharedActorKind::Effect: {
                    const auto& actor = transientActors_[entry.index];
                    input = {actor.kind, actor.timer, 5, static_cast<uint16_t>(actor.spriteIndex + 1), actor.vx8, actor.vy8,
                        static_cast<int16_t>(actor.x), static_cast<int16_t>(actor.y)};
                    backup = actor.animationBackup; typedBackup = true; break;
                }
                case SharedActorKind::Marker: {
                    const auto& marker = launchPadMarkers_[entry.index];
                    input = {marker.kind, marker.timer, marker.mode, marker.frame, marker.velocityX8, marker.velocityY8,
                        static_cast<int16_t>(marker.x), static_cast<int16_t>(marker.y)}; break;
                }
                case SharedActorKind::Bomb: {
                    const auto& bomb = bombs_[entry.index]; const auto profile = bombProfile(bomb.type);
                    input = {profile.actorKind, static_cast<uint8_t>((bomb.timer + 1) / 2), 2,
                        static_cast<uint16_t>(profile.spriteBase + 1), bomb.vx8, bomb.vy8,
                        static_cast<int16_t>(bomb.pixelX), static_cast<int16_t>(bomb.pixelY)}; break;
                }
                case SharedActorKind::Monster: {
                    const auto& actor = monsters_[entry.index];
                    const auto timer = actor.kind == 0x0c && actor.behavior == 2 && !actor.bossDebris
                        ? lezac::gameplay::corpseTimerFromRemainingUpdates(actor.stateTimer, logicTick_)
                        : static_cast<uint8_t>(actor.stateTimer);
                    input = {actor.kind, timer, actor.behavior,
                        static_cast<uint16_t>(actor.animFrame + 1), actor.vx8, actor.vy8,
                        static_cast<int16_t>(actor.x), static_cast<int16_t>(actor.y + actor.hotspotY)};
                    backup = actor.animationBackup; typedBackup = true; break;
                }
                case SharedActorKind::Reward: {
                    const auto& drop = bonusDrops_[entry.index];
                    input = {static_cast<uint8_t>(static_cast<uint8_t>(drop.type) + 0x13), drop.timer, 2,
                        static_cast<uint16_t>(bonusSpriteIndex(drop.type) + 1), drop.vx8, drop.vy8,
                        static_cast<int16_t>(drop.x), static_cast<int16_t>(drop.y)}; break;
                }
            }
            if (!actorSlots_.find(entry.order)) {
                if (!actorSlots_.append(entry.order, input, actorSpriteDescriptor(input.sprite)))
                    throw std::runtime_error("diagnostic actor seed exceeds physical capacity");
                if (entry.kind == SharedActorKind::Monster) {
                    const auto& monster = monsters_[entry.index];
                    if (monster.kind >= 1 && monster.kind <= 8)
                        actorSlots_.initializeSpawnedMonster(entry.order, monster,
                            monster.hasSpawner ? static_cast<uint8_t>(monster.spawnerIndex + 1) : 0);
                }
                ++legacyActorAdoptions_;
            }
            if (typedBackup && actorSlots_.animationBackup(entry.order).packed() != backup.packed()) {
                actorSlots_.setAnimationBackup(entry.order, backup);
                ++legacyActorAdoptions_;
            }
        }
    }

uint64_t GameplayOperations::claimActorOrder() {
        if (!legacyActorSeedsEnabled_) throw std::runtime_error("unallocated production actor identity");
        adoptUnorderedActors();
        return nextActorOrder_++;
    }

uint64_t GameplayOperations::allocateActor(const lezac::gameplay::ActorSlots::Construction& input) {
        adoptUnorderedActors();
        const uint64_t order = nextActorOrder_;
        const auto descriptor = actorSlots_.count() == 30 ? lezac::gameplay::ActorSlots::Descriptor{} : actorSpriteDescriptor(input.sprite);
        if (!actorSlots_.append(order, input, descriptor)) return 0;
        ++nextActorOrder_;
        return order;
    }

void GameplayOperations::retireActor(uint64_t order) {
        if (!actorSlots_.retire(order)) throw std::runtime_error("retiring unbound production actor");
    }

ActorAnimation GameplayOperations::conversionBackup(uint64_t order, ActorAnimation legacy ) const {
        if (actorSlots_.find(order)) return actorSlots_.animationBackup(order);
        if (legacyActorSeedsEnabled_) return legacy;
        throw std::runtime_error("converting unbound production actor");
    }

void GameplayOperations::updateOrderedActors(float dt) {
        adoptUnorderedActors();
        if (orderedActorPass_) throw std::runtime_error("recursive shared actor pass");
        orderedActorPass_ = true;
        struct PassGuard { bool& active; ~PassGuard() { active = false; } } guard{orderedActorPass_};
        uint64_t previous = 0;
        while (true) {
            // Original 3358 shifts records stably; 65C6 rewinds the cursor.
            // Retaining birth order implements both without stale vector indices.
            // In-place conversions keep their order; tail appends run this pass.
            const auto entries = sharedActorEntries();
            const auto found = std::find_if(entries.begin(), entries.end(), [&](const SharedActorEntry& entry) { return entry.order > previous; });
            if (found == entries.end()) break;
            const auto entry = *found;
            previous = entry.order;
            switch (entry.kind) {
                case SharedActorKind::Effect: {
                    updateTransientActor(transientActors_.at(entry.index));
                    if (!transientActors_[entry.index].timer) {
                        retireActor(entry.order);
                        transientActors_.erase(transientActors_.begin() + static_cast<std::ptrdiff_t>(entry.index));
                    }
                    break;
                }
                case SharedActorKind::Marker: updateLaunchPadMarkers(entry.order); break;
                case SharedActorKind::Bomb: updateBombs(entry.order); break;
                case SharedActorKind::Monster: updateMonsters(dt, entry.order); break;
                case SharedActorKind::Reward: updateBonusDrops(std::numeric_limits<size_t>::max(), entry.order); break;
            }
        }
    }

size_t GameplayOperations::sharedActorCount() {
        adoptUnorderedActors();
        return actorSlots_.count();
    }

void GameplayOperations::updateCameraShake() {
        // 1000:806A..8091 advances once per game frame, never per render.
        if (cameraShakeTicks_ == 0) return;
        cameraShakeOffset_ = randomRangeValue(0, static_cast<uint16_t>(cameraShakeTicks_ * 2));
        if (--cameraShakeTicks_ == 0) cameraShakeOffset_ = 0;
    }

size_t GameplayOperations::pickupActorCount() const {
        return static_cast<size_t>(std::count_if(transientActors_.begin(), transientActors_.end(),
            [](const TransientActor& actor) { return actor.kind == 0x0a; }));
    }

TransientActor* GameplayOperations::spawnTransientActor(int x, int y, int16_t vy8, uint8_t sprite,
                             uint8_t kind, uint8_t timer,
                             ActorAnimation animation ) {
        // 1000:2F9F has one 30-slot pool for non-player actors.
        TransientActor actor;
        actor.x = x;
        actor.y = y;
        actor.vy8 = clampConstructedActorVelocity8(vy8);
        actor.kind = kind;
        actor.timer = timer;
        actor.spriteIndex = static_cast<uint8_t>(sprite - 1);
        actor.animation = animation;
        actor.actorOrder = allocateActor({kind, timer, 5, sprite, 0, vy8,
            static_cast<int16_t>(x), static_cast<int16_t>(y)});
        if (!actor.actorOrder) return nullptr;
        actor.hotspotY = actorSlots_.actor(actor.actorOrder)[20];
        actor.animationBackup = actorSlots_.animationBackup(actor.actorOrder);
        actorSlots_.writeTransient(actor.actorOrder, actor, false, {});
        transientActors_.push_back(actor);
        return &transientActors_.back();
    }

void GameplayOperations::updateTransientActor(TransientActor& actor) {
        const bool advanced = lezac::gameplay::advanceTransientActor(actor, logicTick_);
        if (!actorSlots_.find(actor.actorOrder)) {
            if (legacyActorSeedsEnabled_) return;
            throw std::runtime_error("updating unbound production transient");
        }
        actorSlots_.writeTransient(actor.actorOrder, actor, advanced,
            advanced ? actorSpriteDescriptor(static_cast<uint16_t>(actor.spriteIndex) + 1) : lezac::gameplay::ActorSlots::Descriptor{});
    }

void GameplayOperations::updateTransientActors() {
        adoptUnorderedActors();
        for (auto& actor : transientActors_) updateTransientActor(actor);
        for (const auto& actor : transientActors_) if (actor.timer == 0) retireActor(actor.actorOrder);
        transientActors_.erase(std::remove_if(transientActors_.begin(), transientActors_.end(),
            [](const TransientActor& actor) { return actor.timer == 0; }), transientActors_.end());
    }

void GameplayOperations::collectObjectiveTiles(const Player& player, uint8_t playerIndex) {
        collectObjectiveTiles(player, playerIndex, static_cast<int>(player.x), static_cast<int>(player.y));
    }

void GameplayOperations::initializePickupTailAnimation() {
        // 1000:6DDD..6DF3 initializes DS:208D even if 2F9F refused allocation.
        const auto entries = sharedActorEntries();
        if (entries.empty()) return;
        const auto& entry = entries.back();
        const ActorAnimation stopped{0, 0, 0, 0, 0, 0, 1};
        switch (entry.kind) {
            case SharedActorKind::Effect: transientActors_[entry.index].animation = stopped; break;
            case SharedActorKind::Marker: launchPadMarkers_[entry.index].animation = stopped; break;
            case SharedActorKind::Reward: bonusDrops_[entry.index].animation = stopped; break;
            case SharedActorKind::Monster: {
                auto& monster = monsters_[entry.index];
                // Monster cursors/ranges are zero-based; visible animFrame stays latched.
                monster.animCursor = monster.animStart = monster.animEnd = 0xff;
                monster.animTick = monster.animDelay = monster.animMode = 0;
                monster.animStep = 1;
                break;
            }
            case SharedActorKind::Bomb: break; // Bombs have an implicit stopped cursor.
        }
    }

void GameplayOperations::collectObjectiveTiles(const Player& player, uint8_t playerIndex, int originX, int originY) {
        // 1000:6CB8..6DAA visits the cached actor interior clockwise. Scores
        // are DS:0002..0019, file 0xB192; consume/seeder are 5AFD / 370E.
        constexpr std::array<int, 12> scores{
            50, 100, 200, 250, 500, 800, 1000, 1500, 2000, 3000, 5000, 1000};
        constexpr std::array<uint8_t, 12> pickupSprites{80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 86};
        const int x0 = (static_cast<int>(player.x) + 4) >> 3;
        const int y0 = static_cast<int>(player.y) >> 3;
        int score = 0;
        bool high = false;
        for (const auto& cell : std::array<std::array<int, 2>, 4>{{
                 {{x0, y0}}, {{x0 + 1, y0}}, {{x0 + 1, y0 + 1}}, {{x0, y0 + 1}}}}) {
            const int x = cell[0], y = cell[1];
            const uint8_t tile = static_cast<uint8_t>(tileAt(x, y));
            if (!isBombObjectTile(tile)) continue;
            if (tile == 0x72) applyTileTrigger(wordAt(x, y));
            if (!consumeBombObjectTile(x, y)) continue;
            queueTileDamage(x, y - 1, 0, 0, true);
            if (tile == level_.objectiveTile) ++collected_;
            score += scores[tile - 0x67];
            high = high || isHighBombObjectSoundTile(tile);
            if (pickupActorCount() < 14) {
                // 1000:6D88..6DFA draws even if the shared allocator is full.
                const auto vy8 = static_cast<int16_t>(-40 - randomRangeValue(0, 200));
                spawnTransientActor(originX + (x == x0 ? -2 : 10),
                    originY + (y == y0 ? -2 : 10), vy8,
                    pickupSprites[tile - 0x67], 0x0a, 12);
                initializePickupTailAnimation();
            }
        }
        if (score != 0) {
            addScore(playerIndex, score);
            // The low pickup pair is also the already captured objective
            // hook (cursor 0, priority 3). Retain its diagnostic funnel;
            // mixed/high pickups select the original high-object branch.
            if (high) requestBombObjectScoreSound(true);
            else playCompatibilitySound(kObjectivePickupCompatibilityHookSlot);
        }
    }

bool GameplayOperations::activatePortal(int& x, int& y, bool down) {
        const int column = (x + 4) >> 3;
        const int row = (y >> 3) + 2;
        if (!down || tileAt(column, row) != 0x45) return false;
        // 1000:5999 clears both physical Down banks before scanning destinations.
        portalDownConsumed_.fill(true);
        const uint16_t key = static_cast<uint16_t>(wordAt(column, row) & 0x7fffu);
        for (const LevelPortal& portal : level_.portals) {
            if (portal.key != key) continue;
            // The helper changes the motion locals, preserving velocity and carry.
            x = portal.x;
            y = portal.y;
            requestPortalTeleportSound();
            spawnPortalMarker(x, y);
            return true;
        }
        return false;
    }

void GameplayOperations::updatePortalsAndTriggers(Player& player, int& portalCooldown,
                                  int& triggerCooldown, bool down) {
        int tx = static_cast<int>(player.x + 6.0f) / 8;
        int ty = static_cast<int>(player.y + 12.0f) / 8;
        int tile = tileAt(tx, ty);
        int x = static_cast<int>(player.x), y = static_cast<int>(player.y);
        if (activatePortal(x, y, down)) {
            player.x = static_cast<float>(x);
            player.y = static_cast<float>(y);
            writePlayerPosition(player);
            portalCooldown = 0;
        } else if (tile == 0x72 && triggerCooldown == 0) {
            if (applyTileTrigger(wordAt(tx, ty))) {
                triggerCooldown = 30;
                requestTileTriggerSound();
            }
        }
    }

bool GameplayOperations::applyTileTrigger(uint16_t key) {
        bool changed = false;
        for (const TileTriggerRule& rule : level_.tileTriggers) {
            if (rule.triggerKey != key) continue;
            size_t count = std::min(level_.tiles.size(), level_.wordLayer.size());
            for (size_t i = 0; i < count; ++i) {
                uint16_t word = static_cast<uint16_t>(level_.wordLayer[i] & 0x7fffu);
                if (word < rule.wordRangeFirst || word > rule.wordRangeLast) continue;
                for (size_t slot = 0; slot < rule.from.size(); ++slot) {
                    uint8_t from = rule.from[slot];
                    if (from != 0 && level_.tiles[i] == from) {
                        uint8_t to = rule.to[slot];
                        accountTileRewrite(level_.tiles[i], to);
                        level_.tiles[i] = to;
                        changed = true;
                    }
                }
            }
        }
        return changed;
    }

void GameplayOperations::accountTileRewrite(uint8_t from, uint8_t to) {
        (void)from;
        (void)to;
    }

std::array<int, 2> GameplayOperations::monsterFrameRange(uint8_t kind) const {
        return lezac::gameplay::monsterAnimationSetRange(
            lezac::gameplay::monsterAnimationSelectors(kind)[0]);
    }

std::array<int, 2> GameplayOperations::monsterDirectionalFrameRange(uint8_t kind, int16_t vx8) const {
        // vx > 0 selects the right-facing set (1000:72DA `cmp vx,0; jle`);
        // vx < 0 the left set (1000:7286 `jge`). vx == 0 selects NEITHER in
        // the reselection; the spawn default is the actor+0x03 (left) set --
        // both captured spawns show frame 44, the left pair's high member --
        // so the vx == 0 mapping here is the left set.
        return lezac::gameplay::monsterAnimationSetRange(
            lezac::gameplay::monsterAnimationSelectors(kind)[vx8 > 0 ? 1 : 0]);
    }

uint8_t GameplayOperations::monsterHotspotY(uint8_t kind) { return kind == 1 ? 6 : 0; }

bool GameplayOperations::actorTouchesPlayer(const Player& player, int ax, int ayCollide) const {
        const auto touchesAxis = [](int playerCoordinate, int actorCoordinate) {
            const uint16_t delta = static_cast<uint16_t>(
                static_cast<int64_t>(playerCoordinate) - actorCoordinate);
            const uint16_t magnitude = delta & 0x8000
                ? static_cast<uint16_t>(0u - delta) : delta;
            return magnitude == 0x8000 || magnitude < 10;
        };
        return touchesAxis(static_cast<int>(player.x), ax) &&
               touchesAxis(static_cast<int>(player.y), ayCollide);
    }

uint16_t GameplayOperations::randomRangeValue(uint16_t base, uint16_t range) {
        lezac::core::TurboRandom random(randomSeed_);
        const uint16_t value = random.range(base, range);
        randomSeed_ = random.seed();
        return value;
    }

int GameplayOperations::randomInclusive(int low, int high) {
        return static_cast<int>(randomRangeValue(static_cast<uint16_t>(low),
                                                 static_cast<uint16_t>(high - low + 1)));
    }

int16_t GameplayOperations::groundWalkerSpeed8(const ActiveMonster& monster) const {
        return clampI16(monster.ai0);
    }

void GameplayOperations::refreshMonsterAnimationProfile(ActiveMonster& monster) {
        auto frames = lezac::gameplay::monsterFacingFrameRange(monster);
        if (monster.animStart != frames[0] || monster.animEnd != frames[1]) {
            monster.animStart = static_cast<uint8_t>(frames[0]);
            monster.animEnd = static_cast<uint8_t>(frames[1]);
            monster.animFrame = monster.animStart;
            monster.animCursor = monster.animStart;
        }
    }

void GameplayOperations::reselectWalkerFacing(ActiveMonster& monster) {
        if (monster.vx8 == 0) return;
        auto frames = lezac::gameplay::monsterFacingFrameRange(monster);
        monster.animStart = static_cast<uint8_t>(frames[0]);
        monster.animEnd = static_cast<uint8_t>(frames[1]);
        monster.animCursor = monster.animStart;
    }

void GameplayOperations::initializeMonsterMotion(ActiveMonster& monster) {
        if (monster.behavior == 4) {
            // Original 1000:70D7 gates behavior-4 steering on the shared
            // DS:78C2 frame counter. A newly spawned actor therefore stays
            // still until that global clock is divisible by actor +0x0E;
            // there is no private per-actor countdown and no spawn-time draw.
            monster.vx8 = 0;
            monster.vy8 = 0;
            monster.motionTimer = 0;
            refreshMonsterAnimationProfile(monster);
            return;
        }
        monster.vx8 = 0;
        monster.vy8 = 0;
        refreshMonsterAnimationProfile(monster);
    }

std::array<int16_t,2> GameplayOperations::monsterTargetDelta(const ActiveMonster& monster) const {
        // 1000:63F6..654E admits only original state 1, including pending
        // death. Shipped thresholds are below the inactive X sentinel 6000;
        // captured both-inactive states therefore take the random branch.
        const Player* target = nullptr;
        double distance = 0;
        for (uint8_t marker : {uint8_t{1}, uint8_t{2}}) {
            if (originalPlayerState(marker) != 1) continue;
            const Player& candidate = marker == 1 ? player_ : player2_;
            const double candidateDistance =
                std::fabs(static_cast<int>(candidate.x) - monster.x) +
                std::fabs(static_cast<int>(candidate.y) - monster.y);
            if (!target || candidateDistance < distance) {
                target = &candidate;
                distance = candidateDistance;
            }
        }
        const int dx = target ? static_cast<int>(target->x) - monster.x : 6000;
        const int dy = target ? static_cast<int>(target->y) - monster.y : 0;
        // Target selection retains the existing wide-distance owner; the
        // recovered prefix consumes the selected signed component words.
        return {std::bit_cast<int16_t>(static_cast<uint16_t>(dx)),
                std::bit_cast<int16_t>(static_cast<uint16_t>(dy))};
    }

const Player& GameplayOperations::nearestPlayer(float x, float y) const {
        if (playerCount_ <= 1 || player2Dead_) return player_;
        if (playerDead_) return player2_;
        float distance1 =
            std::fabs(player_.x - x) + std::fabs(player_.y - y);
        float distance2 =
            std::fabs(player2_.x - x) + std::fabs(player2_.y - y);
        return distance2 < distance1 ? player2_ : player_;
    }

lezac::core::ActorMotionPrefixResult GameplayOperations::runActorMotionPrefix(lezac::core::ActorMotionPrefixInput input) {
        input.shared={static_cast<uint16_t>(damageLaneData_[0xc1e8]|(uint16_t{damageLaneData_[0xc1e9]}<<8)),
            actorSlots_.state().success,sound_.requestCursor()};
        input.tick=static_cast<uint16_t>(logicTick_);
        input.randomSeed=randomSeed_;
        const auto result=lezac::core::actorMotionPrefix(input,
            std::span<const uint8_t,512>{damageLaneData_.data()+0x58,512});
        randomSeed_=result.randomSeed;
        damageLaneData_[0xc1e8]=static_cast<uint8_t>(result.shared[0]);
        damageLaneData_[0xc1e9]=static_cast<uint8_t>(result.shared[0]>>8);
        actorSlots_.setSharedResult(result.shared[1]);
        sound_.writeSharedCursor(result.shared[2]);
        return result;
    }

void GameplayOperations::requireMotionTerrain(const lezac::core::ActorMotionPrefixResult& result) {
        if (result.outcome!=lezac::core::ActorMotionPrefixOutcome::Terrain)
            throw std::domain_error("Original actor motion reached an unrecovered runtime fault");
    }

void GameplayOperations::updateMonsterMotion(ActiveMonster& monster, float argument1) {
        if (monster.behavior == 6) {
            updateBossHead(monster);
            return;
        }
        if (monster.behavior == 5) {
            applyBossSegmentLinks(monster);
            return;
        }
        lezac::core::ActorMotionPrefixInput input;
        if (actorSlots_.find(monster.actorOrder)) input.actor=actorSlots_.actor(monster.actorOrder);
        input.actor[0]=monster.kind;input.actor[21]=monster.behavior;
        input.actor[3]=monster.animationSetLeft;input.actor[4]=monster.animationSetRight;
        const std::array<uint16_t,3> parameters{monster.ai0,monster.ai1,monster.ai2};
        for (size_t i=0;i<parameters.size();++i) {
            input.actor[14+2*i]=static_cast<uint8_t>(parameters[i]);
            input.actor[15+2*i]=static_cast<uint8_t>(parameters[i]>>8);
        }
        const auto animation=lezac::gameplay::monsterAnimation(monster).packed();
        std::copy(animation.begin(),animation.end(),input.actor.begin()+22);
        input.originalX=input.x=std::bit_cast<int16_t>(static_cast<uint16_t>(monster.x));
        input.y=std::bit_cast<int16_t>(static_cast<uint16_t>(monster.y));
        input.vx8=monster.vx8;input.vy8=monster.vy8;
        const auto delta=monsterTargetDelta(monster);
        input.dx=delta[0];input.dy=delta[1];
        input.edges={static_cast<uint8_t>(monster.edges.top),static_cast<uint8_t>(monster.edges.bottom),
            static_cast<uint8_t>(monster.edges.left),static_cast<uint8_t>(monster.edges.right)};
        const int column=(monster.x+4)>>3,row=(monster.y>>3)+2;
        for (int i=0;i<4;++i) input.tiles[static_cast<size_t>(i)]=static_cast<uint8_t>(tileAt(column+i-1,row));
        const auto result=runActorMotionPrefix(input);
        monster.x=result.x;monster.y=result.y;monster.vx8=result.vx8;monster.vy8=result.vy8;
        const auto& raw=result.actor;
        lezac::gameplay::setMonsterAnimation(monster,{raw[22],raw[23],raw[24],raw[25],raw[26],raw[27],
            static_cast<int8_t>(raw[28])});
        if (actorSlots_.find(monster.actorOrder))
            actorSlots_.setActiveAnimation(monster.actorOrder,lezac::gameplay::monsterAnimation(monster));
        monster.facingDirty=false;
        const uint16_t tick=static_cast<uint16_t>(logicTick_);
        if (monster.behavior==4)
            monster.motionTimer=monster.ai0==0 ? 0 : monster.ai0-(tick%monster.ai0);
        requireMotionTerrain(result);
    }

void GameplayOperations::spawnLevel7Boss() {
        spawnLevel7BossFromBank(gran_);
    }

void GameplayOperations::spawnLevel7BossFromBank(const GranBank& bank) {
        std::vector<uint8_t> granBytes;
        for (const GranRecord& record : bank.records) {
            granBytes.insert(granBytes.end(), record.bytes.begin(), record.bytes.end());
        }
        if (granBytes.size() != 399 || granBytes[0] != 7) return;
        size_t pos = 1;
        const size_t recordCount = granBytes[0];
        pos += recordCount * 0x26;
        const size_t spritesBase = pos;
        pos += recordCount;
        const size_t pairsBase = pos;
        pos += recordCount * 4;
        const size_t extraCount = granBytes[pos++];
        if (pos + extraCount * 16 != granBytes.size()) return;

        const lezac::gameplay::GranGroup group(granBytes);
        const uint64_t firstBossVisualOrder = nextActorOrder_;
        const auto bossGroup = static_cast<uint16_t>(sharedActorCount() + 1);
        const auto visualBase = actorSlots_.state().visualCount;
        const auto linkBase = actorSlots_.state().links[0][15];
        actorSlots_.appendGranGroup(firstBossVisualOrder,group,100,100,
            [this](uint8_t sprite) { return actorSpriteDescriptor(sprite); },
            [](uint8_t selector) {
                if (selector >= kBossAnimSets.size()) throw std::out_of_range("Unknown GRAN animation set");
                return std::array<uint8_t,2>{static_cast<uint8_t>(kBossAnimSets[selector][0]),
                    static_cast<uint8_t>(kBossAnimSets[selector][1])};
            });
        nextActorOrder_ += recordCount;

        for (size_t i = 0; i < bossSinTable_.size(); ++i) {
            // The original fills a 128-entry Real48 table with Sin(i*6.28/128).
            bossSinTable_[i] = std::sin(static_cast<float>(i) * 6.28f / 128.0f);
        }

        bossLinks_.clear();
        for (size_t i = 0; i < extraCount; ++i) {
            const uint8_t* extra = actorSlots_.state().links[linkBase+i+1].data();
            BossMotionLink link;
            link.targetVisual = extra[0];
            link.selfVisual = extra[1];
            link.gain = extra[2];
            link.mode = extra[3];
            link.radiusX = extra[4];
            link.radiusY = extra[5];
            link.phase = extra[6];
            link.offX = static_cast<int16_t>(extra[7] | (extra[8] << 8));
            link.offY = static_cast<int16_t>(extra[9] | (extra[10] << 8));
            // The loader copies the complete link before the first actor pass.
            link.outX = static_cast<int16_t>(extra[11] | (extra[12] << 8));
            link.outY = static_cast<int16_t>(extra[13] | (extra[14] << 8));
            link.biasY = static_cast<int8_t>(extra[15]);
            bossLinks_.push_back(link);
        }

        for (size_t i = 0; i < recordCount; ++i) {
            const auto order = firstBossVisualOrder+i;
            const uint8_t* record = actorSlots_.actor(order).data();
            ActiveMonster actor;
            actor.kind = record[0x00];
            actor.behavior = record[0x15];
            actor.bossVisual = record[0x01];
            // The GRAN reader rewrites the head +0x12 and segment +0x25
            // owner fields to the group's first one-based actor slot.
            actor.bossGroup = bossGroup;
            const size_t entryOrder = static_cast<size_t>(actor.bossVisual) - visualBase;
            if (entryOrder >= recordCount) continue;
            const int dx = static_cast<int16_t>(granBytes[pairsBase + entryOrder * 4] |
                                                (granBytes[pairsBase + entryOrder * 4 + 1] << 8));
            const int dy = static_cast<int16_t>(granBytes[pairsBase + entryOrder * 4 + 2] |
                                                (granBytes[pairsBase + entryOrder * 4 + 3] << 8));
            actor.x = 100 + dx;
            actor.y = 100 + dy;
            const uint8_t entrySprite = granBytes[spritesBase + entryOrder];
            actor.animCursor = static_cast<uint8_t>(record[0x16] - 1);
            actor.animStart = static_cast<uint8_t>(record[0x17] - 1);
            actor.animEnd = static_cast<uint8_t>(record[0x18] - 1);
            actor.animTick = record[0x19];
            actor.animMode = record[0x1b];
            actor.animStep = static_cast<int8_t>(record[0x1c]);
            actor.stateTimer = record[2];
            actor.animationSetLeft = record[3]; actor.animationSetRight = record[4];
            // GRAN.MST and the animation table carry one-based descriptors.
            actor.animFrame = entrySprite - 1;
            // Raw delay byte: the shared advance (1000:608F) fires when the
            // counter exceeds it, so 0 keeps the old every-tick cadence and
            // any nonzero byte means period byte+1.
            actor.animDelay = record[0x1a];
            actor.animationBackup = {record[0x1d], record[0x1e], record[0x1f], record[0x20],
                                     record[0x21], record[0x22], static_cast<int8_t>(record[0x23])};
            if (actor.kind == 0x1e) {
                actor.bossHpByte = record[0x24];
                actor.bossLives = record[0x02];
                actor.bossBoxW = record[0x0e];
                actor.bossBoxH = record[0x0f];
                actor.hp = actor.bossHpByte;
            } else {
                // Segments carry serial link bytes at +0x0e/+0x10; at level
                // entry the DS:0x79F9 rebase base is zero, so the shipped
                // serials index bossLinks_ 1-based directly.
                actor.linkA = record[0x0e];
                actor.linkB = record[0x0f];
                actor.linkC = record[0x10];
                actor.hp = 255;
            }
            actor.actorOrder = order;
            actor.bossVisualOrder = firstBossVisualOrder + entryOrder;
            monsters_.push_back(actor);
        }
        bossPresent_ = true;
    }

ActiveMonster* GameplayOperations::findBossActorByVisual(uint8_t visual) {
        for (ActiveMonster& monster : monsters_) {
            if (monster.alive && !monster.bossDebris &&
                (monster.behavior == 5 || monster.behavior == 6) &&
                monster.bossVisual == visual) {
                return &monster;
            }
        }
        return nullptr;
    }

void GameplayOperations::updateBossLinks() {
        if (bossLinks_.empty()) return;
        for (size_t index=0;index<bossLinks_.size();++index) {
            BossMotionLink& link=bossLinks_[index];
            ActiveMonster* target = findBossActorByVisual(link.targetVisual);
            if (link.mode != 0xff) {
                ActiveMonster* self = findBossActorByVisual(link.selfVisual);
                if (!target || !self) continue;
                link.outX = static_cast<int16_t>(
                    (target->x - self->x + link.offX) * link.gain);
                // 1000:43E8 reads DS:C220 visual Y, including the head's
                // signed hotspot after a nonfatal hit changes its descriptor.
                link.outY = static_cast<int16_t>(
                    (target->y + target->hotspotY - self->y - self->hotspotY + link.offY) * link.gain + link.biasY);
            } else {
                if (!target) continue;
                // Mode 0xff is a VERTICAL-only oscillation about the anchor,
                // not a two-axis orbit. A live level-7 capture pins the rule
                // over all 128 phases and all four orbit links, 774/774 ticks
                // exact on both axes:
                //   outX = anchor.x + offX                     (no x term)
                //   outY = anchor.y + offY + trunc(sin[phase] * radiusY)
                // radiusY is link byte +0x05; byte +0x04 is not an x radius,
                // so the cosine term the port used to add was a spurious 1 px
                // horizontal wobble. The scale is the shipped table's literal
                // 6.28 (not 2*pi), and the product truncates toward zero --
                // rounding to nearest is off by one on 21 of the 128 phases.
                link.phase = static_cast<uint8_t>((link.phase + link.gain) & 0x7f);
                const float sinValue = bossSinTable_[link.phase];
                link.outX = static_cast<int16_t>(target->x + link.offX);
                link.outY = static_cast<int16_t>(
                    target->y + target->hotspotY + link.offY +
                    static_cast<int>(sinValue * link.radiusY));
            }
            if (!legacyActorSeedsEnabled_)
                actorSlots_.writeLinkMotion(index+1,link.phase,link.outX,link.outY);
        }
    }

void GameplayOperations::applyBossSegmentLinks(ActiveMonster& monster) {
        const std::array<uint8_t, 3> serials{monster.linkA, monster.linkB, monster.linkC};
        for (uint8_t serial : serials) {
            if (serial == 0) break;
            int sign = 1;
            uint8_t index = serial;
            if (index > 0x80) {
                index = static_cast<uint8_t>(index - 0x80);
                sign = -1;
            }
            if (index == 0 || index > bossLinks_.size()) continue;
            const BossMotionLink& link = bossLinks_[index - 1];
            if (link.mode != 0xff) {
                monster.vx8 = clampI16(monster.vx8 + sign * link.outX);
                monster.vy8 = clampI16(monster.vy8 + sign * link.outY);
                const int limit = link.mode;
                if (std::abs(monster.vx8) > limit) {
                    monster.vx8 = static_cast<int16_t>(
                        monster.vx8 - (monster.vx8 > 0 ? limit : -limit));
                }
                if (std::abs(monster.vy8) > limit) {
                    monster.vy8 = static_cast<int16_t>(
                        monster.vy8 - (monster.vy8 > 0 ? limit : -limit));
                }
            } else {
                monster.x = link.outX;
                monster.y = link.outY;
                monster.vx8 = 0;
                monster.vy8 = 0;
                monster.fracX = 0;
                monster.fracY = 0;
            }
        }
    }

bool GameplayOperations::isBossMotionBehavior(int behavior) {
        return behavior == 5 || behavior == 6;
    }

bool GameplayOperations::bossScanTileSolid(int index, int upper) const {
        if (index < 0 || static_cast<size_t>(index) >= level_.tiles.size()) {
            return false;
        }
        int tile = level_.tiles[static_cast<size_t>(index)];
        return tile >= 1 && tile <= upper;
    }

BossHeadEdges GameplayOperations::scanBossHeadEdges(const ActiveMonster& monster) const {
        BossHeadEdges edges;
        const int stride = level_.width;
        const int width = monster.bossBoxW;
        const int height = monster.bossBoxH;
        const int base = (monster.y >> 3) * stride + (monster.x >> 3);
        for (int i = 0; i < width; ++i) {
            if (bossScanTileSolid(base - stride + i, 0x4c)) edges.top = true;
            if (bossScanTileSolid(base + height * stride + i, 0x52)) {
                edges.bottom = true;
            }
        }
        for (int i = 0; i < height; ++i) {
            if (bossScanTileSolid(base - 1 + i * stride, 0x4c)) edges.left = true;
            if (bossScanTileSolid(base + width + i * stride, 0x4c)) {
                edges.right = true;
            }
        }
        return edges;
    }

void GameplayOperations::updateBossHead(ActiveMonster& monster) {
        // 1000:5E59 divides the shared 16-bit DS:78C2 clock, including wrap.
        monster.bossTick = static_cast<uint16_t>(logicTick_);
        // The original scans all four edges up front and the later gravity,
        // jump and reflection steps all read those flags, so scan first.
        const BossHeadEdges edges = scanBossHeadEdges(monster);
        // The actor-update caller computes both players' deltas and chooses the
        // Manhattan-nearest one before entering behavior 6. The callee reads
        // that selected X delta indirectly through caller local [BP-4].
        if (monster.bossTick % 29 == 0) {
            const int roarRoll = static_cast<int>(randomRangeValue(0, 100));
            if (roarRoll > 0x46 && (monster.bossTick & 1) == 0) {
                requestSoundCursor(kBossHeadRoarSoundCursor, kBossHeadRoarSoundPriority);
            }
            const int speed = 0x96 + static_cast<int>(randomRangeValue(0, 0x320));
            const Player& target =
                nearestPlayer(static_cast<float>(monster.x),
                              static_cast<float>(monster.y));
            monster.vx8 =
                clampI16(target.x > static_cast<float>(monster.x)
                             ? speed
                             : -speed);
            if (edges.bottom) {
                monster.vy8 = clampI16(-(0x12c + static_cast<int>(randomRangeValue(0, 0x5dc))));
            }
        }
        damageBossHeadFromFlames(monster);
        // Gravity (file 0x673b..0x6742): `add WORD ss:[di-0xe],0x40` is guarded
        // by `cmp BYTE ss:[di-0x21],0 / jne`, so it is applied ONLY when the
        // bottom flag is clear, and there is no upper clamp anywhere in
        // 1000:5CB0..604F. A live level-7 capture reaches vy 0x0a40, well past
        // the 0x07ff the port used to clamp to.
        if (!edges.bottom) {
            monster.vy8 = clampI16(monster.vy8 + 0x40);
        }
        // Reflection (file 0x6743..0x67bf): a top edge with negative velocity,
        // or a bottom edge with positive velocity, replaces the velocity with
        // -(v/2) using `idiv` truncation toward zero; the left/right pair does
        // the same for the horizontal velocity. The original does NOT reset the
        // 8.8 sub-pixel fraction here, and does not push the head out of the
        // tile -- the scan runs one tile outside the box, so the reversal
        // happens before the head enters solid geometry.
        if ((edges.top && monster.vy8 < 0) || (edges.bottom && monster.vy8 > 0)) {
            monster.vy8 = static_cast<int16_t>(-(monster.vy8 / 2));
        }
        if ((edges.left && monster.vx8 < 0) || (edges.right && monster.vx8 > 0)) {
            monster.vx8 = static_cast<int16_t>(-(monster.vx8 / 2));
        }
    }

void GameplayOperations::damageBossHeadFromFlames(ActiveMonster& monster) {
        int damage = 0, lastCell = 0;
        const int headTileX = monster.x / kTileSize;
        const int headTileY = monster.y / kTileSize;
        for (int dy = 0; dy < monster.bossBoxH; ++dy) {
            for (int dx = 0; dx < monster.bossBoxW; dx += 2) {
                if (tileAt(headTileX + dx, headTileY + dy) != 0x75) continue;
                ++damage;
                lastCell = (headTileY + dy) * level_.width + headTileX + dx;
            }
        }
        if (damage == 0) return;
        const auto ray = std::find_if(flameRecords_.rbegin(), flameRecords_.rend(),
            [lastCell](const FlameRecord& item) { return item.cell == lastCell; });
        if (ray != flameRecords_.rend() && ray->mass > 1) damage *= 2;
        if (damage > monster.bossHpByte) {
            --monster.bossLives;
        }
        monster.bossHpByte = static_cast<uint8_t>(monster.bossHpByte - damage);
        // 1000:5A75 replaces the visible descriptor and signed hotspot only.
        // The caller still holds collision-space Y until its final writeback.
        monster.animFrame = 0x2f - 1;
        monster.hotspotY = static_cast<int8_t>(16 - altSprites_.sprites.at(monster.animFrame).height);
        if (!legacyActorSeedsEnabled_ || actorSlots_.find(monster.actorOrder))
            actorSlots_.writeBossDamage(monster.actorOrder,monster.bossHpByte,monster.bossLives,
                actorSpriteDescriptor(static_cast<uint16_t>(monster.animFrame)+1));
        if (monster.bossLives == 0xff) bossDeathChain(monster);
    }

void GameplayOperations::bossDeathChain(ActiveMonster& head) {
        for (ActiveMonster& monster : monsters_) {
            if (!monster.alive) continue;
            if (monster.kind == 0x1f && monster.bossGroup == head.bossGroup) {
                monster.kind = 0x0e;
                monster.behavior = 2;
                monster.bossDebris = true;
                monster.animMode = 0;
                monster.stateTimer = 0x28 + static_cast<int>(randomRangeValue(0, 10));
                if (!legacyActorSeedsEnabled_ || actorSlots_.find(monster.actorOrder))
                    actorSlots_.enterBossDebris(monster.actorOrder,static_cast<uint8_t>(monster.stateTimer));
            }
        }
        head.kind = 0x0e;
        head.behavior = 2;
        head.bossDebris = true;
        head.animMode = 0;
        head.stateTimer = 0x3c;
        if (!legacyActorSeedsEnabled_ || actorSlots_.find(head.actorOrder))
            actorSlots_.enterBossDebris(head.actorOrder,static_cast<uint8_t>(head.stateTimer));
        applyTileTrigger(1000);
        requestTileTriggerSound();
        bossDefeated_ = true;
        requestMonsterDeathSound();
    }

void GameplayOperations::updateMonsterSpawners() {
        // Recovered original spawner loop, 1000:7A6B..7C2C. The decisive byte
        // order per record:
        //   1000:7A9B  dec  es:[di+0x1b]      ; countdown FIRST, before every
        //                                     ; gate -- the byte free-runs and
        //                                     ; wraps 0->255 even when budget
        //                                     ; or slots are spent
        //   1000:7AA2  cmp  es:[di+0x1b],0    ; spawn path only when it
        //              je   ...               ; REACHES 0 this tick
        //   1000:7AAF  cmp  es:[di+0x0a],0    ; live-slot gate
        //   1000:7ABC  cmp  es:[di+0x09],0    ; budget gate
        //   1000:7AC9  cmp  es:[di+0x08],1    ; enabled gate
        //   1000:7AD6  mov  al,es:[di+0x1c]   ; reload from the reset byte...
        //   1000:7ADD  mov  es:[di+0x1b],al   ; ...BEFORE the spawn helper
        //   1000:7B28  call (spawn helper)
        //   1000:7B2B  cmp  ds:0x2072,1       ; helper failure keeps the
        //                                     ; reload but spends nothing
        //   1000:7B38/7B3F dec budget / slots ; only on success, then the RNG
        //                                     ; draws ai0, ai1, ai2, hp
        // A blocked spawn (gates fail at countdown 0) does NOT reload, so the
        // byte wraps and retries 256 ticks later (capture: 5/5 free-running
        // wraps with live=2). Fit: 1458/1458 byte transitions, first spawn at
        // frame 257 (0xE5 = 229 ticks after frame 28), period exactly 90.
        for (size_t i = 0; i < spawnerStates_.size() && i < level_.monsterSpawners.size(); ++i) {
            SpawnerState& state = spawnerStates_[i];
            const MonsterSpawner& spawner = level_.monsterSpawners[i];
            const auto source = static_cast<uint8_t>(i + 1);
            if (legacyActorSeedsEnabled_) {
                auto row = lezac::resources::packMonsterSpawner(spawner);
                row[9] = static_cast<uint8_t>(state.remaining);
                row[10] = static_cast<uint8_t>(state.availableSlots);
                row[27] = state.cooldown;
                spawnerStorage_.loadRecord(source, row);
            }
            const auto& row = spawnerStorage_.record(source);
            const bool ready = spawnerStorage_.tick(source);
            state = {row[9], row[10], row[27]};
            if (!ready) continue;
            ActiveMonster monster;
            monster.x = spawner.x;
            monster.kind = spawner.monsterKind;
            const auto selectors = lezac::gameplay::monsterAnimationSelectors(monster.kind);
            monster.animationSetLeft = selectors[0];
            monster.animationSetRight = selectors[1];
            monster.spawnerIndex = i;
            monster.hasSpawner = true;
            monster.behavior = spawner.spawnArg;
            auto frames = lezac::gameplay::monsterFacingFrameRange(monster);
            monster.animStart = static_cast<uint8_t>(frames[0]);
            monster.animEnd = static_cast<uint8_t>(frames[1]);
            monster.animFrame = monster.animStart;
            monster.animCursor = monster.animStart;
            // DS:79A3 is also the corpse-reward roll scratch byte.
            corpseRewardRoll_ = static_cast<uint8_t>(monster.animFrame + 1);
            monster.hotspotY = static_cast<int8_t>(16 - actorSpriteDescriptor(corpseRewardRoll_)[1]);
            monster.y = static_cast<int>(spawner.y) - monster.hotspotY;
            // Raw delay byte: the shared advance fires when the counter
            // EXCEEDS it (1000:608F cmp/ja), so delay 3 means period 4.
            monster.animDelay = spawner.animationDelay;
            // The anim init helper (1000:06AB) leaves the counter AT the
            // delay, so the first entity update advances immediately: the
            // spawn-tick visible frame is animStart + 1, the pair's high
            // member (capture: 2/2 spawns show 44).
            monster.animTick = monster.animDelay;
            initializeMonsterMotion(monster);
            monster.actorOrder = allocateActor({monster.kind, static_cast<uint8_t>(monster.stateTimer), monster.behavior,
                static_cast<uint16_t>(monster.animFrame + 1), monster.vx8, monster.vy8,
                static_cast<int16_t>(monster.x), static_cast<int16_t>(monster.y + monster.hotspotY)});
            if (!monster.actorOrder) continue;
            spawnerStorage_.consume(source);
            state = {row[9], row[10], row[27]};
            monster.ai0 = randomRangeValue(spawner.param0Base, spawner.param0Range);
            monster.ai1 = randomRangeValue(spawner.param1Base, spawner.param1Range);
            monster.ai2 = randomRangeValue(spawner.param2Base, spawner.param2Range);
            monster.hp = 1 + static_cast<uint8_t>(randomRangeValue(spawner.randomBase, spawner.randomRange));
            actorSlots_.initializeSpawnedMonster(monster.actorOrder, monster, static_cast<uint8_t>(i + 1));
            monster.animationBackup = actorSlots_.animationBackup(monster.actorOrder);
            monsters_.push_back(monster);
        }
    }

void GameplayOperations::applyGroundMonsterGravity(ActiveMonster& monster) {
        const ActiveMonster::EdgeFlags& edges = monster.edges;
        if (!edges.bottom || monster.vy8 < 0) {
            // 1000:717A adds a word before the signed terminal-speed compare.
            const int16_t accelerated = static_cast<int16_t>(monster.vy8 + 0x40);
            monster.vy8 = std::min<int16_t>(0x07ff, accelerated);
        } else if (monster.vy8 > 0) {
            monster.vy8 = 0;
            monster.y &= ~7;
            monster.facingDirty = true;
        }
    }

void GameplayOperations::consumeMonsterObjectTiles(uint16_t footprint) {
        const auto width = static_cast<uint16_t>(level_.width);
        const auto first = static_cast<uint16_t>(footprint + width);
        const auto second = static_cast<uint16_t>(first + width + 1);
        sound_.writeSharedCursor(0);
        const auto consume = [&](uint16_t cell) {
            const int x = cell % width, y = cell / width;
            const auto above = static_cast<uint16_t>(cell - width);
            const auto result = lezac::gameplay::queryMonsterObjectConsumption(
                static_cast<uint8_t>(tileAt(x, y)), wordAt(x, y), wordAt(above % width, above / width));
            corpseRewardRoll_ = result.scratch;
            actorSlots_.setSharedResult(result.sprite);
            monsterTileDamageDelta_ = result.seedAbove ? 1 : 0;
            sound_.writeSharedCursor(static_cast<uint16_t>(sound_.requestCursor() + result.score));
            if (result.consumed) {
                tileRef(x, y) = result.glyph;
                level_.wordLayer[cell] = result.word;
            }
            sound_.writeSharedCursor(static_cast<uint16_t>(sound_.requestCursor() + result.sprite));
            return result.seedAbove;
        };
        // Only the first call seeds above it; the second cursor advances by width+1.
        if (consume(first)) {
            const auto above = static_cast<uint16_t>(first - width);
            queueTileDamage(above % width, above / width, 0, 0, true);
        }
        consume(second);
        if (sound_.requestCursor() != 0) requestSoundCursor(0x21, 1);
    }

void GameplayOperations::updateMonsters(float dt, uint64_t onlyOrder ) {
        adoptUnorderedActors();
        for (ActiveMonster& monster : monsters_) {
            if (onlyOrder && monster.actorOrder != onlyOrder) continue;
            if (!monster.alive) continue;
            // 1000:6078..615A precedes behavior dispatch, including corpses.
            const bool animationAdvanced = lezac::gameplay::advanceMonsterAnimation(monster);
            if (debugMonsterAnimationObserver_) debugMonsterAnimationObserver_(monster, animationAdvanced);
            if ((monster.kind >= 1 && monster.kind <= 8) || isBossMotionBehavior(monster.behavior))
                actorSlots_.writeMonsterAnimation(monster.actorOrder, monster, animationAdvanced,
                    animationAdvanced ? actorSpriteDescriptor(monster.animCursor + 1)
                                      : lezac::gameplay::ActorSlots::Descriptor{});
            if (monster.behavior == 2) {
                if (monster.bossDebris) {
                    updateTimedActorMotion(monster.x, monster.y, monster.vx8, monster.vy8,
                                           monster.fracX, monster.fracY, scanActorEdges(monster.x, monster.y));
                    if (logicTick_ & 1u) monster.stateTimer = static_cast<uint8_t>(monster.stateTimer - 1);
                    if (!legacyActorSeedsEnabled_ || actorSlots_.find(monster.actorOrder))
                        actorSlots_.writeCorpse(monster.actorOrder,monster,static_cast<uint8_t>(monster.stateTimer),
                            animationAdvanced,animationAdvanced ? actorSpriteDescriptor(monster.animCursor+1)
                                : lezac::gameplay::ActorSlots::Descriptor{});
                    if (monster.stateTimer == 0 || monster.stateTimer == 0xff) {
                        Bomb bomb;
                        bomb.type = BombType::Medium;
                        bomb.pixelX = monster.x;
                        bomb.pixelY = monster.y + monster.hotspotY;
                        bomb.x = monster.x >> 3;
                        bomb.y = bomb.pixelY >> 3;
                        bomb.fracX = monster.fracX; bomb.fracY = monster.fracY;
                        bomb.actorOrder = monster.actorOrder;
                        bomb.bossVisualOrder = monster.bossVisualOrder;
                        monster.alive = false;
                        explode(bomb);
                    }
                    continue;
                }
                bool expired = false;
                if (monster.kind == 0x0c) {
                    const auto& raw = actorSlots_.actor(monster.actorOrder);
                    uint8_t timer = raw[0] == 0x0c ? raw[2]
                        : lezac::gameplay::corpseTimerFromRemainingUpdates(monster.stateTimer, logicTick_);
                    expired = lezac::gameplay::advanceCorpseMotion(monster, timer, logicTick_,
                        [this](int& x, int& y, int16_t& vx, int16_t& vy, uint8_t& fx, uint8_t& fy) {
                            updateTimedActorMotion(x, y, vx, vy, fx, fy, scanActorEdges(x, y));
                        });
                    actorSlots_.writeCorpse(monster.actorOrder, monster, timer, animationAdvanced,
                        animationAdvanced ? actorSpriteDescriptor(monster.animCursor + 1)
                                          : lezac::gameplay::ActorSlots::Descriptor{});
                } else expired = --monster.stateTimer <= 0;
                if (expired) {
                    // Corpse expiry reuses its slot for the reward or fade.
                    // Do not count both representations during allocation.
                    monster.alive = false;
                    if (monster.deathRewardPending) {
                        finishMonsterDeathReward(monster);
                        monster.deathRewardPending = false;
                    } else retireActor(monster.actorOrder);
                    releaseMonsterSlot(monster);
                }
                continue;
            }
            const int damageColumn = (monster.x + 4) >> 3;
            const int damageRow = monster.y >> 3;
            // Rank 5: the player-contact test runs BEFORE the tile scan and
            // the motion update (contact at 1000:63C6..63F0, scan from
            // 1000:655B), i.e. from the PRE-motion position. monster.y is the
            // collision-space y (rank 6), which carries the actor +0x14 bias
            // the original applies at 1000:629D before both the contact test
            // and the scan.
            if (!playerDead_ && actorTouchesPlayer(player_, monster.x, monster.y)) {
                queuePlayerDamage(1);
            }
            if (playerCount_ > 1 && !player2Dead_ &&
                actorTouchesPlayer(player2_, monster.x, monster.y)) {
                queuePlayerDamage(2);
            }
            // The level-3 behavior-4 lockstep extends the recovered edge-scan
            // path to free flyers. They use the same pre-integration scan and
            // common top/side response, but have their own bottom reflection
            // before steering and never receive gravity.
            const bool recoveredResolution =
                !isBossMotionBehavior(monster.behavior);
            if (recoveredResolution) {
                monster.edges = scanActorEdges(monster.x, monster.y);
                // Facing-reselect request, seeded from wall contact exactly
                // where the original's behaviour-3 dispatch does it
                // (1000:7159..716B: [bp-0x20] = left || right).
            } else {
                monster.edges = {};
            }
            updateMonsterMotion(monster, dt);

            // Boss segments (behavior 5) are positioned purely by their
            // motion links in the original and pass through terrain. The boss
            // head (behavior 6) is excluded too: 1000:5CB0 does its own
            // four-edge scan and reflects there, keeping the 8.8 fraction.
            if (recoveredResolution) {
                // The facing consume (1000:727D, reselect branches
                // 1000:7286/72DA) sits BEFORE the wall reflection in the
                // instruction stream, so a wall tick consumes the flag with
                // the PRE-reflection vx and re-selects the OLD facing set --
                // an unconditional cursor reset to that set's base -- while
                // the NEW set is selected on the following tick, when the
                // renormalisation (1000:71F3) raises the flag again with the
                // reversed vx. The capture adjudicates the order: walker A's
                // wall tick 374 has the renorm tick 375 land before the next
                // advance tick 376, so its flip shows at row 377 (the next
                // boundary), but walker B's wall tick 481 is immediately
                // followed by the advance tick 482, whose prologue still
                // steps the OLD right pair (46 at row 483, 3/3 wall turns);
                // the left pair only appears at row 487. Reselecting after
                // the reflection flips one boundary early in B's phase.
                if (monster.kind == 4)
                    consumeMonsterObjectTiles(static_cast<uint16_t>(damageRow * level_.width + damageColumn));
                const ActiveMonster::EdgeFlags e = monster.edges;
                if (e.top && monster.vy8 < 0) monster.vy8 = 1;
                if (e.left && e.right) {
                    monster.vx8 = 0;
                } else if ((e.left && monster.vx8 < 0) || (e.right && monster.vx8 > 0)) {
                    // 1000:73CC negates the word before IDIV, including -32768.
                    const int16_t negated = static_cast<int16_t>(-monster.vx8);
                    monster.vx8 = static_cast<int16_t>(negated / 2);
                    monster.x += monster.vx8 < 0 ? -1 : 1;
                }
                integrateAxis8_8(monster.y, monster.fracY, monster.vy8);
                integrateAxis8_8(monster.x, monster.fracX, monster.vx8);
                // The common native ADCs store signed 16-bit coordinate locals.
                monster.x = static_cast<int16_t>(monster.x);
                monster.y = static_cast<int16_t>(monster.y);
            } else {
                integrateAxis8_8(monster.x, monster.fracX, monster.vx8);
                integrateAxis8_8(monster.y, monster.fracY, monster.vy8);
            }

            // 1000:7530 stores coordinates directly, without level-bound clamps.
            if (monster.kind >= 1 && monster.kind <= 8) {
                // 1000:7427 calls 56B6 using the pre-motion 2x2 footprint.
                const auto query = lezac::gameplay::queryMonsterTileDamage(
                    damageColumn, damageRow, level_.width,
                    [this](int x, int y) { return tileAt(x, y); });
                actorSlots_.setSharedResult(query.lastFlameCell);
                sound_.writeSharedCursor(query.footprintCell);
                monsterTileDamageDelta_ = query.delta;
                if (query.delta != 0) damageMonster(monster, -query.delta, true);
                actorSlots_.writeMonsterMotion(monster.actorOrder, monster);
            }
            if (isBossMotionBehavior(monster.behavior) || monster.bossDebris)
                actorSlots_.writeMonsterMotion(monster.actorOrder,monster);
        }
        monsters_.erase(std::remove_if(monsters_.begin(), monsters_.end(),
                                       [](const ActiveMonster& monster) { return !monster.alive; }),
                        monsters_.end());
    }

void GameplayOperations::releaseMonsterSlot(ActiveMonster& monster) {
        if (!monster.hasSpawner || monster.deathCredited) return;
        const auto source = legacyActorSeedsEnabled_ ? static_cast<uint8_t>(monster.spawnerIndex + 1)
            : actorSlots_.actor(monster.actorOrder)[37];
        if (legacyActorSeedsEnabled_ && monster.spawnerIndex < spawnerStates_.size()) {
            auto row = spawnerStorage_.record(source);
            row[10] = static_cast<uint8_t>(spawnerStates_[monster.spawnerIndex].availableSlots);
            spawnerStorage_.loadRecord(source, row);
        }
        if (!spawnerStorage_.release(source)) return;
        if (source - 1u < spawnerStates_.size())
            spawnerStates_[source - 1u].availableSlots = spawnerStorage_.record(source)[10];
        monster.deathCredited = true;
        monster.hasSpawner = false;
    }

void GameplayOperations::updateDamageCooldowns() {
        if (damageCooldown_ > 0) --damageCooldown_;
        if (damageCooldown2_ > 0) --damageCooldown2_;
    }

void GameplayOperations::queuePlayerDamage(uint8_t startMarker, uint8_t amount ) {
        if (amount == 0) return;
        bool secondPlayer = startMarker == 2 && playerCount_ > 1;
        bool dead = secondPlayer ? player2Dead_ : playerDead_;
        int cooldown = secondPlayer ? damageCooldown2_ : damageCooldown_;
        if (!dead && cooldown > 0) return;
        uint8_t& pending = secondPlayer ? pendingDamage2_ : pendingDamage_;
        pending = static_cast<uint8_t>(pending + amount);
    }

void GameplayOperations::drainPlayerDamageCounters() {
        drainPlayerDamageCounter(player_, energy_, lives_, playerDead_, reentryTimer_,
                                 pendingDamage_, 1);
        if (playerCount_ > 1) {
            drainPlayerDamageCounter(player2_, energy2_, lives2_, player2Dead_,
                                     reentryTimer2_, pendingDamage2_, 2);
        } else {
            pendingDamage2_ = 0;
        }
    }

void GameplayOperations::drainPlayerDamageCounter(Player& player, int& energy, int& lives,
                                  bool& dead, int& timer, uint8_t& pending,
                                  uint8_t startMarker) {
        const uint8_t globalState = originalPlayerState(startMarker);
        uint8_t amount = pending;
        pending = 0;
        if (dead) {
            if (amount != 0) requestPlayerDamageSound();
            updatePlayerHudEnergy(startMarker, static_cast<uint8_t>(energy), globalState);
            return;
        }
        uint8_t updatedEnergy =
            static_cast<uint8_t>(std::clamp(energy, 0, 255) - amount);
        energy = static_cast<int>(updatedEnergy);
        writePlayerHealth(startMarker, energy);
        if (amount != 0) requestPlayerDamageSound();
        uint16_t hudEnergy = updatedEnergy;
        if (static_cast<uint16_t>(updatedEnergy) > 0x00c8) {
            // Death helper 30A3 leaves this count in DS:2074 while resetting
            // the separate actor energy byte to 100 (3134).
            hudEnergy = static_cast<uint16_t>(remainingObjectiveTiles());
            beginPlayerDeath(player, energy, lives, dead, timer, startMarker);
        }
        updatePlayerHudEnergy(startMarker, hudEnergy, globalState);
    }

void GameplayOperations::damagePlayer(Player& player, int& energy, int& lives, bool& dead,
                      int& timer, int& damageCooldown, uint8_t startMarker) {
        (void)damageCooldown;
        uint8_t immediateDamage = 1;
        drainPlayerDamageCounter(player, energy, lives, dead, timer,
                                 immediateDamage, startMarker);
    }

bool GameplayOperations::playerOverlapsTileArea(const Player& player, int tx0, int ty0,
                                int tx1, int ty1) const {
        float x = static_cast<float>(tx0 * kTileSize);
        float y = static_cast<float>(ty0 * kTileSize);
        float w = static_cast<float>((tx1 - tx0 + 1) * kTileSize);
        float h = static_cast<float>((ty1 - ty0 + 1) * kTileSize);
        return playerOverlaps(player, x, y, w, h);
    }

void GameplayOperations::damagePlayersInTileArea(int tx0, int ty0, int tx1, int ty1) {
        tx0 = std::clamp(tx0, 0, std::max(0, level_.width - 1));
        tx1 = std::clamp(tx1, 0, std::max(0, level_.width - 1));
        ty0 = std::clamp(ty0, 0, std::max(0, level_.height - 1));
        ty1 = std::clamp(ty1, 0, std::max(0, level_.height - 1));
        if (tx0 > tx1) std::swap(tx0, tx1);
        if (ty0 > ty1) std::swap(ty0, ty1);
        if (playerOverlapsTileArea(player_, tx0, ty0, tx1, ty1)) {
            queuePlayerDamage(1);
        }
        if (playerCount_ > 1 && playerOverlapsTileArea(player2_, tx0, ty0, tx1, ty1)) {
            queuePlayerDamage(2);
        }
    }

void GameplayOperations::beginPlayerDeath(Player& player, int& energy, int& lives, bool& dead,
                          int& timer, uint8_t startMarker) {
        // 1000:30C1..30F5 latches one shared gate at death. Waiting does not
        // recompute it when objective tiles or the collected count change.
        reentryGate_ = canReenterLevel();
        if (debugDeathGateObserver_) debugDeathGateObserver_(startMarker);
        pendingLifeLossFor(startMarker) = lives >= 0;
        deathStateTimerFor(startMarker) = kDeathStateTicks;
        State2VisualCursor& cursor = state2VisualCursorFor(startMarker);
        resetState2VisualCursor(cursor);
        actorSlots_.setPlayerBehavior(startMarker - 1, 2);
        actorSlots_.setPlayerCountdown(startMarker - 1, kDeathStateTicks);
        refreshState2EffectEntry(player, cursor, state2EffectEntryFor(startMarker));
        syncPlayerVelocityMirror(player);
        player.grounded = false;
        energy = 100;
        writePlayerHealth(startMarker, energy);
        if (lives < 0) {
            dead = true;
            timer = 0;
            cursor.active = false;
            state2EffectEntryFor(startMarker).active = false;
            requestPlayerDeathSound();
            if (allPlayersOutOfLives()) beginGameOver();
            return;
        }
        dead = true;
        timer = kDeathStateTicks;
        requestPlayerDeathSound();
    }

State2VisualCursor& GameplayOperations::state2VisualCursorFor(uint8_t startMarker) {
        return startMarker == 2 && playerCount_ > 1 ? state2Visual2_
                                                     : state2Visual_;
    }

State2EffectEntry& GameplayOperations::state2EffectEntryFor(uint8_t startMarker) {
        return startMarker == 2 && playerCount_ > 1 ? state2Effect2_
                                                     : state2Effect_;
    }

void GameplayOperations::refreshState2EffectEntry(const Player& player,
                                  const State2VisualCursor& cursor,
                                  State2EffectEntry& entry) {
        entry.active = cursor.active;
        if (!entry.active) return;
        entry.x = static_cast<int>(player.x);
        entry.y = static_cast<int>(player.y);
        entry.visualFrame = cursor.current;
        State2VisualRow row;
        if (originalState2VisualRow(cursor.current, row)) {
            entry.drawDx = row.row0;
            entry.drawDy = row.row1;
            entry.row2 = row.row2;
            entry.spriteIndex = row.row3;
            return;
        }
        entry.drawDx = 0;
        entry.drawDy = 0;
        entry.row2 = 0;
        entry.spriteIndex = cursor.current;
    }

void GameplayOperations::resetState2VisualCursor(State2VisualCursor& cursor) {
        cursor.current = kState2VisualStartFrame;
        cursor.first = kState2VisualStartFrame;
        cursor.last = kState2VisualEndFrame;
        cursor.counter = kState2VisualDelay;
        cursor.delay = kState2VisualDelay;
        cursor.mode = 1;
        cursor.step = 1;
        cursor.active = true;
        writeState2Animation(cursor);
    }

bool GameplayOperations::updateState2VisualCursor(State2VisualCursor& cursor) {
        if (!cursor.active || cursor.mode == 0) return false;
        ++cursor.counter;
        if (cursor.counter <= cursor.delay) { writeState2Animation(cursor); return false; }
        cursor.counter = 0;
        cursor.current = static_cast<uint8_t>(
            static_cast<int>(cursor.current) + static_cast<int>(cursor.step));
        if (cursor.mode == 2) {
            if (cursor.current >= cursor.last || cursor.current <= cursor.first) {
                cursor.step = static_cast<int8_t>(-cursor.step);
            }
            writeState2Animation(cursor);
            return true;
        }
        if (cursor.current > cursor.last) {
            cursor.current = cursor.first;
        }
        writeState2Animation(cursor);
        return true;
    }

bool GameplayOperations::allPlayersOutOfLives() const {
        return playerCount_ <= 1 ? lives_ < 0 : lives_ < 0 && lives2_ < 0;
    }

int& GameplayOperations::deathStateTimerFor(uint8_t startMarker) {
        return startMarker == 2 && playerCount_ > 1 ? deathStateTimer2_
                                                     : deathStateTimer_;
    }

bool& GameplayOperations::pendingLifeLossFor(uint8_t startMarker) {
        return startMarker == 2 && playerCount_ > 1 ? pendingLifeLoss2_
                                                     : pendingLifeLoss_;
    }

void GameplayOperations::finalizePendingLifeLoss(bool& dead, int& lives, int& timer,
                                 uint8_t startMarker) {
        bool& pending = pendingLifeLossFor(startMarker);
        if (!pending) return;
        pending = false;
        --lives;  // The original reserve byte marks out at FF, not at zero.
        actorSlots_.setPlayerReserve(startMarker - 1, static_cast<uint8_t>(lives));
        if (lives < 0) {
            dead = true;
            timer = 0;
            state2VisualCursorFor(startMarker).active = false;
            state2EffectEntryFor(startMarker).active = false;
            actorSlots_.hidePlayer(startMarker - 1);
            if (remainingPlayerCount() == 1) gameRenderer_.clearEliminatedViewport(startMarker - 1);
            if (allPlayersOutOfLives()) beginGameOver();
        }
    }

bool GameplayOperations::canReenterLevel() const {
        return collected_ + remainingObjectiveTiles() >= level_.requiredBonus;
    }

int GameplayOperations::remainingObjectiveTiles() const {
        return static_cast<int>(std::count(level_.tiles.begin(), level_.tiles.end(),
                                           level_.objectiveTile));
    }

void GameplayOperations::updateWaitingPlayerPlacement(Player& player) {
        const uint16_t x = static_cast<uint16_t>(static_cast<int>(player.x));
        const uint16_t y = static_cast<uint16_t>(static_cast<int>(player.y));
        const uint16_t row = (static_cast<uint16_t>(y + 7) >> 3) + 1;
        const uint16_t cell = static_cast<uint16_t>(row * level_.width + (x >> 3));
        // DS:2074 is shared by this map scan and sound-request construction.
        sound_.writeSharedCursor(cell);
        auto solid = [&](uint16_t at) {
            const uint8_t tile = mapPlaneMemory_.readObject(at, level_.tiles, level_.wordLayer);
            return tile >= 1 && tile <= 76;
        };
        // 1000:7E41 jumps directly to DEC on the left cell. Only the right
        // cell has the unsigned Y > 24 guard; neither branch gates fire.
        if (solid(cell) || (solid(static_cast<uint16_t>(cell + 1)) && y > 24)) {
            player.y = static_cast<float>(static_cast<uint16_t>(y - 1));
            if (const auto index = ownedPlayerIndex(player))
                actorSlots_.setPlayerY(*index, static_cast<uint16_t>(static_cast<int>(player.y)));
        }
    }

void GameplayOperations::updateReentry(Player& player, int& energy, int& lives, bool& dead,
                       int& timer, uint8_t startMarker, bool allowLevelRestart) {
        (void)energy;
        (void)allowLevelRestart;
        if (!dead || lives < 0) return;
        timer = static_cast<uint16_t>(timer - 1);
        actorSlots_.setPlayerCountdown(startMarker - 1, static_cast<uint16_t>(timer));
        int& deathStateTimer = deathStateTimerFor(startMarker);
        if (deathStateTimer > 0) --deathStateTimer;
        if (timer == 0) {
            pendingLifeLossFor(startMarker) = true;
            finalizePendingLifeLoss(dead, lives, timer, startMarker);
            if (lives >= 0 && !ui_.snapshot().menu) {
                // 1000:7D11 calls the start-marker locator at 056B before
                // waiting for input; it preserves motion and animation bytes.
                placePlayerAtStart(player, startMarker);
                player.spriteIndex = 0x27 - 1;
                player.singlePixelSprite = !reentryGate_;
                writePlayerSprite(player);
                if (!reentryGate_) actorSlots_.reducePlayerDimensions(startMarker - 1);
                auto& inventory = startMarker == 2 ? bombInventory2_ : bombInventory_;
                constexpr std::array<int, 3> minimum{100, 10, 2};
                for (size_t i = 0; i < minimum.size(); ++i) {
                    inventory.counts[i] = std::max(inventory.counts[i], minimum[i]);
                }
            }
        }
        if (lives < 0 || ui_.snapshot().menu) return;
        if (!reentryGate_) noActivePlayerTicks_ = kSharedReentryTicks - 1;
        if (originalPlayerState(startMarker) == 2) updateWaitingPlayerPlacement(player);
    }

uint8_t GameplayOperations::originalPlayerState(uint8_t player) const {
        if (player == 2 && playerCount_ < 2) return 0;
        const int lives = player == 2 ? lives2_ : lives_;
        const bool dead = player == 2 ? player2Dead_ : playerDead_;
        const bool pending = player == 2 ? pendingLifeLoss2_ : pendingLifeLoss_;
        if (lives < 0) return 0;
        return dead && !pending && !levelRestartPromoted_ ? 2 : 1;
    }

bool GameplayOperations::updateSharedReentryFallback() {
        if (originalPlayerState(1) == 1 || originalPlayerState(2) == 1) {
            noActivePlayerTicks_ = 0;
            return false;
        }
        if (debugReentryBoundaryObserver_) debugReentryBoundaryObserver_("fallback_increment");
        ++noActivePlayerTicks_;
        if (noActivePlayerTicks_ != kSharedReentryTicks) return false;
        if (debugReentryBoundaryObserver_) debugReentryBoundaryObserver_("fallback_promote");
        levelRestartPromoted_ = true;
        restartCurrentLevelAfterDeath();
        return true;
    }

void GameplayOperations::tryReenterPlayer(Player& player, int& energy, int& lives, bool& dead,
                          int& timer, int& damageCooldown, uint8_t startMarker) {
        if (!dead) return;
        if (deathStateTimerFor(startMarker) > 0) return;
        finalizePendingLifeLoss(dead, lives, timer, startMarker);
        if (lives < 0) return;
        if (!reentryGate_) {
            return;
        }
        const auto& animation = state2VisualCursorFor(startMarker);
        player.animation = ActorAnimation{animation.current, animation.first, animation.last,
            animation.counter, animation.delay, animation.mode, animation.step};
        deathStateTimerFor(startMarker) = 0;
        state2VisualCursorFor(startMarker).active = false;
        state2EffectEntryFor(startMarker).active = false;
        (void)damageCooldown;
        dead = false;
        reentryFire1_ = reentryFire2_ = false;
        actorSlots_.setPlayerBehavior(startMarker - 1, startMarker - 1);
        energy = 100;
        writePlayerHealth(startMarker, energy);
    }

void GameplayOperations::respawnPlayerAtStart(Player& player, int& energy, uint8_t startMarker) {
        energy = 100;
        player.vx = 0.0f;
        player.vy = 0.0f;
        player.grounded = false;
        placePlayerAtStart(player, startMarker);
    }

void GameplayOperations::restartCurrentLevelAfterDeath() {
        beginLevelForPlay(levelIndex_);
    }

bool GameplayOperations::scoreQualifies(uint32_t score) const {
        return recordStore_.scoreQualifies(score);
    }

uint32_t& GameplayOperations::scoreForPlayer(uint8_t player) {
        return player == 2 && playerCount_ > 1 ? score2_ : score_;
    }

void GameplayOperations::addScore(uint8_t player, uint32_t amount) {
        scoreForPlayer(player) += amount;
    }

void GameplayOperations::clearRunScores() {
        score_ = 0;
        score2_ = 0;
        presentation_.clearHudScores();
    }

bool GameplayOperations::isFinalLevel() const {
        return !levels_.empty() &&
               levelIndex_ + 1 >= static_cast<int>(levels_.size());
    }

MenuPage GameplayOperations::endMenuPage(EndReason reason) const {
        return UiController::endMenuPage(reason);
    }

void GameplayOperations::beginGameOver() {
        beginEndRun(EndReason::GameOver);
    }

void GameplayOperations::abortRun() {
        actorSlots_.setSpriteBankTag(1);
        endScreenPattern_ = makeLevelIntroPattern();
        auto actions = uiActions();
        // Natural Escape retains the live map through Game Over and the menu.
        // The next beginLevelForPlay owns freeing and replacing that allocation.
        actions.resetAfterEndRun = [] {};
        ui_.beginEndRun(EndReason::GameOver, levelIndex_, playerCount_, score_, score2_, recordStore_, actions);
    }

void GameplayOperations::beginEndRun(EndReason reason) {
        actorSlots_.setSpriteBankTag(1);
        if (reason == EndReason::GameOver) endScreenPattern_ = makeLevelIntroPattern();
        ui_.beginEndRun(reason, levelIndex_, playerCount_, score_, score2_, recordStore_, uiActions());
    }

void GameplayOperations::finalizePendingRecord() {
        ui_.finalizePendingRecord(recordStore_, uiActions());
    }

void GameplayOperations::cancelPendingRecord() {
        ui_.cancelPendingRecord(recordStore_, uiActions());
    }

void GameplayOperations::clearPendingRecord() {
        recordStore_.clearPendingRecord();
    }

bool GameplayOperations::startNextPendingRecord() {
        return ui_.startNextPendingRecord(recordStore_, uiActions());
    }

void GameplayOperations::placeBombAt(const Player& player, BombInventory& inventory, uint8_t owner) {
        // 1000:6C00 leaves an empty selection and both fire latches unchanged.
        if (!hasBomb(inventory, inventory.selected)) return;
        // Both latches are consumed after a constructor attempt, even when
        // the shared actor pool rejects it (1000:6CA9..6CAE).
        reentryFire1_ = reentryFire2_ = false;
        if (sharedActorCount() >= 30) return;
        // Original pixel->tile mapping, from the blast routine at 655B..6582
        // (re-read this session: base = ((py>>3)-1)*width + (((px+4)>>3)-1))
        // plus the burn walk at 6CB8..6D1B, whose consumed 2x2 block has its
        // top-left tile at ((px+4)>>3, py>>3). The L2 capture pins the
        // arithmetic: player pixel (200,308) at drop -> base 3724 and
        // post-walk DS:C1E8 = 3925, exactly as measured. The identification
        // of initial bomb pixels with player pixels is also explicit in the
        // constructor call at 1000:6C25..6C5B. Motion refreshes these tile
        // coordinates from the bomb's own pixels before detonation.
        int tx = (static_cast<int>(player.x) + 4) / 8;
        int ty = static_cast<int>(player.y) / 8;
        BombProfile profile = bombProfile(inventory.selected);
        // First update is on the frame after construction. Encode the
        // odd-frame byte countdown as remaining game ticks.
        int timer = profile.fuseTicks - static_cast<int>((logicTick_ + 1) & 1u);
        Bomb bomb{tx, ty, timer, inventory.selected, profile.fuseTicks, owner};
        bomb.pixelX = static_cast<int>(player.x);
        bomb.pixelY = static_cast<int>(player.y);
        // 6C2B..6C41 wraps the multiply/subtraction before signed division.
        bomb.vx8 = clampConstructedActorVelocity8(static_cast<int16_t>(3 * player.vx8) / 2);
        bomb.vy8 = clampConstructedActorVelocity8(static_cast<int16_t>(player.vy8 - 500));
        bomb.moving = true;
        bomb.actorOrder = allocateActor({profile.actorKind, static_cast<uint8_t>(profile.fuseTicks / 2), 2,
            static_cast<uint16_t>(profile.spriteBase + 1), bomb.vx8, bomb.vy8,
            static_cast<int16_t>(bomb.pixelX), static_cast<int16_t>(bomb.pixelY)});
        if (!bomb.actorOrder) throw std::runtime_error("bomb allocation disagrees with capacity");
        // 1000:6C65..6C7B initializes the new slot's active animation, not its backup.
        actorSlots_.setActiveAnimation(bomb.actorOrder, {0, 0, 0, 0, 0, 0, 1});
        bombs_.push_back(bomb);
        requestBombPlaceSound();
        --inventory.counts[static_cast<size_t>(bombTypeIndex(inventory.selected))];
        inventory.hudDirty = 1;
    }

int GameplayOperations::bombHeightOffset(BombType type) const {
        const size_t sprite = bombProfile(type).spriteBase;
        return 16 - sprites_.sprites.at(sprite).height;
    }

void GameplayOperations::updateBombMotion(Bomb& bomb) {
        if (!bomb.moving) return;
        const int heightOffset = bomb.hotspotY >= 0 ? bomb.hotspotY : bombHeightOffset(bomb.type);
        int collideY = static_cast<int16_t>(bomb.pixelY - heightOffset);
        ActiveMonster::EdgeFlags edges;
        if (bomb.type == BombType::Small) {
            // 1000:65DA..6640 selects four single cells for actor kind 0x0d.
            // Other bombs use the usual two-cell actor edges.
            const int column = (bomb.pixelX + 4) >> 3;
            const int row = collideY >> 3;
            edges.top = solidTileSide(static_cast<uint8_t>(tileAt(column, row)));
            edges.bottom = solidTileBottom(static_cast<uint8_t>(tileAt(column, row + 2)));
            edges.left = solidTileSide(static_cast<uint8_t>(tileAt(column - 1, row + 1)));
            edges.right = solidTileSide(static_cast<uint8_t>(tileAt(column + 1, row + 1)));
        } else {
            edges = scanActorEdges(bomb.pixelX, collideY);
        }
        updateTimedActorMotion(bomb.pixelX, collideY, bomb.vx8, bomb.vy8,
                               bomb.fracX, bomb.fracY, edges);
        bomb.pixelY = static_cast<int16_t>(collideY + heightOffset);
        // 1000:75E3 uses visual X directly, without the collision-scan +4.
        bomb.x = bomb.pixelX >> 3;
        bomb.y = bomb.pixelY >> 3;
    }

void GameplayOperations::updateTimedActorMotion(int& x, int& y, int16_t& vx, int16_t& vy,
            uint8_t& fracX, uint8_t& fracY, const ActiveMonster::EdgeFlags& edges) {
        lezac::core::ActorMotionPrefixInput input;
        input.actor[21]=2;
        input.originalX=input.x=std::bit_cast<int16_t>(static_cast<uint16_t>(x));
        input.y=std::bit_cast<int16_t>(static_cast<uint16_t>(y));
        input.vx8=vx;input.vy8=vy;
        input.edges={static_cast<uint8_t>(edges.top),static_cast<uint8_t>(edges.bottom),
            static_cast<uint8_t>(edges.left),static_cast<uint8_t>(edges.right)};
        const auto result=runActorMotionPrefix(input);
        x=result.x;y=result.y;vx=result.vx8;vy=result.vy8;
        requireMotionTerrain(result);
        if (edges.top && vy < 0) vy = 1;
        if (edges.left && edges.right) vx = 0;
        else if ((edges.left && vx < 0) || (edges.right && vx > 0)) {
            // 1000:73CC narrows NEG before signed IDIV, including -32768.
            const int16_t reflected = static_cast<int16_t>(-vx);
            vx = static_cast<int16_t>(reflected / 2);
            x += vx < 0 ? -1 : 1;
        }
        integrateAxis8_8(y, fracY, vy);
        integrateAxis8_8(x, fracX, vx);
        x = static_cast<int16_t>(x);
        y = static_cast<int16_t>(y);
    }

void GameplayOperations::updateBombs(uint64_t onlyOrder ) {
        adoptUnorderedActors();
        std::vector<Bomb> expired;
        for (Bomb& b : bombs_) {
            if (onlyOrder && b.actorOrder != onlyOrder) continue;
            updateBombMotion(b);
            // 754A..7588 precedes the 75B0 countdown and 75FB explosion call.
            actorSlots_.writeBombMotion(b.actorOrder, b);
            --b.timer;
            actorSlots_.setTimer(b.actorOrder, static_cast<uint8_t>((b.timer + 1) / 2));
            if (b.timer <= 0) {
                expired.push_back(b);
                pendingActorConversions_.push_back(b.actorOrder);
            }
        }
        bombs_.erase(std::remove_if(bombs_.begin(), bombs_.end(),
                                    [onlyOrder](const Bomb& b) { return b.timer <= 0 && (!onlyOrder || b.actorOrder == onlyOrder); }),
                     bombs_.end());
        int generation = levelResetGeneration_;
        for (const Bomb& b : expired) {
            if (levelResetGeneration_ != generation) break;
            explode(b);
            const auto pending = std::find(pendingActorConversions_.begin(), pendingActorConversions_.end(), b.actorOrder);
            if (pending == pendingActorConversions_.end()) throw std::runtime_error("missing bomb conversion reservation");
            pendingActorConversions_.erase(pending);
        }
    }

std::vector<std::array<int, 2>> GameplayOperations::explosionTilesFor(const Bomb& bomb) const {
        std::vector<std::array<int, 2>> tiles;
        auto add = [&](int x, int y) {
            if (x < 0 || y < 0 || x >= level_.width || y >= level_.height) return;
            std::array<int, 2> pos{x, y};
            if (std::find(tiles.begin(), tiles.end(), pos) == tiles.end()) {
                tiles.push_back(pos);
            }
        };
        add(bomb.x, bomb.y);
        add(bomb.x + 1, bomb.y);
        add(bomb.x + 1, bomb.y + 1);
        add(bomb.x, bomb.y + 1);
        return tiles;
    }

void GameplayOperations::spawnExplosionEffect(const Bomb& bomb) {
        if (debugBombExpiryObserver_) debugBombExpiryObserver_(bomb, "before_explosion");
        if (explosionVisualType(bomb.type) > 1) cameraShakeTicks_ = 2;  // 1000:4164
        int visualType = explosionVisualType(bomb.type);
        int ticks = explosionEffectTicks(visualType);
        ExplosionEffect effect;
        effect.x = bomb.x;
        effect.y = bomb.y;
        effect.visualSelector = static_cast<uint8_t>(visualType);
        effect.dispatcherState = explosionDispatcherState(visualType);
        effect.timer = ticks;
        effect.totalTimer = ticks;
        effect.soundOffset = explosionSoundOffset(visualType);
        effect.soundSelector = explosionSoundSelector(visualType);
        effect.seedTicksByte = static_cast<uint8_t>(ticks & 0xff);
        effect.variantByte = explosionVariantByte(visualType);
        effect.computedX = bomb.x * kTileSize;
        effect.computedY = bomb.y * kTileSize;
        explosionEffects_.push_back(effect);
        seedFlameRecords(bomb.y * level_.width + bomb.x, visualType);
        requestSoundOffset(effect.soundOffset, effect.soundSelector);
    }

void GameplayOperations::seedFlameRecords(int cell, int type) {
        // Exact finite constructor outputs. Turbo Pascal's real48 sine/cosine
        // and truncation produce asymmetric bytes, including 79 rather than 80.
        static const std::array<std::vector<std::array<int, 2>>, 4> velocities{{
            {{79,0},{56,-56},{0,-79},{-56,-56},{-79,0},{-56,56},{0,79},{56,56}},
            {{109,0},{95,-54},{55,-95},{0,-109},{-54,-95},{-95,-55},
             {-109,0},{-95,54},{-55,95},{0,109},{54,95},{95,55}},
            {{109,0},{101,-41},{79,-76},{44,-100},{3,-109},{-37,-103},
             {-73,-81},{-98,-48},{-109,-7},{-104,33},{-84,70},{-51,97},
             {-11,109},{30,105},{67,86},{95,55},{108,15}},
            {{0,-125},{-32,-121},{-62,-109},{-88,-89},{-109,-63},{-121,-32},{-125,0},
             {125,0},{121,-32},{109,-62},{89,-89},{63,-109},{32,-121},
             {-125,0},{-121,32},{-109,62},{-89,88},{-63,108},{-32,121},{0,125},
             {21,124},{52,114},{80,96},{103,72},{118,43},{125,11}},
        }};
        if (type < 1 || type > 4) return;
        const auto& rays = velocities[static_cast<size_t>(type - 1)];
        for (size_t i = 0; i < rays.size() && flameRecords_.size() < 198; ++i) {
            int origin = cell;
            if (type == 4) {
                if (i >= 20) origin += level_.width + 1;
                else if (i >= 13) origin += level_.width;
                else if (i >= 7) ++origin;
            }
            FlameRecord record = flameRecords_.retainedSlot(flameRecords_.size());
            record.cell = static_cast<uint16_t>(origin);
            record.vx = static_cast<int8_t>(rays[i][0]);
            record.vy = static_cast<int8_t>(rays[i][1]);
            record.subX = 0;
            record.subY = 0;
            record.glyph = 0x75;
            record.timer = static_cast<uint8_t>(explosionEffectTicks(type));
            record.variant = explosionVariantByte(type);
            record.mass = static_cast<uint8_t>(type == 4 ? 221 : type == 3 ? 9 : 1);
            flameRecords_.push_back(record);
        }
    }

void GameplayOperations::updateFlameRecords() {
        auto object = [&](int cell) -> uint8_t {
            return cell >= 0 && static_cast<size_t>(cell) < level_.tiles.size() ? level_.tiles[cell] : 1;
        };
        auto stamp = [&](int cell, uint8_t value) {
            if (cell >= 0 && static_cast<size_t>(cell) < level_.tiles.size()) level_.tiles[cell] = value;
        };
        // Descending live slots. New chain-reaction records wait until next pass.
        for (size_t slot = flameRecords_.size(); slot > 0; --slot) {
            const size_t index = slot - 1;
            FlameRecord ray = flameRecords_[index];
            int vx = ray.vx, subX = ray.subX, vy = ray.vy, subY = ray.subY;
            auto memory = damageLaneMemory({&vx, &subX, &vy, &subY});
            int delta = 0;
            auto integrate = [&](int velocity, int& fraction, int step) {
                int sum = fraction + velocity;
                if (sum > 127 || sum < -128) {
                    sum += sum > 127 ? -128 : 128;
                    delta += velocity < 0 ? -step : step;
                }
                fraction = sum;
            };
            integrate(vx, subX, 1);
            integrate(vy, subY, level_.width);
            if (delta != 0) {
                const int target = static_cast<uint16_t>(ray.cell + delta);
                const uint8_t code = object(target);
                uint16_t word = wordAt(target % level_.width, target / level_.width);
                if (code == 0x66) {
                    // 1000:468E: consume the chain tile even when the pool is full.
                    stamp(target, word > 0x7fff ? 0xff : 0);
                    if (word <= 0x7fff && static_cast<size_t>(target) < level_.wordLayer.size()) {
                        level_.wordLayer[target] = 0;
                        word = 0;
                    }
                    seedFlameRecords(target, 1);
                    requestSoundOffset(explosionSoundOffset(1), explosionSoundSelector(1));
                }
                if (code == 0 || code == 0x75) {
                    if (object(ray.cell) == 0x75) stamp(ray.cell, 0);
                    stamp(target, ray.glyph);
                    ray.cell = static_cast<uint16_t>(target);
                    flameRecords_[index].cell = ray.cell;
                } else if (word != 0) {
                    uint8_t seededClass = 0;
                    if ((word & kDamagedWordBit) == 0) {
                        queueTileDamage(target % level_.width, target / level_.width, 0, 0, true, &seededClass);
                    }
                    const bool flagged = (word & kDamagedWordBit) != 0;
                    const bool debris = flagged ? (word & 0x7fff) >= kDeferredThreshold : seededClass != 0;
                    if (flagged || tileSeederResult_ != 0) {
                        uint8_t incomingX = 0, incomingY = 0;
                        if (flagged) {
                            sound_.writeSharedCursor(word);
                            lezac::gameplay::lookupDamageLaneBytes(memory, false);
                            incomingX = memory.read(0x661e);
                            sound_.writeSharedCursor(word);
                            lezac::gameplay::lookupDamageLaneBytes(memory, true);
                            incomingY = memory.read(0x661e);
                        } else sound_.writeSharedCursor(static_cast<uint16_t>(debris ?
                            kDebrisRecordIndexBase + debrisQueue_.size() : collapseQueue_.size()));
                        const uint16_t cursor = sound_.requestCursor();
                        const uint8_t weight = debris ? 1 : memory.read(static_cast<uint16_t>(0x661f + 15u * cursor));
                        if (flagged && debris && flameRecords_[index].variant > 0) stamp(target, 0xff);
                        const uint8_t mass = memory.read(static_cast<uint16_t>(0x78d5 + slot));
                        const auto x = lezac::gameplay::blendFlameVelocity(vx,
                            lezac::gameplay::damageLaneSignedByte(incomingX), mass, weight);
                        const auto y = lezac::gameplay::blendFlameVelocity(vy,
                            lezac::gameplay::damageLaneSignedByte(incomingY), mass, weight);
                        // Unlike 3BB2/3D46, the flame caller does not add 4E20.
                        const uint16_t address = static_cast<uint16_t>(debris ?
                            0x2097 + 11u * cursor : 0x6617 + 15u * cursor);
                        memory.write(address, static_cast<uint8_t>(x));
                        memory.write(static_cast<uint16_t>(address + 1), static_cast<uint8_t>(y));
                    }
                }
            }
            auto& current = flameRecords_[index];
            current.vx = static_cast<int8_t>(vx);
            current.vy = static_cast<int8_t>(vy);
            current.subX = static_cast<int8_t>(subX);
            current.subY = static_cast<int8_t>(subY);
            if (current.variant > 0) --current.variant;
            --current.timer;
            if (current.timer == 0) {
                if (object(current.cell) == 0x75) stamp(current.cell, 0);
                flameRecords_.erase(flameRecords_.begin() + static_cast<std::ptrdiff_t>(index));
            }
        }
    }

bool GameplayOperations::isBombObjectTile(uint8_t tile) const {
        return tile > 0x66 && tile < 0x73;
    }

bool GameplayOperations::isHighBombObjectSoundTile(uint8_t tile) const {
        return tile > kBombObjectHighSoundThreshold;
    }

bool GameplayOperations::isPassableObjectTile(uint8_t tile) const {
        return tile == 0x45 || isBombObjectTile(tile);
    }

bool GameplayOperations::isPassableObjectCell(int tx, int ty) const {
        uint8_t tile = static_cast<uint8_t>(tileAt(tx, ty));
        if (isPassableObjectTile(tile)) return true;
        return countsForPhysicalDamageProgress(wordAt(tx, ty));
    }

bool GameplayOperations::requestBombObjectScoreSound(bool sawHighObjectTile) {
        return requestSoundCursor(sawHighObjectTile ? kBombObjectHighSoundCursor
                                                    : kBombObjectDefaultSoundCursor,
                                  kBombObjectSoundPriority);
    }

bool GameplayOperations::requestBombPlaceSound() {
        return requestSoundOffset(kBombPlaceSoundCursor, kBombPlaceSoundPriority);
    }

bool GameplayOperations::requestMonsterDeathSound() {
        return requestSoundCursor(kMonsterDeathSoundCursor, kMonsterDeathSoundPriority);
    }

bool GameplayOperations::requestRecordNamePromptSound() {
        return requestSoundCursor(kRecordNamePromptSoundCursor,
                                  kRecordNamePromptSoundPriority);
    }

bool GameplayOperations::requestRecordNameCommitSound() {
        return requestSoundCursor(kRecordNameCommitSoundCursor,
                                  kRecordNameCommitSoundPriority);
    }

bool GameplayOperations::requestRecordsPageSound() {
        return requestSoundCursor(kRecordsPageSoundCursor, kRecordsPageSoundPriority);
    }

bool GameplayOperations::requestWeaponSwitchSound() {
        return requestSoundCursor(kWeaponSwitchSoundCursor, kWeaponSwitchSoundPriority);
    }

bool GameplayOperations::requestLaunchPadSound() {
        return requestSoundCursor(kLaunchPadSoundCursor, kLaunchPadSoundPriority);
    }

bool GameplayOperations::requestPortalTeleportSound() {
        return requestSoundCursor(kPortalTeleportSoundCursor, kPortalTeleportSoundPriority);
    }

bool GameplayOperations::requestTileTriggerSound() {
        return requestSoundCursor(kTileTriggerSoundCursor, kTileTriggerSoundPriority);
    }

bool GameplayOperations::requestPlayerDamageSound() {
        return requestSoundCursor(kPlayerDamageSoundCursor, kPlayerDamageSoundPriority);
    }

bool GameplayOperations::requestPlayerDeathSound() {
        return requestSoundCursor(kPlayerDeathSoundCursor, kPlayerDeathSoundPriority);
    }

bool GameplayOperations::consumeBombObjectTile(int tx, int ty) {
        if (tx < 0 || ty < 0 || tx >= level_.width || ty >= level_.height) return false;
        uint8_t& tile = tileRef(tx, ty);
        if (!isBombObjectTile(tile)) return false;
        const bool flagged = (wordAt(tx, ty) & 0x8000u) != 0;
        tile = flagged ? 0xff : 0;
        if (!flagged) level_.wordLayer[static_cast<size_t>(ty) * level_.width + tx] = 0;
        return true;
    }

bool GameplayOperations::markDamagedTile(int tx, int ty) {
        if (tx < 0 || ty < 0 || tx >= level_.width || ty >= level_.height) return false;
        uint8_t& tile = tileRef(tx, ty);
        bool counted = countsForDestructionProgress(tile, level_.objectiveTile);
        if (tile != level_.objectiveTile) {
            tile = 1;
        }
        return counted;
    }

void GameplayOperations::queueTileDamage(int tx, int ty, uint8_t forwardPhase , uint8_t reversePhase ,
                         bool preserveCollapseGlyphs , uint8_t* seededClass ) {
        if (tx < 0 || ty < 0 || tx >= level_.width || ty >= level_.height) return;
        const size_t start = static_cast<size_t>(ty) * level_.width + tx;
        if (start >= level_.wordLayer.size()) return;
        queuePhysicalTileDamage(static_cast<uint16_t>(start), forwardPhase,
                                reversePhase, preserveCollapseGlyphs, seededClass);
    }

void GameplayOperations::queuePhysicalTileDamage(uint16_t cell, uint8_t forwardPhase , uint8_t reversePhase ,
                                 bool preserveCollapseGlyphs , uint8_t* seededClass ) {
        if (level_.width <= 0) return;
        const uint16_t start = static_cast<uint16_t>(static_cast<uint16_t>(cell * 2u) >> 1);
        const uint16_t word = mapPlaneMemory_.readWord(start, level_.tiles, level_.wordLayer);
        if (word == 0 || (word & kDamagedWordBit) != 0) return;
        if (seededClass) *seededClass = static_cast<uint8_t>(word >= kDeferredThreshold);

        if (word >= kDeferredThreshold) {
            // Debris branch 374C..37F4: flags the word (3770/3780), copies the
            // object byte into the record (37B8/37BE) but never writes the
            // object plane â€” the glyph stays put until the fragment's first
            // move (CONFIRMED by the L2 capture; the earlier markDamagedTile
            // call here was unfaithful). Cap check 3753: refuse once slot
            // index base + record count reaches 0x640.
            tileSeederResult_ = static_cast<uint8_t>(
                lezac::gameplay::seedFallingFragmentPhysical(debrisQueue_, cell, forwardPhase, reversePhase,
                    [&](size_t rawCell) {
                        return mapPlaneMemory_.readWord(static_cast<int>(rawCell), level_.tiles, level_.wordLayer);
                    },
                    [&](size_t rawCell) {
                        return mapPlaneMemory_.readObject(static_cast<int>(rawCell), level_.tiles, level_.wordLayer);
                    },
                    [&](size_t rawCell, uint16_t flaggedWord) {
                        mapPlaneMemory_.writeWord(static_cast<int>(rawCell), flaggedWord, level_.tiles, level_.wordLayer);
                    }));
            return;
        }

        tileSeederResult_ = 0;
        if (collapseQueue_.size() >= kCollapseCapacity) return;
        auto geometry = lezac::gameplay::seedCollapseWordGroupPhysical(level_.width, start,
            [&](uint16_t physicalCell) { return mapPlaneMemory_.readWord(physicalCell, level_.tiles, level_.wordLayer); },
            [&](uint16_t physicalCell, uint16_t flaggedWord) {
                mapPlaneMemory_.writeWord(physicalCell, flaggedWord, level_.tiles, level_.wordLayer);
            });
        for (size_t index : geometry.cells) {
            int x = static_cast<int>(index % static_cast<size_t>(level_.width));
            int y = static_cast<int>(index / static_cast<size_t>(level_.width));
            if (!preserveCollapseGlyphs) markDamagedTile(x, y);
        }
        if (!geometry.cells.empty() && collapseQueue_.size() < kCollapseCapacity) {
            CollapseRecord record;
            record.x = start % level_.width;
            record.y = start / level_.width;
            record.startOffsetBytes = geometry.firstOffsetBytes;
            record.endOffsetBytes = geometry.lastOffsetBytes;
            record.word = word;
            record.flaggedWord = static_cast<uint16_t>(word | kDamagedWordBit);
            record.forwardPhase = forwardPhase;
            record.reversePhase = reversePhase;
            int signedForward = static_cast<int>(static_cast<int8_t>(forwardPhase));
            int signedReverse = static_cast<int>(static_cast<int8_t>(reversePhase));
            record.argMagnitude = static_cast<uint16_t>(std::abs(signedForward) +
                                                        std::abs(signedReverse));
            record.affectedBytes = static_cast<uint8_t>((geometry.cells.size() * 2) & 0xff);
            record.count = static_cast<int>(geometry.cells.size());
            collapseQueue_.push_back(record);
            tileSeederResult_ = 1;
        }
    }

DamagePhaseLookup GameplayOperations::resolveDamagePhase(uint16_t flaggedWord, bool reverse) const {
        if ((flaggedWord & kDamagedWordBit) == 0) return {};
        uint16_t key = static_cast<uint16_t>(flaggedWord & ~kDamagedWordBit);
        if (key >= kDeferredThreshold) {
            for (size_t i = debrisQueue_.size(); i > 0; --i) {
                const DebrisRecord& record = debrisQueue_[i - 1];
                if (record.flaggedWord == flaggedWord) {
                    return {static_cast<int>(i),
                            static_cast<uint8_t>(reverse ? record.velocityY
                                                         : record.velocityX),
                            true};
                }
            }
            return {};
        }
        for (size_t i = collapseQueue_.size(); i > 0; --i) {
            const CollapseRecord& record = collapseQueue_[i - 1];
            if (record.flaggedWord == flaggedWord) {
                return {static_cast<int>(i),
                        reverse ? record.reversePhase : record.forwardPhase, false};
            }
        }
        return {};
    }

void GameplayOperations::writeContactWordGuardAlias(size_t index, uint16_t word) {
        if (index > 5) return;
        // DS:655E aliases the eleven bytes after the last admitted fragment.
        auto& guard = debrisQueue_.retainedSlot(kDebrisCapacity - kDebrisRecordIndexBase);
        switch (index) {
        case 0: guard.tileIndex = word; break;
        case 1: guard.flaggedWord = word; break;
        case 2:
            guard.velocityX = static_cast<int8_t>(word);
            guard.velocityY = static_cast<int8_t>(word >> 8);
            break;
        case 3:
            guard.subX = static_cast<int8_t>(word);
            guard.subY = static_cast<int8_t>(word >> 8);
            break;
        case 4:
            guard.restTicks = static_cast<uint8_t>(word);
            guard.lookup = static_cast<uint8_t>(word >> 8);
            break;
        case 5: guard.aux = static_cast<uint8_t>(word); break;
        }
    }

lezac::gameplay::DamageLaneMemory<lezac::sound::SoundEngine>
    GameplayOperations::damageLaneMemory(std::array<int*, 4> lanes ) {
        return lezac::gameplay::DamageLaneMemory(damageLaneData_, debrisQueue_, collapseQueue_,
            flameRecords_, sound_, tileSeederResult_, lanes);
    }

lezac::gameplay::DamageLaneSeed GameplayOperations::seedDamageLaneContact(uint16_t cell, uint8_t& seededClass) {
        queuePhysicalTileDamage(cell, 0, 0, true, &seededClass);
        if (tileSeederResult_ == 0) return lezac::gameplay::DamageLaneSeed::Failed;
        return seededClass ? lezac::gameplay::DamageLaneSeed::Debris : lezac::gameplay::DamageLaneSeed::Collapse;
    }

void GameplayOperations::blendDebrisImpactLane(int target, uint16_t word, int& vx, int& subX,
                               int& vy, int& subY, bool reverse) {
        writeContactWordGuardAlias(0, word);  // 1000:4C8C / 4C9F, before seeding
        auto memory = damageLaneMemory({&vx, &subX, &vy, &subY});
        lezac::gameplay::writeDamageLaneWord(memory, 0x2078, 1);
        lezac::gameplay::writeDamageLaneWord(memory, 0x659a, static_cast<uint16_t>(target * 2));
        uint8_t seededClass = 0;
        lezac::gameplay::blendDamageLaneBytes(memory, reverse ? 0x78d4 : 0x78d2, 1, reverse,
            [&](uint16_t cell) { return seedDamageLaneContact(cell, seededClass); });
    }

void GameplayOperations::explode(const Bomb& bomb) {
        spawnExplosionEffect(bomb);
        TransientActor fade;
        fade.x = bomb.pixelX;
        fade.y = bomb.pixelY;
        fade.kind = 0;
        fade.timer = 18;
        fade.fracX = bomb.fracX;
        fade.fracY = bomb.fracY;
        fade.spriteIndex = 68;
        fade.animation = ActorAnimation::initialize(69, 79, 2, 1);
        fade.actorOrder = bomb.actorOrder;
        fade.bossVisualOrder = bomb.bossVisualOrder;
        fade.animationBackup = conversionBackup(bomb.actorOrder);
        const auto descriptor = actorSpriteDescriptor(69);
        fade.hotspotY = static_cast<uint8_t>(16 - descriptor[1]);
        actorSlots_.enterBombFade(bomb.actorOrder, fade, descriptor);
        transientActors_.push_back(fade);
        if (debugBombExpiryObserver_) debugBombExpiryObserver_(bomb, "before_particles");
        spawnExpiryParticles(bomb.pixelX, bomb.pixelY, bombTypeIndex(bomb.type) + 2);
        if (debugBombExpiryObserver_) debugBombExpiryObserver_(bomb, "after_particles");
    }

int GameplayOperations::monsterDamageForBomb(BombType type) const {
        // UNEVIDENCED legacy diagnostic only (@unevidenced:bomb_direct_monster_damage).
        // Live explode() now seeds flame records and never calls this helper.
        return std::clamp(bombTypeIndex(type) + 1, 1, 4);
    }

void GameplayOperations::damageMonstersInExplosion(const std::vector<std::array<int, 2>>& tiles,
                                   BombType type) {
        int damage = monsterDamageForBomb(type);
        for (ActiveMonster& monster : monsters_) {
            if (!monster.alive) continue;
            // Boss actors are exempt from the generic shot-damage path in
            // the original (1000:7427); the head instead drains from live
            // flames each frame in updateBossHead.
            if (monster.behavior == 5 || monster.behavior == 6) continue;
            if (monsterOverlapsExplosionTiles(monster, tiles)) {
                damageMonster(monster, damage);
            }
        }
    }

bool GameplayOperations::monsterOverlapsExplosionTiles(const ActiveMonster& monster,
                                       const std::vector<std::array<int, 2>>& tiles) const {
        for (const auto& tile : tiles) {
            float x = static_cast<float>(tile[0] * kTileSize);
            float y = static_cast<float>(tile[1] * kTileSize);
            if (rectsOverlap(static_cast<float>(monster.x), static_cast<float>(monster.y),
                             14.0f, 16.0f, x, y, static_cast<float>(kTileSize),
                             static_cast<float>(kTileSize))) {
                return true;
            }
        }
        return false;
    }

bool GameplayOperations::rectsOverlap(float ax, float ay, float aw, float ah,
                      float bx, float by, float bw, float bh) const {
        return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
    }

void GameplayOperations::damageMonster(ActiveMonster& monster, int damage, bool updatedThisTick ) {
        if (monster.behavior == 2) return;
        // Boss actors are exempt from generic damage (original 1000:7427
        // applies shot damage to kinds 1..8 only).
        if (monster.behavior == 5 || monster.behavior == 6) return;
        // 1000:745B..74A6 changes the displayed sprite, not the animation
        // cursor. The byte rewind holds this impact until the next advance.
        monster.animFrame = static_cast<uint8_t>(monsterCorpseSprite(monster));
        monster.hotspotY = static_cast<uint8_t>(16 - sprites_.sprites.at(monster.animFrame).height);
        monster.animTick = static_cast<uint8_t>(monster.animDelay - 4);
        if (actorSlots_.find(monster.actorOrder)) {
            actorSlots_.applyMonsterImpact(monster.actorOrder, actorSpriteDescriptor(monster.animFrame + 1));
            const bool fatal = actorSlots_.applyMonsterDamage(monster.actorOrder,
                static_cast<int8_t>(-std::max(1, damage)));
            monster.hp = fatal ? 0 : actorSlots_.actor(monster.actorOrder)[36] + 1;
        } else {
            if (!legacyActorSeedsEnabled_) throw std::runtime_error("damaging unbound production monster");
            monster.hp = std::max(0, monster.hp - std::max(1, damage));
        }
        if (monster.hp == 0) {
            enterMonsterDeath(monster, updatedThisTick);
        }
    }

bool GameplayOperations::playerOverlapsAnyExplosionTile(const Player& player,
                                        const std::vector<std::array<int, 2>>& tiles) const {
        for (const auto& tile : tiles) {
            float x = static_cast<float>(tile[0] * kTileSize);
            float y = static_cast<float>(tile[1] * kTileSize);
            if (playerOverlaps(player, x, y, static_cast<float>(kTileSize),
                               static_cast<float>(kTileSize))) {
                return true;
            }
        }
        return false;
    }

void GameplayOperations::damagePlayersInExplosion(const std::vector<std::array<int, 2>>& tiles) {
        if (!playerDead_ && playerOverlapsAnyExplosionTile(player_, tiles)) {
            queuePlayerDamage(1);
        }
        if (playerCount_ > 1 && !player2Dead_ &&
            playerOverlapsAnyExplosionTile(player2_, tiles)) {
            queuePlayerDamage(2);
        }
    }

int GameplayOperations::monsterCorpseSprite(const ActiveMonster& monster) const {
        const size_t kind = monster.kind < kMonsterImpactSprites.size()
                                ? monster.kind
                                : 0;
        return kMonsterImpactSprites[kind][monster.vx8 > 0 ? 1 : 0];
    }

void GameplayOperations::enterMonsterDeath(ActiveMonster& monster, bool updatedThisTick ) {
        if (monster.behavior == 2) return;
        // Fatal conversion follows movement; the velocity and fractions survive.
        monster.corpseSprite = static_cast<uint8_t>(monsterCorpseSprite(monster));
        monster.behavior = 2;
        monster.kind = 0x0c;
        // Encode raw timer 25's odd-frame countdown as remaining updates.
        // External blast conversion precedes this tick's monster dispatch.
        monster.stateTimer = 50 - static_cast<int>((logicTick_ + 1) & 1u) + (updatedThisTick ? 0 : 1);
        monster.animMode = 0;
        monster.hotspotY = static_cast<uint8_t>(16 - sprites_.sprites.at(monster.corpseSprite).height);
        monster.deathRewardPending = true;
        if (actorSlots_.find(monster.actorOrder)) actorSlots_.enterMonsterCorpse(monster.actorOrder);
        else if (!legacyActorSeedsEnabled_) throw std::runtime_error("converting unbound production monster");
        releaseMonsterSlot(monster);
        // 1000:74BB..7517 makes no sound request; 5C9E belongs to the boss chain.
    }

void GameplayOperations::spawnBonusDrop(float x, float y, BonusType type) {
        if (sharedActorCount() >= 30) return;
        BonusDrop drop;
        drop.x = x;
        drop.y = y;
        drop.type = type;
        drop.hotspotY = static_cast<uint8_t>(16 - sprites_.sprites.at(bonusSpriteIndex(type)).height);
        drop.actorOrder = allocateActor({static_cast<uint8_t>(static_cast<uint8_t>(type) + 0x13), drop.timer, 2,
            static_cast<uint16_t>(bonusSpriteIndex(type) + 1), 0, 0, static_cast<int16_t>(x), static_cast<int16_t>(y)});
        if (!drop.actorOrder) throw std::runtime_error("reward allocation disagrees with capacity");
        bonusDrops_.push_back(drop);
    }

void GameplayOperations::finishMonsterDeathReward(ActiveMonster& monster) {
        // Exact original kind-0x0c expiry path, disassembled at file
        // 0x7ddd..0x7ec0 (Ghidra 1000:766d..7750) and confirmed by the live
        // level-1 trace. The transition first rolls Random(100); values below
        // 40 produce no reward, while the ascending DGROUP thresholds select
        // one of the seven bonus kinds for rolls 40..99.
        corpseRewardRoll_ = static_cast<uint8_t>(randomRangeValue(0, 100));
        const uint16_t rewardSound =
            static_cast<uint16_t>(0xea74 + randomRangeValue(0, 20));
        requestSoundCursor(rewardSound, 4);
        auto conversion = lezac::gameplay::convertCorpseReward(monster, corpseRewardRoll_,
            [this](uint8_t sprite) { return static_cast<uint8_t>(16 - actorSpriteDescriptor(sprite)[1]); });
        const uint16_t sprite = conversion.hasReward
            ? static_cast<uint8_t>(conversion.reward.type) + 62 : 69;
        actorSlots_.convertCorpse(monster.actorOrder, conversion, actorSpriteDescriptor(sprite));
        if (conversion.hasReward) bonusDrops_.push_back(conversion.reward);
        else {
            conversion.fade.animationBackup = conversionBackup(monster.actorOrder, monster.animationBackup);
            transientActors_.push_back(conversion.fade);
        }

        spawnExpiryParticles(monster.x, monster.y + monster.hotspotY);
    }

void GameplayOperations::spawnExpiryParticles(int x, int y, int count ) {
        // 1000:772A..777D draws both velocities even on allocation failure.
        // The dynamic actor-loop bound at 7ECB visits appended actors this frame.
        for (int effect = 0; effect < count; ++effect) {
            const int vx8 = static_cast<int>(randomRangeValue(0, 600)) - 300;
            const int vy8 = static_cast<int>(randomRangeValue(0, 600)) - 300;
            if (auto* actor = spawnTransientActor(x, y,
                    static_cast<int16_t>(vy8), 13, 0x0b, 15,
                    ActorAnimation::initialize(69, 79, 2, 2))) {
                actor->vx8 = static_cast<int16_t>(vx8);
                if (!orderedActorPass_) updateTransientActor(*actor);
            }
        }
    }

void GameplayOperations::updateBonusDrops(size_t initialDrops , uint64_t onlyOrder ) {
        adoptUnorderedActors();
        initialDrops = std::min(initialDrops, bonusDrops_.size());
        for (size_t i = 0; i < initialDrops && i < bonusDrops_.size(); ++i) {
            BonusDrop& drop = bonusDrops_[i];
            if (onlyOrder && drop.actorOrder != onlyOrder) continue;
            if (drop.collected) continue;
            const int collisionX = static_cast<int16_t>(drop.x);
            const int collisionY = static_cast<int16_t>(static_cast<int>(drop.y) - static_cast<int8_t>(drop.hotspotY));
            const std::array<bool, 2> touching{{
                !playerDead_ && actorTouchesPlayer(player_, collisionX, collisionY),
                playerCount_ > 1 && !player2Dead_ && actorTouchesPlayer(player2_, collisionX, collisionY)}};
            const auto step = lezac::gameplay::advanceBonusDrop(drop, conversionBackup(drop.actorOrder),
                logicTick_, touching, pendingBonuses_,
                [&](int& x, int& y, int16_t& vx, int16_t& vy, uint8_t& fracX, uint8_t& fracY) {
                    updateTimedActorMotion(x, y, vx, vy, fracX, fracY, scanActorEdges(x, y));
                }, [&] { return randomInclusive(1, 3); },
                [&](uint8_t sprite) { return static_cast<uint8_t>(16 - sprites_.sprites.at(sprite).height); });
            if (step.converted) {
                const auto descriptor = actorSpriteDescriptor(static_cast<uint16_t>(step.conversion.spriteIndex) + 1);
                actorSlots_.setSpriteDescriptor(drop.actorOrder, descriptor);
                actorSlots_.writeTransient(drop.actorOrder, step.conversion, false, {});
                transientActors_.push_back(step.conversion);
            } else {
                const auto descriptor = step.animationAdvanced ? actorSpriteDescriptor(drop.animation.current)
                                                               : lezac::gameplay::ActorSlots::Descriptor{};
                actorSlots_.writeReward(drop.actorOrder, drop, step.animationAdvanced, descriptor);
            }
        }
        bonusDrops_.erase(std::remove_if(bonusDrops_.begin(), bonusDrops_.end(),
                                         [](const BonusDrop& drop) { return drop.collected; }),
                          bonusDrops_.end());
    }

void GameplayOperations::applyPendingBonus(const Player& collector, int& energy,
                           BombInventory& inventory, uint8_t playerIndex) {
        auto& pending = pendingBonuses_.at(playerIndex - 1);
        if (!pending) return;
        const auto type = static_cast<BonusType>(pending - 1);
        pending = 0;
        applyBonus(type, collector, energy, inventory, playerIndex);
        requestSoundCursor(kBonusPickupSoundCursor, kBonusPickupSoundPriority);
    }

void GameplayOperations::applyBonus(BonusType type, const Player& argument1, int& energy,
                    BombInventory& inventory, uint8_t playerIndex ) {
        switch (type) {
            case BonusType::Present:
                addScore(playerIndex, 2000);
                break;
            case BonusType::FirstAid:
                energy = 100;
                writePlayerHealth(playerIndex, energy);
                addScore(playerIndex, 1000);
                break;
            case BonusType::HotDog:
                // 6E64 adds a BYTE before the unsigned cap at 6E6C.
                energy = static_cast<uint8_t>(energy + 33);
                writePlayerHealth(playerIndex, energy);
                if (energy > 100) {
                    energy = 100;
                    writePlayerHealth(playerIndex, energy);
                }
                addScore(playerIndex, 1500);
                break;
            case BonusType::JollyCloud:
                addScore(playerIndex, 2000);
                bonusRainTicks_ = lezac::gameplay::kJollyCloudRainTicks;
                break;
            case BonusType::YellowBombBox:
                addScore(playerIndex, 3000);
                grantNormalBombSet(inventory);
                break;
            case BonusType::GreenBombBox:
                addScore(playerIndex, 1000);
                grantSuperBombSet(inventory);
                break;
            case BonusType::BigDiamond:
                addScore(playerIndex, 5000);
                break;
        }
    }

void GameplayOperations::grantNormalBombSet(BombInventory& inventory) {
        inventory.counts[0] = 200;
        inventory.counts[1] = std::min(99, inventory.counts[1] + randomInclusive(1, 10));
        inventory.counts[2] = std::min(99, inventory.counts[2] + randomInclusive(1, 4));
        inventory.hudDirty = 1;
    }

void GameplayOperations::grantSuperBombSet(BombInventory& inventory) {
        inventory.counts[0] = 200;
        inventory.counts[1] = std::min(99, inventory.counts[1] + randomInclusive(1, 13));
        inventory.counts[2] = std::min(99, inventory.counts[2] + randomInclusive(2, 6));
        inventory.counts[3] = std::min(99, inventory.counts[3] + randomInclusive(1, 2));
        inventory.hudDirty = 1;
    }

void GameplayOperations::updateBonusRain() {
        lezac::core::TurboRandom random(randomSeed_);
        const auto cell = lezac::gameplay::advanceJollyCloudRain(
            bonusRainTicks_, level_, nextCollapseFragmentWord_, random);
        randomSeed_ = random.seed();
        if (cell) queueTileDamage(static_cast<int>(*cell % level_.width),
                                  static_cast<int>(*cell / level_.width));
    }

void GameplayOperations::updateDebrisRecords() {
        // Loop-2 emptiness gate (4934 cmp DS:207E,0xC8 / jb exit).
        if (debrisQueue_.empty()) return;
        const int width = level_.width;
        if (width <= 0 || level_.tiles.empty()) return;
        // Preserve segment wrapping and live word-plane aliases past the map.
        auto objectByteAt = [&](int index) -> uint8_t {
            return mapPlaneMemory_.readObject(index, level_.tiles, level_.wordLayer);
        };
        auto setObjectByte = [&](int index, uint8_t value) {
            mapPlaneMemory_.writeObject(index, value, level_.tiles, level_.wordLayer);
        };
        auto wordCellAt = [&](int index) -> uint16_t {
            return mapPlaneMemory_.readWord(index, level_.tiles, level_.wordLayer);
        };
        auto setWordCell = [&](int index, uint16_t value) {
            mapPlaneMemory_.writeWord(index, value, level_.tiles, level_.wordLayer);
        };

        // Ascending slot order with the bound re-read live every iteration
        // (4947 re-reads DS:207E): a record seeded mid-pass by a cascade IS
        // updated later in this same tick (CONFIRMED by the L2 capture,
        // frame 404). Removal (458D) shifts the survivors down and rewinds
        // the caller's counter, which a vector erase without ++i reproduces.
        for (size_t i = 0; i < debrisQueue_.size();) {
            // Slot number as the original counts it: [bp-2] starts at 0xC8.
            const int slot = static_cast<int>(kDebrisRecordIndexBase) + 1 +
                             static_cast<int>(i);
            // Lane load 4950..49A1 (DS:78D2/78D3/78D4/78D5).
            int pos = debrisQueue_[i].tileIndex;
            int vx = debrisQueue_[i].velocityX;
            int vy = debrisQueue_[i].velocityY;
            int subX = debrisQueue_[i].subX;
            int subY = debrisQueue_[i].subY;
            auto laneGlobals = damageLaneMemory({&vx, &subX, &vy, &subY});
            uint8_t code = debrisQueue_[i].lookup;
            const uint16_t fw = debrisQueue_[i].flaggedWord;

            // Fragile-word auto-shatter 49A4..49C8: raw words 0x7FBD..0x7FFF
            // shatter even without a landing when still carrying a non-shatter
            // glyph.
            if (fw > kDebrisFragileWordFloor && code <= 0x66) {
                code = kDebrisShatterFrame;
                debrisQueue_[i].lookup = code;
                requestSoundCursor(kDebrisAutoShatterSoundCursor,
                                   kDebrisAutoShatterSoundPriority);
            }

            // Shatter frame stepper 49CB..4A18: one frame per tick; reaching
            // 0x79 picks the terminal glyph (0x6B+Random(5) for fragile words,
            // else 0xFF which dissolves through the consume path below); the
            // object plane is restamped every tick while code >= 0x76.
            if (code >= kDebrisShatterFrame) {
                code = static_cast<uint8_t>(code + 1);
                if (code == kDebrisShatterLastStep) {
                    code = fw > kDebrisFragileWordFloor
                               ? static_cast<uint8_t>(kDebrisTerminalBase +
                                                      randomRangeValue(0, 5))
                               : kDebrisDissolveByte;
                }
                debrisQueue_[i].lookup = code;
                setObjectByte(pos, code);
            }

            // 0xFF consume 4A1B..4A75: the fragment dissolves (both planes
            // cleared) and the cell above is re-seeded through the seeder
            // (guard 4A5B is word > 0 only; the seeder rejects the rest).
            if (objectByteAt(pos) == kDebrisDissolveByte) {
                setObjectByte(pos, 0);   // 4A31
                setWordCell(pos, 0);     // 4A49
                debrisQueue_.erase(debrisQueue_.begin() +
                                   static_cast<std::ptrdiff_t>(i));  // 4A39 -> 458D
                const int above = pos - width;
                if (wordCellAt(above) > 0) {                        // 4A5B
                    queuePhysicalTileDamage(static_cast<uint16_t>(above));  // 4A72 -> 370E
                }
                continue;
            }

            // Integrator 3EDA (called at 4A81): per axis, a signed 8-bit
            // sub-accumulator gains v; on signed overflow it loses 0x80 and
            // the move delta gains one tile in v's direction. x axis first,
            // then y; both can step in the same tick (diagonal move).
            int delta = 0;
            auto integrateAxis = [&](int v, int& sub, int unitMagnitude) {
                const int unit = v < 0 ? -unitMagnitude : unitMagnitude;  // 3EE4/3F0B
                int sum = sub + v;                                        // 3EEB/3F11
                if (sum > 127) {          // 3EED/3F13 jno (signed overflow)
                    sum -= 128;           // 3EEF/3F15 sub 0x80
                    delta += unit;        // 3EF2/3F18
                } else if (sum < -128) {
                    sum += 128;
                    delta += unit;
                }
                sub = sum;
            };
            integrateAxis(vx, subX, 1);
            integrateAxis(vy, subY, width);
            bool resting = delta == 0;  // 4A84..4A8B

            // Support / gravity / friction / landing shatter 4A93..4B32,
            // keyed on the object byte directly below (4A9D).
            if (objectByteAt(pos + width) == 0) {
                // Unsupported: gravity +4 while vy < 0x7B signed (so the
                // attainable terminal value from a zero start is 0x7C), and
                // the rest counter resets every airborne tick (4AB3).
                if (vy < kDebrisGravityCompare) vy += kDebrisGravityStep;
                debrisQueue_[i].restTicks = 0;
            } else {
                if (!resting) {
                    // Horizontal friction 4AC0..4AE2, only on ticks whose
                    // integrator produced a step.
                    if (vx > 0) {
                        --vx;
                    } else if (vx < 0) {
                        ++vx;
                    }
                }
                // Landing shatter 4AE6..4B32. The dice is
                // (DS:78C2 + slot) mod 6 â€” a frame counter, not the RNG; the
                // ADD AX at 4AFD wraps before unsigned DIV 6 at 4B05. The
                // port's logicTick_ stands in for DS:78C2 (INFERRED @unevidenced:debris_shatter_dice_phase,
                // equivalence, phase not pinned against the original).
                if (vy > 0 && vy > kDebrisLandingShatterVyGate && code > 0x66 &&
                    static_cast<uint16_t>(logicTick_ + static_cast<uint32_t>(slot)) % 6u > 2u) {
                    setObjectByte(pos, kDebrisShatterFrame);  // 4B16
                    debrisQueue_[i].lookup = kDebrisShatterFrame;
                    code = kDebrisShatterFrame;
                    requestSoundCursor(kDebrisLandingShatterSoundCursor,
                                       kDebrisLandingShatterSoundPriority);
                }
            }

            // Move 4B35..4CB5.
            if (delta != 0) {
                const int dest = static_cast<uint16_t>(pos + delta);
                if (objectByteAt(dest) == 0) {
                    // Free move 4B61..4C1D: the fragment is materialized at
                    // the destination in BOTH planes and erased from the
                    // vacated cell â€” these stamps happen on every free move,
                    // not on rest.
                    debrisQueue_[i].restTicks = 0;  // 4B6E
                    setObjectByte(dest, code);      // 4B7E
                    setObjectByte(pos, 0);          // 4B89
                    setWordCell(dest, fw);          // 4B9B
                    setWordCell(pos, 0);            // 4BAB
                    debrisQueue_[i].tileIndex = dest;  // 4BB5
                    // Cascade 4BB9..4C19: a move that was not straight up
                    // re-seeds the cell above the vacated one when its word
                    // is live and unflagged (words 1..0x3FFF spawn a collapse
                    // record through the same seeder).
                    if (delta != -width) {
                        const int above = pos - width;
                        const uint16_t aboveWord = wordCellAt(above);
                        if (aboveWord > 0 &&
                            aboveWord < kDamagedWordBit) {  // 4BE4..4BF5
                            queuePhysicalTileDamage(static_cast<uint16_t>(above));  // 4C08
                            // Set even when the seeder is at capacity (no
                            // DS:79C8 check at 4C0B..4C19). queueTileDamage
                            // may reallocate the queue, so re-index.
                            debrisQueue_[i].aux |= 0x80;
                        }
                    }
                    pos = dest;
                } else {
                    // Blocked move 4C20..4CAC.
                    resting = true;  // 4C20
                    if (vy > 0) {
                        // Bounce 4C24..4C5F: exactly these two RNG draws in
                        // this order, then vy = 0.
                        vx = static_cast<int8_t>(
                            vx + static_cast<int>(randomRangeValue(0, 0x1e)) -
                            15);  // 4C2B/4C41, stored through AL
                        requestSoundOffset(
                            static_cast<uint16_t>(kDebrisBounceSoundBase +
                                                  randomRangeValue(0, 8)),
                            kDebrisBounceSoundPriority);  // 4C4A/4C51/4C57
                        vy = 0;                           // 4C5F
                    }
                    const uint16_t destWord = wordCellAt(dest);  // 4C64..4C75
                    if (destWord == 0) {
                        vx = 0;  // 4CAE
                    } else {
                        blendDebrisImpactLane(dest, destWord, vx, subX, vy, subY, false);  // 4C96
                        // X may have seeded the target. The original forces
                        // its flag for the Y matcher at 4C99 before 4CA9.
                        blendDebrisImpactLane(
                            dest, static_cast<uint16_t>(destWord | kDamagedWordBit),
                            vx, subX, vy, subY, true);
                    }
                }
            }

            // Lane write-back 4CB9..4CEB.
            debrisQueue_[i].velocityX = static_cast<int8_t>(vx);
            debrisQueue_[i].velocityY = static_cast<int8_t>(vy);
            debrisQueue_[i].subX = static_cast<int8_t>(subX);
            debrisQueue_[i].subY = static_cast<int8_t>(subY);

            // 4CF8 increments a byte; 4CFF tests equality with 100. Removal
            // clears only the map flag, leaves the glyph, and rewinds the
            // live loop so the shifted successor is processed this tick.
            // The original leaves stale tail bytes; they do not stay live.
            if (resting) ++debrisQueue_[i].restTicks;
            if (debrisQueue_[i].restTicks == kDebrisRestRetireTicks) {
                setWordCell(pos, static_cast<uint16_t>(wordCellAt(pos) & ~kDamagedWordBit));
                debrisQueue_.erase(debrisQueue_.begin() + static_cast<std::ptrdiff_t>(i));
                continue;
            }
            ++i;
        }
    }

void GameplayOperations::blendCollapseContacts(const std::vector<DamageContact>& contacts, int& velocity,
                               uint8_t ownWeight, bool reverse) {
        auto memory = damageLaneMemory();
        lezac::gameplay::writeDamageLaneWord(memory, 0x2078, static_cast<uint16_t>(contacts.size()));
        for (size_t index = 0; index < contacts.size(); ++index) {
            lezac::gameplay::writeDamageLaneWord(memory, static_cast<uint16_t>(0x655e + 2 * index), contacts[index].word);
            lezac::gameplay::writeDamageLaneWord(memory, static_cast<uint16_t>(0x659a + 2 * index),
                static_cast<uint16_t>(contacts[index].cell * 2));
        }
        // The collapse caller passes SS:BP-0B / SS:BP-0C, not a DS address.
        // The helper's SS seed-class local survives every contact in this call.
        uint8_t seededClass = 0;
        const auto phase = lezac::gameplay::blendDamageLaneValue(memory, static_cast<uint8_t>(velocity),
            ownWeight, reverse, [&](uint16_t cell) { return seedDamageLaneContact(cell, seededClass); });
        if (phase) velocity = lezac::gameplay::damageLaneSignedByte(*phase);
    }

void GameplayOperations::updateCollapseRecords() {
        if (level_.width <= 0 || level_.tiles.empty()) return;
        const int width = level_.width;
        struct Scan {
            bool blocked = false;
            int firstColumn = 10000;
            int lastColumn = 0;
            std::vector<DamageContact> contacts;
        };
        auto mapWord = [&](int cell) -> uint16_t {
            return mapPlaneMemory_.readWord(cell, level_.tiles, level_.wordLayer);
        };
        auto mapTile = [&](int cell) -> uint8_t {
            return mapPlaneMemory_.readObject(cell, level_.tiles, level_.wordLayer);
        };
        auto setMapWord = [&](int cell, uint16_t value) {
            mapPlaneMemory_.writeWord(cell, value, level_.tiles, level_.wordLayer);
        };
        auto setMapTile = [&](int cell, uint8_t value) {
            mapPlaneMemory_.writeObject(cell, value, level_.tiles, level_.wordLayer);
        };
        // 1000:5102 visits the records newest-first. Cascades appended during
        // this pass start moving on the following tick.
        for (size_t remaining = collapseQueue_.size(); remaining > 0; --remaining) {
            const size_t slot = remaining - 1;
            CollapseRecord record = collapseQueue_[slot];
            lezac::gameplay::CollapseRectangle rectangle(record.startOffsetBytes, record.endOffsetBytes,
                                                        static_cast<uint16_t>(width));
            const auto& first = rectangle.first;
            const auto& last = rectangle.last;
            int vx = static_cast<int8_t>(record.forwardPhase);
            int vy = static_cast<int8_t>(record.reversePhase);
            const int incomingX = vx, incomingY = vy;
            bool moved = false;
            auto cells = [&] {
                std::vector<int> result;
                rectangle.visit(0, [&](uint16_t cell) {
                    if (mapWord(cell) == record.flaggedWord) result.push_back(cell);
                });
                return result;
            };
            auto scan = [&](int delta, bool collectContacts = false) {
                Scan result;
                // 4D3C/4E48 own the scratch phase also read by damage helpers.
                damageLaneData_[0x661e] = 0;
                for (int cell : cells()) {
                    const uint16_t target = static_cast<uint16_t>(cell + delta);
                    const uint16_t word = mapWord(target);
                    if (mapTile(target) == 0 || word == record.flaggedWord) continue;
                    result.blocked = true;
                    damageLaneData_[0x661e] = 1;
                    result.firstColumn = std::min(result.firstColumn, target % width);
                    result.lastColumn = std::max(result.lastColumn, target % width);
                    if (collectContacts && word != 0 && std::none_of(result.contacts.begin(), result.contacts.end(),
                        [&](const DamageContact& contact) { return contact.word == word; })) {
                        writeContactWordGuardAlias(result.contacts.size(), word);  // 1000:4ECD
                        result.contacts.push_back({static_cast<uint16_t>(target * 2u) / 2, word});
                    }
                }
                return result;
            };
            auto seedAbove = [&] {
                for (const auto& contact : scan(-width, true).contacts) {
                    if (contact.word < kDamagedWordBit) {
                        queuePhysicalTileDamage(contact.cell, 0, 1, true);
                    }
                }
            };
            auto move = [&](int delta) {
                Scan result = scan(delta, true);
                moved = false;
                if (result.blocked) return result;
                rectangle.visit(delta, [&](uint16_t cell) {
                    const uint16_t word = mapWord(cell);
                    if (word != record.flaggedWord) return;
                    const uint16_t target = static_cast<uint16_t>(cell + delta);
                    setMapWord(target, word);
                    setMapWord(cell, 0);
                    const uint8_t tile = mapTile(cell);
                    setMapTile(cell, 0);  // 4F9D exchanges the source before the destination write.
                    setMapTile(target, tile);
                });
                rectangle.translate(delta);
                moved = true;
                return result;
            };
            auto blend = [&](const Scan& result, int& velocity, bool reverse) {
                blendCollapseContacts(result.contacts, velocity, record.affectedBytes, reverse);
            };
            auto integrate = [](int velocity, int8_t& fraction) {
                int sum = fraction + velocity;
                const bool overflow = sum > 127 || sum < -128;
                if (sum > 127) sum -= 128;
                else if (sum < -128) sum += 128;
                fraction = static_cast<int8_t>(sum);
                return overflow ? (velocity < 0 ? -1 : 1) : 0;
            };
            const int dx = integrate(vx, record.subX);
            if (dx != 0) {
                if ((record.flags & 0x80) == 0) seedAbove();
                else record.flags &= 0x7f;
                const auto result = move(dx);
                if (!result.contacts.empty()) blend(result, vx, false);
            }
            const int dy = integrate(vy, record.subY);
            if (dy != 0) {
                if (dy > 0 && (record.flags & 0x80) == 0) {
                    record.flags |= 0x80;
                    seedAbove();
                } else if (dy < 0) record.flags &= 0x7f;
                const auto result = move(dy * width);
                if (result.blocked && vy > 0) {
                    vy = 0;
                    cameraShakeTicks_ = 3;  // 1000:5388
                    requestSoundOffset(static_cast<uint16_t>(kDebrisBounceSoundBase + randomRangeValue(0, 8)), 1);
                }
                if (!result.contacts.empty()) blend(result, vy, true);
            }
            const auto support = scan(width);
            if (!support.blocked) {
                if (vy < 123) vy += 4;
                moved = true;
                record.flags &= 0xfc;
            } else {
                const int left = first % width, right = rectangle.topRight % width;
                const int halfWidth = static_cast<uint16_t>(right - left) >> 1;
                const int centerLeft = static_cast<uint16_t>(left + halfWidth);
                const int centerRight = static_cast<uint16_t>(right - halfWidth);
                if (std::abs(vy) < 10 && std::abs(vx) < 30) {
                    if (support.firstColumn > centerLeft && (record.flags & 2) == 0) {
                        if (!scan(-1).blocked) { vx = -15; record.flags |= 1; }
                        else record.flags &= 0xfc;
                    } else if (support.lastColumn < centerRight && (record.flags & 1) == 0) {
                        if (!scan(1).blocked) { vx = 15; record.flags |= 2; }
                        else record.flags &= 0xfc;
                    }
                    if (support.firstColumn <= centerLeft && support.lastColumn >= centerRight) record.flags &= 0xfc;
                }
                if (vx > 0) --vx;
                else if (vx < 0) ++vx;
            }
            if (moved) record.restTicks = 0;
            ++record.restTicks;
            // The original commits these bytes before fracture, but not the motion fields.
            collapseQueue_[slot].flags = record.flags;
            collapseQueue_[slot].restTicks = record.restTicks;
            const int magnitude = std::abs(vx) + std::abs(vy);
            sound_.writeSharedCursor(static_cast<uint16_t>(magnitude));  // 1000:555A
            const auto magnitudeDelta = lezac::gameplay::collapseMagnitudeDelta(
                record.argMagnitude, static_cast<uint16_t>(magnitude));
            actorSlots_.setSharedResult(magnitudeDelta);  // 1000:556E
            const bool fracture = magnitudeDelta > 63;
            if (fracture) {
                requestSoundOffset(0xea74, 3);
                for (int cell : cells()) {
                    setMapWord(cell, nextCollapseFragmentWord_++);
                    setMapTile(cell, static_cast<uint8_t>(0x47 + (logicTick_ & 2)));
                    ++destroyed_;
                    sound_.writeSharedCursor(static_cast<uint16_t>(cell));  // 1000:501F
                    const auto x = static_cast<uint8_t>(incomingX + randomRangeValue(0, 20) - 10);
                    const auto y = static_cast<uint8_t>(incomingY - randomRangeValue(0, 40));
                    queuePhysicalTileDamage(static_cast<uint16_t>(cell), x, y, true);
                }
                // 1000:558C selects a cell backward from the bottom-right.
                const uint16_t actorCell = lezac::gameplay::collapseActorCell(
                    static_cast<uint16_t>(last * 2u), randomRangeValue(0, rectangle.columns()));
                spawnTransientActor((actorCell % width) * 8, (actorCell / width) * 8,
                                    0, 74, 0x0b, 8, ActorAnimation::initialize(74, 79, 2, 1));
            }
            if (!fracture) {
                // 1000:5602..5651 commits normal motion before the timer-95 removal.
                record.startOffsetBytes = static_cast<uint16_t>(first * 2);
                record.endOffsetBytes = static_cast<uint16_t>(last * 2);
                record.x = first % width;
                record.y = first / width;
                record.forwardPhase = static_cast<uint8_t>(vx);
                record.reversePhase = static_cast<uint8_t>(vy);
                record.argMagnitude = static_cast<uint16_t>(magnitude);
                collapseQueue_[slot] = record;
            }
            if (fracture || record.restTicks == 95) {
                collapseQueue_.erase(collapseQueue_.begin() + static_cast<std::ptrdiff_t>(slot));
                // Fracture leaves top-right in cells; timer retirement doubles it at 5660.
                lezac::gameplay::visitCollapseRemovalWords(static_cast<uint16_t>(first * 2u),
                    fracture ? rectangle.topRight : static_cast<uint16_t>(rectangle.topRight * 2u),
                    static_cast<uint16_t>(last * 2u), static_cast<uint16_t>(width), [&](uint16_t cell) {
                        const uint16_t word = mapWord(cell);
                        if (word == record.flaggedWord) {
                            setMapWord(cell, static_cast<uint16_t>(word & ~kDamagedWordBit));
                        }
                    });
                continue;
            }
        }
    }

void GameplayOperations::updateFlashes() {
        for (Flash& f : flashes_) --f.timer;
        flashes_.erase(std::remove_if(flashes_.begin(), flashes_.end(),
                                      [](const Flash& f) { return f.timer <= 0; }),
                       flashes_.end());
        for (ExplosionEffect& e : explosionEffects_) --e.timer;
        explosionEffects_.erase(std::remove_if(explosionEffects_.begin(), explosionEffects_.end(),
                                               [](const ExplosionEffect& e) { return e.timer <= 0; }),
                                explosionEffects_.end());
        updateFlameRecords();
        updateDebrisRecords();
        updateCollapseRecords();
    }

int GameplayOperations::destructionPercent() const {
        if (level_.startingDestructibleTiles == 0) return 100;
        return std::min(100, destroyed_ * 100 / level_.startingDestructibleTiles);
    }

bool GameplayOperations::isComplete() const {
        return collected_ >= level_.requiredBonus &&
               destructionPercent() >= static_cast<int>(level_.requiredDestruction);
    }

void GameplayOperations::adjustGameplayViewWidth(int delta) {
        if (!viewportLayout_.adjustWidth(remainingPlayerCount(), delta)) return;
        gameplayViewWidth_ = viewportLayout_.pitch;
        actorSlots_.setSavedViewportColumns(static_cast<uint16_t>(gameplayViewWidth_ / 8));
        writeViewportDestinations();
        gameRenderer_.resizePlayfield(gameplayViewWidth_);
    }

int GameplayOperations::remainingPlayerCount() const {
        return static_cast<int>(lives_ >= 0) + static_cast<int>(playerCount_ > 1 && lives2_ >= 0);
    }

void GameplayOperations::writeViewportDestinations() {
        const int remaining = remainingPlayerCount();
        if (remaining != 1 && remaining != 2) return;
        for (size_t index = 0; index < 2; ++index)
            actorSlots_.setViewportDestination(index, static_cast<uint16_t>(1284 + viewportLayout_.left[index]));
    }

void GameplayOperations::initializeGameplayView() {
        const int remaining = remainingPlayerCount();
        viewportLayout_ = lezac::rendering::ViewportLayout::initialize(remaining, gameplayViewWidth_);
        gameRenderer_.initializePlayfield(remaining, gameplayViewWidth_);
        playfieldConfiguredCount_ = playerCount_;
    }

void GameplayOperations::buildBackdropBuffer() {
        if (playfieldConfiguredCount_ != playerCount_) initializeGameplayView();
        lezac::core::TurboRandom random(randomSeed_);
        presentation_.buildBackdropBufferForPitch(viewportLayout_.pitch, random);
        randomSeed_ = random.seed();
    }

std::vector<SharedActorEntry> GameplayOperations::prepareRenderState() {
        if (playfieldConfiguredCount_ != playerCount_) initializeGameplayView();
        adoptUnorderedActors();
        auto order = sharedActorEntries();
        // Actor update order and the original boss visual-block order differ.
        std::stable_sort(order.begin(), order.end(), [&](const auto& a, const auto& b) {
            return sharedActorVisualKey(a) < sharedActorVisualKey(b);
        });
        return order;
    }

lezac::rendering::WorldRenderView GameplayOperations::worldRenderView(const std::vector<SharedActorEntry>& order) const {
        return {level_, levelIndex_, playerCount_,
                {{{player_, playerDead_, lives_, state2Visual_, state2Effect_, originalPlayerState(1)},
                  {player2_, player2Dead_, lives2_, state2Visual2_, state2Effect2_, originalPlayerState(2)}}},
                bombs_, monsters_, bonusDrops_, flashes_, launchPadMarkers_, transientActors_, order,
                gameplayViewWidth_, ui_.snapshot().showBackground, cameraShakeOffset_,
                state2VisualCursorPreview_, state2VisualRowPreview_, &viewportLayout_, &mapPlaneMemory_,
                legacyActorSeedsEnabled_ ? nullptr : &actorSlots_.state(), legacyActorSeedsEnabled_};
    }

lezac::rendering::HudView GameplayOperations::hudView() const {
        return {playerCount_,
                {{{presentation_.hudEnergy()[0], score_, lives_, presentation_.hudAmmoPanels()[0]},
                  {presentation_.hudEnergy()[1], score2_, lives2_, presentation_.hudAmmoPanels()[1]}}},
                level_.objectiveTile, level_.requiredBonus, level_.requiredDestruction,
                collected_, presentation_.hudDestructionPercent(),
                levelFlow_.interactiveEnabled() ? levelFlow_.outro().active : isComplete(), levelFlow_.outro().active,
                presentation_.hudScores(), presentation_.hudColumnReady(), damageLaneData_[kLaneHelperNeighborLaneScratch]};
    }

lezac::rendering::MenuView GameplayOperations::menuRenderView() const {
        const auto progress = ui_.mainMenuProgress(presentationMilliseconds());
        return {ui_.snapshot().page, ui_.snapshot().italian, recordStore_.records(), recordStore_.pending().player, recordStore_.pending().score,
                recordStore_.pending().level, recordStore_.pending().name, playerCount_, {{score_, score2_}}, progress.fade, progress.steps, endScreenPattern_};
    }

GameplayOperations::GameplayOperations(GameplayServices services)
    : services_(std::move(services)), assets_(services_.assets),
      sprites_(assets_.sprites()),
      altSprites_(assets_.altSprites()),
      gran_(assets_.gran()),
      levels_(assets_.levels()),
      sound_(services_.sound),
      audioOutput_(services_.audio),
      presentation_(services_.presentation),
      ui_(services_.ui),
      recordStore_(services_.records),
      levelFlow_(services_.flow),
      endScreenPattern_(services_.endPattern),
      canvas_(services_.canvas),
      gameRenderer_(services_.renderer),
      viewportLayout_(services_.viewport),
      gameplayViewWidth_(services_.viewWidth),
      playfieldConfiguredCount_(services_.configuredPlayers),
      gameplayPresentation_(services_.present),
      gameplayPalettePresentation_(services_.presentPalette),
      debugResultReelObserver_(services_.resultReelObserver),
      debugResultTypingObserver_(services_.resultTypingObserver),
      debugActorPassObserver_(services_.actorPassObserver),
      debugBombExpiryObserver_(services_.bombExpiryObserver),
      debugMonsterAnimationObserver_(services_.animationObserver),
      debugDeathGateObserver_(services_.deathGateObserver),
      debugPlayerHealthWriteObserver_(services_.healthWriteObserver),
      debugReentryBoundaryObserver_(services_.reentryObserver) {}
}
