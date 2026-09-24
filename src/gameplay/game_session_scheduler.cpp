#include "gameplay/game_session.hpp"
#include "gameplay/motion_math.hpp"
#include "core/progress.hpp"
#include <cmath>

namespace lezac::gameplay {
using namespace lezac::core;
using detail::clampI16;
using detail::integrateAxis8_8;

void GameSession::resetLevel(int index) {
        if (hooks_.beforeReset) hooks_.beforeReset();
        ++levelResetGeneration_;
        levelIndex_ = (index + static_cast<int>(levels_.size())) % static_cast<int>(levels_.size());
        level_ = levels_[levelIndex_];
        if (hooks_.mapSizeChanged) hooks_.mapSizeChanged(static_cast<size_t>(level_.width) * level_.height);
        player_ = {};
        player2_ = {};
        player2_.animation = ActorAnimation::initialize(21, 28, 1, 1);
        spawnerStates_.clear();
        monsters_.clear();
        bonusDrops_.clear();
        bombs_.clear();
        flashes_.clear();
        launchPadMarkers_.clear();
        transientActors_.clear();
        cameraShakeTicks_ = cameraShakeOffset_ = 0;
        nextActorOrder_ = 1;
        explosionEffects_.clear();
        flameRecords_.clear();
        debrisQueue_.clear();
        collapseQueue_.clear();

        nextCollapseFragmentWord_ = level_.fieldA;
        collected_ = 0;
        destroyed_ = 0;
        if (hooks_.resetHud) hooks_.resetHud();
        completeTimer_ = 0;
        portalCooldown_ = 0;
        triggerCooldown_ = 0;
        portalCooldown2_ = 0;
        triggerCooldown2_ = 0;
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
        for (const MonsterSpawner& spawner : level_.monsterSpawners) {
            SpawnerState state;
            state.remaining = spawner.enabled ? spawner.spawnBudget : 0;
            state.availableSlots = spawner.liveAllowance;
            state.cooldown = spawner.cooldown;
            spawnerStates_.push_back(state);
        }
        if (const LevelPortal* start = findStartPortal(1)) {
            player_.x = static_cast<float>(start->x);
            player_.y = static_cast<float>(start->y);
        }
        if (const LevelPortal* start = findStartPortal(2)) {
            player2_.x = static_cast<float>(start->x);
            player2_.y = static_cast<float>(start->y);
        } else {
            player2_.x = std::min(player_.x + 16.0f, std::max(16.0f, level_.width * 8.0f - 16.0f));
            player2_.y = player_.y;
        }
        if (playerCount_ > 1) {
            playerDead_ = lives_ < 0;
            player2Dead_ = lives2_ < 0;
        }
        bossLinks_.clear();
        bossPresent_ = false;
        bossDefeated_ = false;
        // The original loads gran.mst at the end of level setup only when the
        // current-level byte DS:0x79B7 equals 7 (callsite 1000:2E78).
        if (levelIndex_ == 6) spawnLevel7Boss();
    }

void GameSession::tryActivePlayerFireAt(const Player& player, int x, int y, uint8_t playerIndex) {
        if (!(playerIndex == 2 ? reentryFire2_ : reentryFire1_)) return;
        Player launch = player;
        launch.x = static_cast<float>(x);
        launch.y = static_cast<float>(y);
        placeBombAt(launch, playerIndex == 2 ? bombInventory2_ : bombInventory_, playerIndex);
    }

bool GameSession::playerOverlaps(const Player& player, float x, float y, float w, float h) const {
        return player.x < x + w && player.x + 12.0f > x &&
               player.y < y + h && player.y + 16.0f > y;
    }

int GameSession::bombTypeIndex(BombType type) const {
        return static_cast<int>(type);
    }

int GameSession::explosionVisualType(BombType type) const {
        return std::clamp(bombTypeIndex(type) + 1, 1, 4);
    }

bool GameSession::hasBomb(const BombInventory& inventory, BombType type) const {
        return inventory.counts[static_cast<size_t>(bombTypeIndex(type))] > 0;
    }

void GameSession::selectNextAvailableBomb(BombInventory& inventory) {
        int start = bombTypeIndex(inventory.selected);
        for (int step = 1; step <= 4; ++step) {
            int idx = (start + step) % 4;
            if (inventory.counts[static_cast<size_t>(idx)] > 0) {
                inventory.selected = static_cast<BombType>(idx);
                return;
            }
        }
    }

void GameSession::updateWeaponSwitch(BombInventory& inventory, uint8_t& holdTicks, bool pressed) {
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

void GameSession::updatePlayerReentryPrepass(const FrameControls& controls) {
        // State-2 countdown precedes both actor passes (1000:7C89).
        // 1000:7E9D/7EA2 clear BOTH latches on the first successful reentry.
        if (!reentryGate_) noActivePlayerTicks_ = kSharedReentryTicks - 1;
        reentryFire1_ = reentryFire1_ || controls.p1Reenter;
        reentryFire2_ = reentryFire2_ || controls.p2Reenter;
        if (playerDead_) {
            updateReentry(player_, energy_, lives_, playerDead_, reentryTimer_, 1,
                          playerCount_ == 1 || player2Dead_);
            if (reentryFire1_) tryReenterPlayer(player_, energy_, lives_, playerDead_, reentryTimer_, damageCooldown_, 1);
        }
        if (playerCount_ > 1 && player2Dead_) {
            updateReentry(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_, 2,
                          playerDead_);
            if (reentryFire2_) tryReenterPlayer(player2_, energy2_, lives2_, player2Dead_, reentryTimer2_, damageCooldown2_, 2);
        }
    }

void GameSession::updateWithControls(const FrameControls& controls, float dt) {
        if (hooks_.tickBlocked && hooks_.tickBlocked()) return;
        ++logicTick_;
        if (hooks_.prepareHudObjectives) hooks_.prepareHudObjectives(view());
        if (hooks_.presentGameplay) hooks_.presentGameplay();
        // 1000:7A6B precedes state-2 and both actor passes. An effect that
        // expires later this frame still occupies its slot during spawning.
        updateMonsterSpawners();
        updatePlayerReentryPrepass(controls);
        if (hooks_.reentryBlocked && hooks_.reentryBlocked()) return;
        // 1000:7ECB..7EE8 precedes the player calls at 7F59. New pickup
        // and collapse-fracture actors therefore start on the next frame.
        updateDamageCooldowns();
        bool p1Switch = controls.p1Left && controls.p1Right;
        bool p2Switch = controls.p2Left && controls.p2Right;
        bool p1Jump = controls.p1Jump && !controls.p1Down;
        bool p1Down = controls.p1Down && !controls.p1Jump;
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
        updateOrderedActors(dt);
        applyAfterActorPassActions();
        if (hooks_.actorPassObserver) hooks_.actorPassObserver(view());
        if (updateSharedReentryFallback()) return;

        if (playerDead_) {
            if (deathStateTimer_ > 0) {
                if (updateState2VisualCursor(state2Visual_)) {
                    player_.spriteIndex = state2Visual_.current - 1;
                    player_.singlePixelSprite = false;
                }
                updateDyingPlayerMotion(player_);
            }
            refreshState2EffectEntry(player_, state2Visual_, state2Effect_);
        } else {
            collectObjectiveTiles(player_, 1);
            updatePlayer(player_, controls.p1Left, controls.p1Right, p1Jump, p1Switch, 0, p1Down);
            updatePortalsAndTriggers(player_, portalCooldown_, triggerCooldown_, p1Down);
        }
        if (playerCount_ > 1) {
            if (player2Dead_) {
                if (deathStateTimer2_ > 0) {
                    if (updateState2VisualCursor(state2Visual2_)) {
                        player2_.spriteIndex = state2Visual2_.current - 1;
                        player2_.singlePixelSprite = false;
                    }
                    updateDyingPlayerMotion(player2_);
                }
                refreshState2EffectEntry(player2_, state2Visual2_, state2Effect2_);
            } else {
                collectObjectiveTiles(player2_, 2);
                updatePlayer(player2_, controls.p2Left, controls.p2Right, p2Jump, p2Switch, 19, p2Down);
                updatePortalsAndTriggers(player2_, portalCooldown2_, triggerCooldown2_,
                                         p2Down);
            }
        }
        drainPlayerDamageCounters();
        if (hooks_.updateHudScores) hooks_.updateHudScores(view());
        updateFlashes();
        updateCameraShake();
        if (hooks_.advanceHudPalette) hooks_.advanceHudPalette();
        if (hooks_.updateRedPalette) hooks_.updateRedPalette(static_cast<uint16_t>(logicTick_));
        if (hooks_.levelCompletion) hooks_.levelCompletion();
        if (hooks_.pumpSound) hooks_.pumpSound();
    }

void GameSession::updateOrderedActors(float dt) {
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
                    if (!transientActors_[entry.index].timer) transientActors_.erase(transientActors_.begin() + static_cast<std::ptrdiff_t>(entry.index));
                    break;
                }
                case SharedActorKind::Marker: updateLaunchPadMarkers(entry.order); break;
                case SharedActorKind::Bomb: updateBombs(entry.order); break;
                case SharedActorKind::Monster: updateMonsters(dt, entry.order); break;
                case SharedActorKind::Reward: updateBonusDrops(std::numeric_limits<size_t>::max(), entry.order); break;
            }
        }
    }

