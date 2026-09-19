#include "ui/ui_controller.hpp"

namespace lezac::ui {
char UiController::recordCharForKey(Key key) {
    if (key >= Key::A && key <= Key::Z) return static_cast<char>('a' + static_cast<int>(key) - static_cast<int>(Key::A));
    if (key == Key::Space) return ' ';
    return '\0';
}
bool UiController::shouldAcceptRepeatedNameEntryKey(Key key) const {
    if (!state_.menu || state_.page != MenuPage::NameEntry) return false;
    return key == Key::Backspace || recordCharForKey(key) != '\0';
}
bool UiController::isPlayer1FireKey(Key key) {
    return key == Key::N || key == Key::Space || key == Key::RightControl;
}
bool UiController::isPlayer2FireKey(Key key) { return key == Key::Keypad0 || key == Key::Insert; }
MenuPage UiController::endMenuPage(EndReason reason) {
    return reason == EndReason::CompletedGame ? MenuPage::CompletedGame : MenuPage::GameOver;
}

bool UiController::startNextPendingRecord(RecordStore& records, const UiActions& actions) {
    if (!records.startNextPendingRecord()) return false;
    state_.page = MenuPage::NameEntry;
    actions.recordPromptSound();
    return true;
}
void UiController::finalizePendingRecord(RecordStore& records, const UiActions& actions) {
    const auto result = records.finalizePendingRecord();
    if (result == RecordStore::CommitResult::NoPending) { state_.page = MenuPage::Records; return; }
    if (result == RecordStore::CommitResult::SaveFailed) { state_.page = MenuPage::NameEntry; return; }
    if (startNextPendingRecord(records, actions)) return;
    actions.clearScores();
    state_.page = MenuPage::Records;
}
void UiController::cancelPendingRecord(RecordStore& records, const UiActions& actions) {
    records.clearPendingRecord();
    if (startNextPendingRecord(records, actions)) return;
    actions.clearScores();
    state_.page = MenuPage::Records;
}
void UiController::handleNameEntryKey(Key key, RecordStore& records, const UiActions& actions) {
    if (key == Key::Return || key == Key::KeypadEnter) {
        actions.recordCommitSound();
        finalizePendingRecord(records, actions);
        return;
    }
    if (key == Key::Backspace) { records.eraseNameCharacter(); return; }
    if (key == Key::Escape) { cancelPendingRecord(records, actions); return; }
    records.appendNameCharacter(recordCharForKey(key));
}
void UiController::beginEndRun(EndReason reason, int levelIndex, int playerCount,
                              uint32_t score, uint32_t score2, RecordStore& records,
                              const UiActions& actions) {
    records.beginEndRun(reason, levelIndex, playerCount, score, score2);
    state_.menu = true;
    state_.lastEndReason = reason;
    actions.resetAfterEndRun();
    if (!startNextPendingRecord(records, actions)) state_.page = endMenuPage(reason);
}
void UiController::onKey(Key key, bool& running, int levelIndex, int playerCount,
                         RecordStore& records, const UiActions& actions) {
    if (state_.menu) {
        if (state_.page == MenuPage::NameEntry) {
            handleNameEntryKey(key, records, actions);
        } else if (state_.page == MenuPage::GameOver || state_.page == MenuPage::CompletedGame) {
            if (key == Key::Escape || key == Key::Return || key == Key::KeypadEnter || key == Key::Space) {
                actions.clearScores(); records.clearQueue(); records.clearPendingRecord();
                state_.page = MenuPage::Main;
            }
        } else if (key == Key::Escape) {
            if (state_.page == MenuPage::Main) running = false;
            else state_.page = MenuPage::Main;
        } else if (key == Key::Return || key == Key::One || key == Key::Two) {
            actions.prepareNewGame(key == Key::Two ? 2 : 1);
            actions.clearScores(); records.clearQueue(); records.clearPendingRecord();
            actions.beginLevel(0);
            state_.menu = false; state_.page = MenuPage::Main;
        } else if (key == Key::I) state_.page = MenuPage::Info;
        else if (key == Key::Z) state_.page = MenuPage::Instructions;
        else if (key == Key::R) { state_.page = MenuPage::Records; actions.recordsPageSound(); }
        else if (key == Key::S) state_.showBackground = !state_.showBackground;
        else if (key == Key::L) state_.italian = !state_.italian;
    } else if (key == Key::P) state_.paused = !state_.paused;
    else if (key == Key::Escape) { state_.paused = false; state_.menu = true; state_.page = MenuPage::Main; }
    else if (key == Key::F5) { state_.paused = false; actions.beginLevel(levelIndex); }
    else if (key == Key::PageUp) { state_.paused = false; actions.beginLevel(levelIndex + 1); }
    else if (key == Key::PageDown) { state_.paused = false; actions.beginLevel(levelIndex - 1); }
    else if (state_.paused) return;
    else if (isPlayer1FireKey(key)) actions.firePlayer(1);
    else if (playerCount > 1 && isPlayer2FireKey(key)) actions.firePlayer(2);
    else if (key == Key::S) state_.showBackground = !state_.showBackground;
    else if (key == Key::R && playerCount == 1) actions.adjustViewWidth(-32);
    else if (key == Key::E && playerCount == 1) actions.adjustViewWidth(32);
}
}
