#include "gameplay/player_roster.hpp"
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

State2VisualCursor& PlayerRoster::state2VisualCursorFor(uint8_t startMarker) {
        return startMarker == 2 && state_.playerCount_ > 1 ? state_.state2Visual2_
                                                     : state_.state2Visual_;
    }

State2EffectEntry& PlayerRoster::state2EffectEntryFor(uint8_t startMarker) {
        return startMarker == 2 && state_.playerCount_ > 1 ? state_.state2Effect2_
                                                     : state_.state2Effect_;
    }

void PlayerRoster::refreshState2EffectEntry(const Player& player, const State2VisualCursor& cursor, State2EffectEntry& entry) {
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

void PlayerRoster::resetState2VisualCursor(State2VisualCursor& cursor) {
        cursor.current = kState2VisualStartFrame;
        cursor.first = kState2VisualStartFrame;
        cursor.last = kState2VisualEndFrame;
        cursor.counter = kState2VisualDelay;
        cursor.delay = kState2VisualDelay;
        cursor.mode = 1;
        cursor.step = 1;
        cursor.active = true;
    }

bool PlayerRoster::updateState2VisualCursor(State2VisualCursor& cursor) {
        if (!cursor.active || cursor.mode == 0) return false;
        ++cursor.counter;
        if (cursor.counter <= cursor.delay) return false;
        cursor.counter = 0;
        cursor.current = static_cast<uint8_t>(
            static_cast<int>(cursor.current) + static_cast<int>(cursor.step));
        if (cursor.mode == 2) {
            if (cursor.current >= cursor.last || cursor.current <= cursor.first) {
                cursor.step = static_cast<int8_t>(-cursor.step);
            }
            return true;
        }
        if (cursor.current > cursor.last) {
            cursor.current = cursor.first;
        }
        return true;
    }

bool PlayerRoster::allPlayersOutOfLives() const {
        return state_.playerCount_ <= 1 ? state_.lives_ < 0 : state_.lives_ < 0 && state_.lives2_ < 0;
    }

int& PlayerRoster::deathStateTimerFor(uint8_t startMarker) {
        return startMarker == 2 && state_.playerCount_ > 1 ? state_.deathStateTimer2_
                                                     : state_.deathStateTimer_;
    }

bool& PlayerRoster::pendingLifeLossFor(uint8_t startMarker) {
        return startMarker == 2 && state_.playerCount_ > 1 ? state_.pendingLifeLoss2_
                                                     : state_.pendingLifeLoss_;
    }

uint8_t PlayerRoster::originalPlayerState(uint8_t player) const {
        if (player == 2 && state_.playerCount_ < 2) return 0;
        const int lives = player == 2 ? state_.lives2_ : state_.lives_;
        const bool dead = player == 2 ? state_.player2Dead_ : state_.playerDead_;
        const bool pending = player == 2 ? state_.pendingLifeLoss2_ : state_.pendingLifeLoss_;
        if (lives < 0) return 0;
        return dead && !pending && !state_.levelRestartPromoted_ ? 2 : 1;
    }

uint32_t& PlayerRoster::scoreForPlayer(uint8_t player) {
        return player == 2 && state_.playerCount_ > 1 ? state_.score2_ : state_.score_;
    }

void PlayerRoster::addScore(uint8_t player, uint32_t amount) {
        scoreForPlayer(player) += amount;
    }

void PlayerRoster::clearRunScores() {
        state_.score_ = 0;
        state_.score2_ = 0;
    }

void PlayerRoster::updateDamageCooldowns() {
        if (state_.damageCooldown_ > 0) --state_.damageCooldown_;
        if (state_.damageCooldown2_ > 0) --state_.damageCooldown2_;
    }

void PlayerRoster::queuePlayerDamage(uint8_t startMarker, uint8_t amount) {
        if (amount == 0) return;
        bool secondPlayer = startMarker == 2 && state_.playerCount_ > 1;
        bool dead = secondPlayer ? state_.player2Dead_ : state_.playerDead_;
        int cooldown = secondPlayer ? state_.damageCooldown2_ : state_.damageCooldown_;
        if (!dead && cooldown > 0) return;
        uint8_t& pending = secondPlayer ? state_.pendingDamage2_ : state_.pendingDamage_;
        pending = static_cast<uint8_t>(pending + amount);
    }

void PlayerRoster::selectPlayerPosture(Player& player, uint8_t spriteBase, bool dropping) {
        // 1000:6772..67FE and 69BB..6A43 preserve the running cursor, or
        // initialize an idle backup, before selecting the temporary pose.
        if (player.animation.first == spriteBase + 18) return;
        player.animationBackup = player.animation.mode == 0 ?
            ActorAnimation::initialize(spriteBase + 1, spriteBase + 1, 2, 3) : player.animation;
        player.animation = ActorAnimation::initialize(spriteBase + 17,
                                                       spriteBase + (dropping ? 19 : 18), 3, 3);
        player.spriteIndex = spriteBase + 17;
        player.singlePixelSprite = false;
    }

void PlayerRoster::updatePlayerGravity(Player& player, bool bottom, uint8_t spriteBase, int& y) {
        // 1000:6743..6813 precedes input; a new jump does not add gravity.
        if (!bottom || player.vy8 < 0) {
            player.vy8 = static_cast<int16_t>(std::min<int>(kPlayerTerminalVelocity8,
                                                           player.vy8 + kPlayerGravity8));
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

void PlayerRoster::integratePlayerMotion(Player& player, int x, int y, const ActiveMonster::EdgeFlags& edges) {
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
        player.grounded = edges.bottom && player.vy8 == 0;
        syncPlayerVelocityMirror(player);
    }

void PlayerRoster::syncPlayerVelocityMirror(Player& player) {
        player.vx = player.vx8 / 256.0f;
        player.vy = player.vy8 / 256.0f;
    }

int16_t PlayerRoster::actorFloorFriction(int16_t velocity) {
        // Original shared helper 1000:5B86, called by players and bombs.
        return static_cast<int16_t>(std::abs(velocity) < 43 ? 0 :
                                    velocity + (velocity < 0 ? 42 : -42));
    }

int16_t PlayerRoster::playerWalkVelocity(int16_t velocity, bool left, bool right, bool bottom) {
        // 1000:6AC6/6B1C test before adding. Reaccelerating after friction
        // can cross +/-1024; clamping the result would change the original.
        if (left && velocity > -kPlayerWalkVelocity8) velocity -= kPlayerWalkAcceleration8;
        if (right && velocity < kPlayerWalkVelocity8) velocity += kPlayerWalkAcceleration8;
        if (bottom && !left && !right) velocity = actorFloorFriction(velocity);
        return velocity;
    }
}