TransientActor* GameSession::spawnTransientActor(int x, int y, int16_t vy8, uint8_t sprite, uint8_t kind, uint8_t timer, ActorAnimation animation) {
        // 1000:2F9F has one 30-slot pool for non-player actors.
        if (sharedActorCount() >= 30) return nullptr;
        TransientActor actor;
        actor.x = x;
        actor.y = y;
        actor.vy8 = vy8;
        actor.kind = kind;
        actor.timer = timer;
        actor.spriteIndex = static_cast<uint8_t>(sprite - 1);
        actor.hotspotY = static_cast<uint8_t>(16 - sprites_.sprites.at(actor.spriteIndex).height);
        actor.animation = animation;
        actor.actorOrder = claimActorOrder();
        transientActors_.push_back(actor);
        return &transientActors_.back();
    }

void GameSession::updateTransientActor(TransientActor& actor) {
        if (actor.animation.advance(ActorAnimation{})) {
            actor.spriteIndex = static_cast<uint8_t>(actor.animation.current - 1);
        }
        // 1000:65A2..65D7 bypasses collision/gravity and deletes before
        // integration when the byte reaches zero, not on animation wrap.
        actor.timer = static_cast<uint8_t>(actor.timer - (logicTick_ & 1u));
        if (actor.timer == 0) return;
        integrateAxis8_8(actor.y, actor.fracY, actor.vy8);
        integrateAxis8_8(actor.x, actor.fracX, actor.vx8);
    }

