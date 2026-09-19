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

bool GameSession::activateLaunchPad(Player& player, bool down, int localY) {
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
        if (sharedActorCount() < 30) {
            LaunchPadMarker marker;
            marker.x = static_cast<int>(player.x) + 4;
            marker.y = localY + 13;
            marker.actorOrder = claimActorOrder();
            launchPadMarkers_.push_back(marker);
        }
        return true;
    }

void GameSession::updateLaunchPadMarkers(uint64_t onlyOrder) {
        for (LaunchPadMarker& marker : launchPadMarkers_) {
            if (onlyOrder && marker.actorOrder != onlyOrder) continue;
            if ((logicTick_ & 1u) != 0 && marker.timer > 0) {
                --marker.timer;
            }
            if (marker.timer == 0) continue;
            integrateAxis8_8(marker.x, marker.fracX, marker.velocityX8);
            integrateAxis8_8(marker.y, marker.fracY, marker.velocityY8);
        }
        launchPadMarkers_.erase(
            std::remove_if(launchPadMarkers_.begin(), launchPadMarkers_.end(),
                           [](const LaunchPadMarker& marker) {
                               return marker.timer == 0;
                           }),
            launchPadMarkers_.end());
    }

void GameSession::updatePlayer(Player& player, bool left, bool right, bool jump, bool switchWeapon, uint8_t spriteBase, bool down) {
        if (player.animation.advance(player.animationBackup)) {
            player.spriteIndex = static_cast<uint8_t>(player.animation.current - 1);
            player.singlePixelSprite = false;
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
                }
            }
            if (player.dropTicks != 0) {
                // 1000:6A5E..6A76 lowers the local Y before integration.
                y += 2;
                --player.dropTicks;
                player.idleTicks = 0xF8;
            }
        }
        if (left) {
            if (stepLeft) {
                player.vy8 = -500;
                player.vx8 = -250;
                edges.left = false;
            }
            if (inputFrame < spriteBase + 10 || inputFrame > spriteBase + 17) {
                player.animation = ActorAnimation::initialize(spriteBase + 10, spriteBase + 17, 0, 1);
                player.idleTicks = 0;
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
                player.idleTicks = 0;
            }
        }
        player.vx8 = playerWalkVelocity(player.vx8, left, right, edges.bottom);
        player.animation.delay = static_cast<uint8_t>(4 - std::abs(player.vx8) / 256);
        if (!left && !right && !down && ++player.idleTicks == 5) {
            player.animation.mode = 0;
            // The cursor becomes 1 even for player 2; its displayed idle
            // descriptor is independently selected as 20 (1000:6BAD..6BD1).
            player.animation.current = 1;
            player.spriteIndex = spriteBase;
            player.singlePixelSprite = false;
        }
        if (jump && edges.bottom && player.vy8 == 0) {
            player.vy8 = kPlayerJumpVelocity8;
        }
        // 1000:6BD5 uses the updated velocity and local drop/ground Y, before
        // terrain damage and integration. The non-player pass is already over.
        tryActivePlayerFireAt(player, x, y, spriteBase == 19 ? 2 : 1);
        applyPlayerTerrainDamage(player, spriteBase == 19 ? energy2_ : energy_);
        integratePlayerMotion(player, x, y, edges);
    }

void GameSession::applyPlayerTerrainDamage(Player& player, int& energy) {
        // 1000:6F90..7011 scans TL, TR, BR, BL before integration. Only
        // the last flame cell supplies impulse, using its highest pool slot.
        const int x = (static_cast<int>(player.x) + 4) >> 3;
        const int y = static_cast<int>(player.y) >> 3;
        const std::array<std::array<int, 2>, 4> cells{{{x,y}, {x+1,y}, {x+1,y+1}, {x,y+1}}};
        int damage = 0, flameCell = 0;
        for (size_t i = 0; i < cells.size(); ++i) {
            const auto& cell = cells[i];
            const int glyph = tileAt(cell[0], cell[1]);
            if (glyph == 0x75) {
                damage += 2;
                flameCell = cell[1] * level_.width + cell[0];
            } else if (i < 2 && glyph >= 1 && glyph <= 0x4c) {
                damage += 2;
            }
        }
        if (flameCell != 0) {
            const auto ray = std::find_if(flameRecords_.rbegin(), flameRecords_.rend(),
                [flameCell](const FlameRecord& item) { return item.cell == flameCell; });
            if (ray != flameRecords_.rend()) {
                player.vx8 = static_cast<int16_t>(ray->vx * 8);
                player.vy8 = static_cast<int16_t>(ray->vy * 8);
                if (ray->mass > 1) damage += ray->mass / 10;
            }
        }
        energy = static_cast<uint8_t>(energy - damage);
    }

