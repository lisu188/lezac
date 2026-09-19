#pragma once

#include "resources/types.hpp"
#include <array>
#include <cstddef>
#include <cstdint>
#include <string>

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

}