void GameSession::updateTransientActors() {
        for (auto& actor : transientActors_) updateTransientActor(actor);
        transientActors_.erase(std::remove_if(transientActors_.begin(), transientActors_.end(),
            [](const TransientActor& actor) { return actor.timer == 0; }), transientActors_.end());
    }

void GameSession::collectObjectiveTiles(const Player& player, uint8_t playerIndex) {
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
                spawnTransientActor(static_cast<int>(player.x) + (x == x0 ? -2 : 10),
                    static_cast<int>(player.y) + (y == y0 ? -2 : 10), vy8,
                    pickupSprites[tile - 0x67], 0x0a, 12);
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

void GameSession::updatePortalsAndTriggers(Player& player, int& portalCooldown, int& triggerCooldown, bool down) {
        int tx = static_cast<int>(player.x + 6.0f) / 8;
        int ty = static_cast<int>(player.y + 12.0f) / 8;
        int tile = tileAt(tx, ty);
        uint16_t key = static_cast<uint16_t>(wordAt(tx, ty) & 0x7fffu);

        if (down && tile == 0x45 && key != 0 && portalCooldown == 0) {
            for (const LevelPortal& portal : level_.portals) {
                if (portal.key == key) {
                    player.x = static_cast<float>(portal.x);
                    player.y = static_cast<float>(portal.y);
                    player.vx = 0.0f;
                    player.vy = 0.0f;
                    portalCooldown = 30;
                    requestPortalTeleportSound();
                    break;
                }
            }
        } else if (tile == 0x72 && triggerCooldown == 0) {
            if (applyTileTrigger(wordAt(tx, ty))) {
                triggerCooldown = 30;
                requestTileTriggerSound();
            }
        }
    }

bool GameSession::applyTileTrigger(uint16_t key) {
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

void GameSession::accountTileRewrite(uint8_t from, uint8_t to) {
        (void)from;
        (void)to;
    }
}