void GameSession::updateDyingPlayerMotion(Player& player) {
        // Behavior 2 (1000:7018) preserves velocity and fractional carries.
        int x = static_cast<int>(player.x), y = static_cast<int>(player.y);
        const auto edges = scanActorEdges(x, y);
        if (!edges.bottom || player.vy8 < 0) {
            player.vy8 = static_cast<int16_t>(std::min<int>(2047, player.vy8 + 64));
        } else if (player.vy8 > 0) {
            player.vy8 = 0;
            y &= ~7;
        }
        if (edges.bottom) player.vx8 = actorFloorFriction(player.vx8);
        integratePlayerMotion(player, x, y, edges);
    }

void GameSession::drainPlayerDamageCounters() {
        drainPlayerDamageCounter(player_, energy_, lives_, playerDead_, reentryTimer_,
                                 pendingDamage_, 1);
        if (playerCount_ > 1) {
            drainPlayerDamageCounter(player2_, energy2_, lives2_, player2Dead_,
                                     reentryTimer2_, pendingDamage2_, 2);
        } else {
            pendingDamage2_ = 0;
        }
    }

void GameSession::drainPlayerDamageCounter(Player& player, int& energy, int& lives, bool& dead, int& timer, uint8_t& pending, uint8_t startMarker) {
        uint8_t amount = pending;
        pending = 0;
        if (amount != 0) requestPlayerDamageSound();
        if (dead) return;
        uint8_t updatedEnergy =
            static_cast<uint8_t>(std::clamp(energy, 0, 255) - amount);
        energy = static_cast<int>(updatedEnergy);
        if (static_cast<uint16_t>(updatedEnergy) > 0x00c8) {
            beginPlayerDeath(player, energy, lives, dead, timer, startMarker);
        }
    }

void GameSession::damagePlayer(Player& player, int& energy, int& lives, bool& dead, int& timer, int& damageCooldown, uint8_t startMarker) {
        (void)damageCooldown;
        uint8_t immediateDamage = 1;
        drainPlayerDamageCounter(player, energy, lives, dead, timer,
                                 immediateDamage, startMarker);
    }

bool GameSession::playerOverlapsTileArea(const Player& player, int tx0, int ty0, int tx1, int ty1) const {
        float x = static_cast<float>(tx0 * kTileSize);
        float y = static_cast<float>(ty0 * kTileSize);
        float w = static_cast<float>((tx1 - tx0 + 1) * kTileSize);
        float h = static_cast<float>((ty1 - ty0 + 1) * kTileSize);
        return playerOverlaps(player, x, y, w, h);
    }

