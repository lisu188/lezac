#pragma once

#include "resources/types.hpp"
#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>

namespace lezac::ui {
using resources::Rgb;

inline constexpr int kNameEntryLabelX = 58;
inline constexpr int kNameEntrySlotY = 120;
inline constexpr int kNameEntrySlotCount = 8;
inline constexpr int kNameEntrySlotAdvance = 9;
inline constexpr int kNameEntryCursorBoxW = 8;
inline constexpr int kNameEntryCursorBoxH = 10;
inline constexpr uint32_t kNameEntryCursorBackground = 0xff90ffb0u;
inline constexpr uint32_t kNameEntryCursorForeground = 0xff000000u;
inline constexpr uint32_t kLevelIntroCharacterDelayMs = 81;
inline constexpr int kLevelIntroCellAdvance = 11;
inline constexpr int kLevelIntroTextY = 94;
inline constexpr uint8_t kLevelIntroPaletteFirst = 176;
inline constexpr size_t kLevelIntroPaletteCount = 7;
inline constexpr uint32_t kMainMenuFadeStepMs = 22;
inline constexpr uint32_t kMainMenuFadeDurationMs = 64 * kMainMenuFadeStepMs;
// 1000:247F calibrates CRT.Delay with 8000 / elapsed hundredths: 80 ms.
inline constexpr uint32_t kMainMenuCharacterDelayMs = 80;
inline constexpr int kMainMenuCellAdvance = 9;
inline constexpr int kMainMenuTextY = 77;
inline constexpr int kMainMenuLinePitch = 10;
inline constexpr size_t kMainMenuTrailSteps = 5;

inline const std::array<std::string_view, 7>& mainMenuLines(bool italian) {
    static constexpr std::array<std::string_view, 7> italianLines{{
        "PREMI 1 PER UN GIOCATORE.", "PREMI 2 PER DUE GIOCATORI.",
        "I: INFORMAZIONI.", "Z: ISTRUZIONI.", "R: VEDI RECORDS.",
        "L: ENGLISH.", "ESC PER USCIRE."}};
    static constexpr std::array<std::string_view, 7> englishLines{{
        "PRESS 1 FOR ONE PLAYER GAME.", "PRESS 2 FOR TWO PLAYERS GAME.",
        "I: INFOS.", "Z: INSTRUCTIONS.", "R: SHOW RECORDS.",
        "L: ITALIANO.", "ESC EXITS."}};
    return italian ? italianLines : englishLines;
}

inline size_t mainMenuStepCount(bool italian) {
    size_t count = 0;
    for (const auto line : mainMenuLines(italian)) count += line.size() + kMainMenuTrailSteps;
    return count;
}

struct MainMenuState {
    bool active = false;
    uint32_t startedAt = 0;
    uint32_t fadeEnd = kMainMenuFadeDurationMs;
    bool textSkipped = false;
};

struct MainMenuProgress {
    uint8_t fade = 63;
    size_t steps = 0;
    bool waitingForKey = true;
};

inline MainMenuProgress mainMenuProgress(const MainMenuState& state, uint32_t now, bool italian) {
    const size_t count = mainMenuStepCount(italian);
    if (!state.active) return {63, count, true};
    const uint32_t elapsed = now - state.startedAt;
    if (elapsed < state.fadeEnd) {
        if (state.fadeEnd != kMainMenuFadeDurationMs && elapsed >= state.fadeEnd - kMainMenuFadeStepMs)
            return {63, 0, false};
        const auto fade = static_cast<uint8_t>(elapsed / kMainMenuFadeStepMs);
        return {static_cast<uint8_t>(fade > 63 ? 63 : fade), 0, false};
    }
    if (state.textSkipped) return {63, count, true};
    const uint32_t textElapsed = elapsed - state.fadeEnd;
    const size_t steps = textElapsed / kMainMenuCharacterDelayMs + 1;
    return {63, steps > count ? count : steps, textElapsed >= count * kMainMenuCharacterDelayMs};
}

struct LevelIntroPattern {
    int horizontalStep = 1;
    int verticalStep = 1;
    std::array<Rgb, kLevelIntroPaletteCount> colors{};
};

enum class MenuPage {
    Main,
    Info,
    Instructions,
    Records,
    NameEntry,
    GameOver,
    CompletedGame,
};

enum class EndReason {
    GameOver,
    CompletedGame,
};

struct OutroLine {
    std::string text;
    int cell;
    uint8_t glyphColor;
    uint8_t shadowColor;
    int y;
    int player;  // -1 for shared lines; 0/1 for the per-player lines
};

struct OutroSegment {
    uint32_t start;
    uint32_t end;
    int line;    // index into levelOutroLines(), -1 for pauses/count-ups
    int player;  // count-up player index, -1 otherwise
    bool typing;
};

inline std::string levelIntroCaption(int levelIndex) {
    return "PREPARATI PER IL LIVELLO " + std::to_string(levelIndex + 1);
}

struct LevelIntroState {
    bool active = false;
    uint32_t startedAt = 0;
    int levelIndex = 0;
    LevelIntroPattern pattern;
    bool typingSkipped = false;
};

// Level-completion banner sequence (original routine at file 0x24d3):
// typed lines over the live gameplay frame, a score count-up per player, then
// a blocking key wait before the level byte increments.
struct LevelOutroState {
    bool active = false;
    uint32_t startedAt = 0;
    int destBonus = 0;
    std::array<int, 2> bombBonus{{0, 0}};
    std::array<bool, 2> playerActive{{false, false}};
    std::array<int, 2> awarded{{0, 0}};
    bool typingSkipped = false;
    uint32_t typingSkipAt = 0;
    bool awaitKey = false;
};

struct PendingRecordEntry {
    uint32_t score = 0;
    uint8_t level = 0;
    uint8_t player = 1;
    EndReason reason = EndReason::GameOver;
};

struct PendingRecordState : PendingRecordEntry {
    std::string name;
};

struct UiState {
    bool menu = true;
    MenuPage page = MenuPage::Main;
    bool paused = false;
    bool showBackground = true;
    bool italian = true;
    EndReason lastEndReason = EndReason::GameOver;
    MainMenuState mainMenu;
};

}
