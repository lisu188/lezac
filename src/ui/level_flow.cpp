#include "ui/level_flow.hpp"
#include "resources/palette.hpp"
#include <algorithm>
#include <utility>

namespace lezac::ui {
using resources::vga6To8;

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
            static_cast<uint32_t>(lines[k].text.size()) *
            kLevelIntroCharacterDelayMs;
        segs.push_back({t, t + dur, static_cast<int>(k), -1, true});
        t += dur;
        if (lines[k].player >= 0) {
            const int total = levelOutro_.destBonus +
                              levelOutro_.bombBonus[
                                  static_cast<size_t>(lines[k].player)];
            const uint32_t count =
                static_cast<uint32_t>((total + 99) / 100) * 15u;
            segs.push_back({t, t + count, -1, lines[k].player, false});
            t += count;
            segs.push_back({t, t + 200, -1, -1, false});
            t += 200;
        }
    }
    return segs;
}

void LevelFlow::beginIntro(int levelIndex, LevelIntroPattern pattern, uint32_t now) {
    levelIntro_.active = true;
    levelIntro_.startedAt = now;
    levelIntro_.levelIndex = levelIndex;
    levelIntro_.pattern = std::move(pattern);
}

void LevelFlow::beginOutro(uint32_t now, int destructionPercent,
                          std::array<bool, 2> active,
                          std::array<std::array<int, 4>, 2> bombCounts) {
    levelOutro_ = {};
    levelOutro_.active = true;
    levelOutro_.startedAt = now;
    levelOutro_.destBonus = destructionPercent * 10;
    levelOutro_.playerActive = active;
    for (size_t p = 0; p < 2; ++p) {
        levelOutro_.bombBonus[p] = bombCounts[p][1] * 100 + bombCounts[p][2] * 500 + bombCounts[p][3] * 2000;
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
                           const std::function<void(size_t, uint32_t)>& awardScore,
                           const std::function<void()>& awardTick) {
    if (!levelOutro_.active || levelOutro_.awaitKey) return;
    const uint32_t elapsed = now - levelOutro_.startedAt;
    const std::vector<OutroSegment> segs = levelOutroSchedule(italian);
    for (const OutroSegment& seg : segs) {
        if (seg.player < 0) continue;
        const size_t p = static_cast<size_t>(seg.player);
        const int total = levelOutro_.destBonus + levelOutro_.bombBonus[p];
        int target = 0;
        if (elapsed >= seg.end) target = total;
        else if (elapsed > seg.start) target = std::min(total, static_cast<int>((elapsed - seg.start) / 15) * 100);
        int delta = target - levelOutro_.awarded[p];
        if (delta > 0) {
            levelOutro_.awarded[p] = target;
            awardScore(p, static_cast<uint32_t>(delta));
            // The callback performs the shared RNG draw immediately after scoring.
            awardTick();
        }
    }
    if (!segs.empty() && elapsed >= segs.back().end) levelOutro_.awaitKey = true;
}

void LevelFlow::finishOutro(const std::function<void(size_t, uint32_t)>& awardScore) {
    for (size_t p = 0; p < 2; ++p) {
        if (!levelOutro_.playerActive[p]) continue;
        const int total = levelOutro_.destBonus + levelOutro_.bombBonus[p];
        const int delta = total - levelOutro_.awarded[p];
        if (delta > 0) awardScore(p, static_cast<uint32_t>(delta));
    }
    levelOutro_ = {};
}
}