void GameSession::damagePlayersInTileArea(int tx0, int ty0, int tx1, int ty1) {
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

void GameSession::beginPlayerDeath(Player& player, int& energy, int& lives, bool& dead, int& timer, uint8_t startMarker) {
        // 1000:30C1..30F5 latches one shared gate at death. Waiting does not
        // recompute it when objective tiles or the collected count change.
        reentryGate_ = canReenterLevel();
        pendingLifeLossFor(startMarker) = lives >= 0;
        energy = 100;
        deathStateTimerFor(startMarker) = kDeathStateTicks;
        State2VisualCursor& cursor = state2VisualCursorFor(startMarker);
        resetState2VisualCursor(cursor);
        refreshState2EffectEntry(player, cursor, state2EffectEntryFor(startMarker));
        syncPlayerVelocityMirror(player);
        player.grounded = false;
        if (lives < 0) {
            dead = true;
            timer = 0;
            cursor.active = false;
            state2EffectEntryFor(startMarker).active = false;
            requestPlayerDeathSound();
            if (allPlayersOutOfLives()) if (hooks_.gameOver) hooks_.gameOver();
            return;
        }
        dead = true;
        timer = kDeathStateTicks;
        requestPlayerDeathSound();
    }

void GameSession::finalizePendingLifeLoss(bool& dead, int& lives, int& timer, uint8_t startMarker) {
        bool& pending = pendingLifeLossFor(startMarker);
        if (!pending) return;
        pending = false;
        --lives;  // The original reserve byte marks out at FF, not at zero.
        if (lives < 0) {
            dead = true;
            timer = 0;
            state2VisualCursorFor(startMarker).active = false;
            state2EffectEntryFor(startMarker).active = false;
            if (allPlayersOutOfLives()) if (hooks_.gameOver) hooks_.gameOver();
        }
    }

void GameSession::updateWaitingPlayerPlacement(Player& player) {
        const uint16_t x = static_cast<uint16_t>(player.x);
        const uint16_t y = static_cast<uint16_t>(player.y);
        const uint16_t row = (static_cast<uint16_t>(y + 7) >> 3) + 1;
        const uint16_t cell = static_cast<uint16_t>(row * level_.width + (x >> 3));
        auto solid = [&](uint16_t at) {
            const uint8_t tile = at < level_.tiles.size() ? level_.tiles[at] : 0;
            return tile >= 1 && tile <= 76;
        };
        // 1000:7E41 jumps directly to DEC on the left cell. Only the right
        // cell has the unsigned Y > 24 guard; neither branch gates fire.
        if (solid(cell) || (solid(static_cast<uint16_t>(cell + 1)) && y > 24)) {
            player.y = static_cast<float>(static_cast<uint16_t>(y - 1));
        }
    }

void GameSession::updateReentry(Player& player, int& energy, int& lives, bool& dead, int& timer, uint8_t startMarker, bool allowLevelRestart) {
        (void)energy;
        (void)allowLevelRestart;
        if (!dead || lives < 0) return;
        timer = static_cast<uint16_t>(timer - 1);
        int& deathStateTimer = deathStateTimerFor(startMarker);
        if (deathStateTimer > 0) --deathStateTimer;
        if (timer == 0) {
            pendingLifeLossFor(startMarker) = true;
            finalizePendingLifeLoss(dead, lives, timer, startMarker);
            if (lives >= 0 && !(hooks_.menuActive && hooks_.menuActive())) {
                // 1000:7D11 calls the start-marker locator at 056B before
                // waiting for input; it preserves motion and animation bytes.
                if (const LevelPortal* start = findStartPortal(startMarker)) {
                    player.x = static_cast<float>(start->x);
                    player.y = static_cast<float>(start->y);
                }
                player.idleTicks = 0;
                player.spriteIndex = 0x27 - 1;
                player.singlePixelSprite = !reentryGate_;
                auto& inventory = startMarker == 2 ? bombInventory2_ : bombInventory_;
                constexpr std::array<int, 3> minimum{100, 10, 2};
                for (size_t i = 0; i < minimum.size(); ++i) {
                    inventory.counts[i] = std::max(inventory.counts[i], minimum[i]);
                }
            }
        }
        if (lives < 0 || (hooks_.menuActive && hooks_.menuActive())) return;
        if (!reentryGate_) noActivePlayerTicks_ = kSharedReentryTicks - 1;
        if (originalPlayerState(startMarker) == 2) updateWaitingPlayerPlacement(player);
    }

bool GameSession::updateSharedReentryFallback() {
        if (originalPlayerState(1) == 1 || originalPlayerState(2) == 1) {
            noActivePlayerTicks_ = 0;
            return false;
        }
        notifyReentryBoundary("fallback_increment");
        ++noActivePlayerTicks_;
        if (noActivePlayerTicks_ != kSharedReentryTicks) return false;
        notifyReentryBoundary("fallback_promote");
        levelRestartPromoted_ = true;
        restartCurrentLevelAfterDeath();
        return true;
    }

void GameSession::tryReenterPlayer(Player& player, int& energy, int& lives, bool& dead, int& timer, int& damageCooldown, uint8_t startMarker) {
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
        energy = 100;
        deathStateTimerFor(startMarker) = 0;
        state2VisualCursorFor(startMarker).active = false;
        state2EffectEntryFor(startMarker).active = false;
        (void)damageCooldown;
        dead = false;
        reentryFire1_ = reentryFire2_ = false;
    }

void GameSession::respawnPlayerAtStart(Player& player, int& energy, uint8_t startMarker) {
        energy = 100;
        player.vx = 0.0f;
        player.vy = 0.0f;
        player.grounded = false;
        if (const LevelPortal* start = findStartPortal(startMarker)) {
            player.x = static_cast<float>(start->x);
            player.y = static_cast<float>(start->y);
        }
    }

void GameSession::restartCurrentLevelAfterDeath() {
        if (hooks_.beginLevel) hooks_.beginLevel(levelIndex_);
    }

bool GameSession::isFinalLevel() const {
        return !levels_.empty() &&
               levelIndex_ + 1 >= static_cast<int>(levels_.size());
    }
}
