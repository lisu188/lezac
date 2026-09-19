#pragma once

#include "ui/input.hpp"
#include "ui/models.hpp"
#include "ui/record_store.hpp"
#include <functional>

namespace lezac::ui {
// Actions are invoked synchronously and are never retained by the controller.
// Their order preserves the recovered reset, prompt, and score transitions.
struct UiActions {
    std::function<void()> clearScores;
    std::function<void(int)> prepareNewGame;
    std::function<void(int)> beginLevel;
    std::function<void()> resetAfterEndRun;
    std::function<void()> recordPromptSound;
    std::function<void()> recordCommitSound;
    std::function<void()> recordsPageSound;
    std::function<void(int)> firePlayer;
    std::function<void(int)> adjustViewWidth;
};

class UiController {
public:
    const UiState& snapshot() const { return state_; }
    void restoreSnapshot(UiState state) { state_ = state; }
    void setMenu(bool value) { state_.menu = value; }
    void setPage(MenuPage value) { state_.page = value; }
    void setPaused(bool value) { state_.paused = value; }
    void setShowBackground(bool value) { state_.showBackground = value; }
    void setItalian(bool value) { state_.italian = value; }
    void onKey(Key key, bool& running, int levelIndex, int playerCount,
               RecordStore& records, const UiActions& actions);
    bool shouldAcceptRepeatedNameEntryKey(Key key) const;
    static char recordCharForKey(Key key);
    static bool isPlayer1FireKey(Key key);
    static bool isPlayer2FireKey(Key key);
    static MenuPage endMenuPage(EndReason reason);
    void handleNameEntryKey(Key key, RecordStore& records, const UiActions& actions);
    void beginEndRun(EndReason reason, int levelIndex, int playerCount,
                     uint32_t score, uint32_t score2, RecordStore& records,
                     const UiActions& actions);
    void finalizePendingRecord(RecordStore& records, const UiActions& actions);
    void cancelPendingRecord(RecordStore& records, const UiActions& actions);
    bool startNextPendingRecord(RecordStore& records, const UiActions& actions);
private:
    UiState state_;
};
}
