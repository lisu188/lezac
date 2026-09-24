#pragma once
#include "gameplay/world_models.hpp"

namespace lezac::gameplay {

struct PlayerRosterSnapshot {
    int playerCount_ = 1;
    Player player_;
    Player player2_;
    int portalCooldown_ = 0;
    int triggerCooldown_ = 0;
    int portalCooldown2_ = 0;
    int triggerCooldown2_ = 0;
    int energy_ = 100;
    int energy2_ = 100;
    int lives_ = 3;
    int lives2_ = 3;
    bool playerDead_ = false;
    bool player2Dead_ = false;
    int reentryTimer_ = 0;
    int reentryTimer2_ = 0;
    bool reentryFire1_ = false;
    bool reentryFire2_ = false;
    bool reentryGate_ = true;
    uint8_t noActivePlayerTicks_ = 0;
    bool levelRestartPromoted_ = false;
    int deathStateTimer_ = 0;
    int deathStateTimer2_ = 0;
    bool pendingLifeLoss_ = false;
    bool pendingLifeLoss2_ = false;
    State2VisualCursor state2Visual_;
    State2VisualCursor state2Visual2_;
    State2EffectEntry state2Effect_;
    State2EffectEntry state2Effect2_;
    bool state2VisualCursorPreview_ = false;
    bool state2VisualRowPreview_ = false;
    int damageCooldown_ = 0;
    int damageCooldown2_ = 0;
    uint8_t pendingDamage_ = 0;
    uint8_t pendingDamage2_ = 0;
    BombInventory bombInventory_;
    BombInventory bombInventory2_;
    uint8_t weaponSwitchHoldTicks_ = 0;
    uint8_t weaponSwitchHoldTicks2_ = 0;
    uint32_t score_ = 0;
    uint32_t score2_ = 0;
};

class GameSession;
// The session alone coordinates cross-owner writes at recovered tick boundaries.
class PlayerRoster {
public:
    const PlayerRosterSnapshot& snapshot() const { return state_; }

    bool allPlayersOutOfLives() const;
    uint8_t originalPlayerState(uint8_t player) const;
private:
    friend class GameSession;
    State2VisualCursor& state2VisualCursorFor(uint8_t startMarker);
    State2EffectEntry& state2EffectEntryFor(uint8_t startMarker);
    void refreshState2EffectEntry(const Player& player, const State2VisualCursor& cursor, State2EffectEntry& entry);
    void resetState2VisualCursor(State2VisualCursor& cursor);
    bool updateState2VisualCursor(State2VisualCursor& cursor);
    int& deathStateTimerFor(uint8_t startMarker);
    bool& pendingLifeLossFor(uint8_t startMarker);
    uint32_t& scoreForPlayer(uint8_t player);
    void addScore(uint8_t player, uint32_t amount);
    void clearRunScores();
    void updateDamageCooldowns();
    void queuePlayerDamage(uint8_t startMarker, uint8_t amount = 1);
    static void selectPlayerPosture(Player& player, uint8_t spriteBase, bool dropping);
    static void updatePlayerGravity(Player& player, bool bottom, uint8_t spriteBase, int& y);
    static void integratePlayerMotion(Player& player, int x, int y, const ActiveMonster::EdgeFlags& edges);
    static void syncPlayerVelocityMirror(Player& player);
    static int16_t actorFloorFriction(int16_t velocity);
    static int16_t playerWalkVelocity(int16_t velocity, bool left, bool right, bool bottom);
    PlayerRosterSnapshot state_;
};
}
