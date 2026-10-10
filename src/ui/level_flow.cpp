#include "ui/level_flow.hpp"
#include "resources/palette.hpp"
#include <algorithm>
#include <utility>

namespace lezac::ui {
using resources::vga6To8;

std::vector<OutroLine> LevelFlow::gameOverLines(bool italian, const std::array<uint32_t, 2>& scores) {
    std::vector<OutroLine> lines{
        {"GAME OVER", 11, 31, 25, 77, -1},
        {italian ? "PUNTEGGIO FINALE" : "FINAL SCORE", 11, 244, 25, 97, -1}};
    int y = 121;
    for (size_t p = 0; p < scores.size(); ++p) {
        // 1C4B treats the stored score as a signed long and omits nonpositive values.
        if (scores[p] == 0 || scores[p] >= 0x80000000u) continue;
        lines.push_back({(italian ? std::string("GIOCATORE") : std::string("PLAYER")) +
                             std::to_string(p + 1) + ": " + std::to_string(scores[p]),
                         9, 244, 25, y, static_cast<int>(p)});
        y += 11;
    }
    return lines;
}

LevelIntroPattern LevelFlow::makeLevelIntroPattern(const std::function<int(int, int)>& randomInclusive) {
    LevelIntroPattern pattern;
    pattern.horizontalStep = randomInclusive(1, 80);
    pattern.verticalStep = randomInclusive(1, 80);
    std::array<int, 3> starts{};
    std::array<int, 3> deltas{};
    for (int& start : starts) start = randomInclusive(0, 19);
    for (int& delta : deltas) delta = randomInclusive(0, 29);
    for (size_t i = 0; i < pattern.colors.size(); ++i) {
        auto component = [&](size_t channel) {
            return vga6To8(static_cast<uint8_t>(
                starts[channel] +
                deltas[channel] * static_cast<int>(i) /
                    static_cast<int>(kLevelIntroPaletteCount)));
        };
        pattern.colors[i] = {component(0), component(1), component(2)};
    }
    return pattern;
}

LevelIntroPattern LevelFlow::capturedLevelIntroPattern() {
    LevelIntroPattern pattern;
    pattern.horizontalStep = 37;
    pattern.verticalStep = 77;
    constexpr std::array<int, 3> kStarts{17, 18, 16};
    constexpr std::array<int, 3> kDeltas{21, 23, 9};
    for (size_t i = 0; i < pattern.colors.size(); ++i) {
        auto component = [&](size_t channel) {
            return vga6To8(static_cast<uint8_t>(
                kStarts[channel] +
                kDeltas[channel] * static_cast<int>(i) /
                    static_cast<int>(kLevelIntroPaletteCount)));
        };
        pattern.colors[i] = {component(0), component(1), component(2)};
    }
    return pattern;
}

size_t LevelFlow::visibleLevelIntroCharacters(uint32_t now) const {
    if (!levelIntro_.active) return 0;
    const size_t captionSize =
        levelIntroCaption(levelIntro_.levelIndex).size();
    if (levelIntro_.typingSkipped) return captionSize;
    const uint32_t elapsed = now - levelIntro_.startedAt;
    return std::min(captionSize,
                    static_cast<size_t>(elapsed /
                                        kLevelIntroCharacterDelayMs) +
                        1);
}

void LevelFlow::updateLevelIntro(uint32_t now) {
    // Text typing is time-based; original 1000:2C72 then blocks for a key.
    (void)now;
}

bool LevelFlow::introWaitingForKey(uint32_t now) const {
    return levelIntro_.active && (levelIntro_.typingSkipped ||
        now - levelIntro_.startedAt >= levelIntroCaption(levelIntro_.levelIndex).size() * kLevelIntroCharacterDelayMs);
}

void LevelFlow::skipIntroTyping() {
    if (levelIntro_.active) levelIntro_.typingSkipped = true;
}

std::vector<OutroLine> LevelFlow::levelOutroLines(bool italian) const {
    std::vector<OutroLine> lines;
    const bool it = italian;
    lines.push_back({it ? "LIVELLO COMPLETATO" : "LEVEL COMPLETED",
                     11, 31, 25, 60, -1});
    lines.push_back({(it ? std::string("BONUS DISTRUZIONE: ")
                         : std::string("DESTRUCTION BONUS: ")) +
                         std::to_string(levelOutro_.destBonus),
                     9, 244, 241, 81, -1});
    lines.push_back({"BOMBA BONUS", 9, 244, 25, 99, -1});
    int y = 120;
    for (int i = 0; i < 2; ++i) {
        if (!levelOutro_.playerActive[static_cast<size_t>(i)]) continue;
        lines.push_back({(it ? std::string("GIOCATORE ")
                             : std::string("PLAYER ")) +
                             std::to_string(i + 1) + "   " +
                             std::to_string(levelOutro_.bombBonus[
                                 static_cast<size_t>(i)]),
                         9, 31, 13, y, i});
        y += 11;
    }
    return lines;
}

std::vector<OutroSegment> LevelFlow::levelOutroSchedule(bool italian) const {
    std::vector<OutroSegment> segs;
    const std::vector<OutroLine> lines = levelOutroLines(italian);
    uint32_t t = 500;
    for (size_t k = 0; k < lines.size(); ++k) {
        const uint32_t dur =
            (static_cast<uint32_t>(lines[k].text.size()) + kLevelOutroColorSpan) *
            kLevelIntroCharacterDelayMs;
        segs.push_back({t, t + dur, static_cast<int>(k), -1, true});
        t += dur;
        if (lines[k].player >= 0) {
            const uint32_t count = levelOutro_.reelSteps[
                static_cast<size_t>(lines[k].player)] * 15u;
            segs.push_back({t, t + count, -1, lines[k].player, false});
            t += count;
            segs.push_back({t, t + 200, -1, -1, false});
            t += 200;
        }
    }
    return segs;
}

void LevelFlow::beginIntro(int levelIndex, LevelIntroPattern pattern, uint32_t now) {
    levelIntro_ = {};
    levelIntro_.active = true;
    levelIntro_.startedAt = now;
    levelIntro_.levelIndex = levelIndex;
    levelIntro_.pattern = std::move(pattern);
}

void LevelFlow::beginOutro(uint32_t now, int destroyedCount,
                          std::array<bool, 2> active,
                          std::array<std::array<int, 4>, 2> bombCounts,
                          const std::array<uint32_t, 2>& scores,
                          const std::array<core::HudScoreReel, 2>& reels) {
    levelOutro_ = {};
    levelOutro_.active = true;
    levelOutro_.startedAt = now;
    levelOutro_.destBonus = static_cast<uint16_t>(static_cast<uint32_t>(destroyedCount) * 10u);
    levelOutro_.playerActive = active;
    for (size_t p = 0; p < 2; ++p) {
        const uint16_t bombWord = static_cast<uint16_t>(
            static_cast<uint8_t>(bombCounts[p][1]) * 100 +
            static_cast<uint8_t>(bombCounts[p][2]) * 500 +
            static_cast<uint8_t>(bombCounts[p][3]) * 2000);
        // 1F5B sign-extends the wrapped 16-bit unused-bomb sum.
        levelOutro_.bombBonus[p] = bombWord < 0x8000 ? bombWord : static_cast<int>(bombWord) - 0x10000;
        core::HudScoreReel next = reels[p];
        next.setValue(scores[p] + static_cast<uint32_t>(levelOutro_.destBonus + levelOutro_.bombBonus[p]));
        next.prepareTargets();
        levelOutro_.reelSteps[p] = next.stepsUntilSettled();
    }
}

void LevelFlow::skipOutroTyping(uint32_t now, bool italian) {
    const uint32_t elapsed = now - levelOutro_.startedAt;
    for (const OutroSegment& seg : levelOutroSchedule(italian)) {
        if (seg.typing && elapsed >= seg.start && elapsed < seg.end) {
            levelOutro_.startedAt -= (seg.end - elapsed);
            break;
        }
    }
}

void LevelFlow::updateOutro(uint32_t now, bool italian,
                           const std::function<void()>& preparePrelude,
                           const std::function<void(size_t, uint32_t)>& awardScore,
                           const std::function<void(size_t)>& advanceScore,
                           const std::function<void(size_t)>& awardTick,
                           const std::function<void(size_t, uint32_t, uint32_t)>& typingBoundary) {
    if (!levelOutro_.active || levelOutro_.awaitKey) return;
    const uint32_t elapsed = now - levelOutro_.startedAt;
    if (elapsed >= 500 && !levelOutro_.preludeApplied) {
        levelOutro_.preludeApplied = true;
        preparePrelude();
    }
    const std::vector<OutroSegment> segs = levelOutroSchedule(italian);
    for (const OutroSegment& seg : segs) {
        if (elapsed < seg.start) continue;
        if (seg.typing) {
            const size_t line = static_cast<size_t>(seg.line);
            const uint32_t steps = std::min((seg.end - seg.start) / kLevelIntroCharacterDelayMs,
                (elapsed - seg.start) / kLevelIntroCharacterDelayMs + 1);
            while (levelOutro_.typingSteps[line] < steps) {
                const uint32_t step = ++levelOutro_.typingSteps[line];
                if (typingBoundary) typingBoundary(line, step, seg.start + (step - 1) * kLevelIntroCharacterDelayMs);
            }
            continue;
        }
        if (seg.player < 0 || elapsed < seg.start) continue;
        const size_t p = static_cast<size_t>(seg.player);
        const int total = levelOutro_.destBonus + levelOutro_.bombBonus[p];
        if (!levelOutro_.awardStarted[p]) {
            levelOutro_.awardStarted[p] = true;
            levelOutro_.awarded[p] = total;
            awardScore(p, static_cast<uint32_t>(total));
        }
        const uint32_t delays = std::min(levelOutro_.reelSteps[p], (elapsed - seg.start) / 15u);
        const uint32_t advances = std::min(levelOutro_.reelSteps[p], delays + 1);
        // 2007 advances/draws first; 201A delays 15ms, then 2021 draws RNG.
        while (levelOutro_.completedDelays[p] < delays || levelOutro_.advancedSteps[p] < advances) {
            if (levelOutro_.completedDelays[p] < delays &&
                levelOutro_.completedDelays[p] < levelOutro_.advancedSteps[p]) {
                awardTick(p);
                ++levelOutro_.completedDelays[p];
            } else {
                advanceScore(p);
                ++levelOutro_.advancedSteps[p];
            }
        }
    }
    if (!segs.empty() && elapsed >= segs.back().end) levelOutro_.awaitKey = true;
}

void LevelFlow::finishOutro(const std::function<void(size_t, uint32_t)>& awardScore) {
    for (size_t p = 0; p < 2; ++p) {
        if (!levelOutro_.playerActive[p]) continue;
        const int total = levelOutro_.destBonus + levelOutro_.bombBonus[p];
        if (!levelOutro_.awardStarted[p]) awardScore(p, static_cast<uint32_t>(total));
    }
    levelOutro_ = {};
}
}
