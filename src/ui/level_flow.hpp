#pragma once

#include "ui/models.hpp"
#include "core/hud.hpp"
#include <functional>
#include <utility>
#include <vector>

namespace lezac::ui {
class LevelFlow {
public:
    const LevelIntroState& intro() const { return levelIntro_; }
    const LevelOutroState& outro() const { return levelOutro_; }
    bool interactiveEnabled() const { return interactiveEnabled_; }
    void setInteractiveEnabled(bool value) { interactiveEnabled_ = value; }
    void restoreIntro(LevelIntroState state) { levelIntro_ = std::move(state); }
    void restoreOutro(LevelOutroState state) { levelOutro_ = std::move(state); }
    void setIntroActiveForFixture(bool value) { levelIntro_.active = value; }
    void setOutroStartForFixture(uint32_t value) { levelOutro_.startedAt = value; }
    void reset() { levelIntro_ = {}; levelOutro_ = {}; }
    static LevelIntroPattern makeLevelIntroPattern(const std::function<int(int, int)>& randomInclusive);
    static LevelIntroPattern capturedLevelIntroPattern();
    void beginIntro(int levelIndex, LevelIntroPattern pattern, uint32_t now);
    size_t visibleLevelIntroCharacters(uint32_t now) const;
    bool introWaitingForKey(uint32_t now) const;
    void skipIntroTyping();
    void updateLevelIntro(uint32_t now);
    std::vector<OutroLine> levelOutroLines(bool italian) const;
    std::vector<OutroSegment> levelOutroSchedule(bool italian) const;
    void beginOutro(uint32_t now, int destroyedCount,
                    std::array<bool, 2> active, std::array<std::array<int, 4>, 2> bombCounts,
                    const std::array<uint32_t, 2>& scores,
                    const std::array<core::HudScoreReel, 2>& reels);
    void skipOutroTyping(uint32_t now, bool italian);
    void updateOutro(uint32_t now, bool italian,
                     const std::function<void()>& preparePrelude,
                     const std::function<void(size_t, uint32_t)>& awardScore,
                     const std::function<void(size_t)>& advanceScore,
                     const std::function<void(size_t)>& awardTick);
    void finishOutro(const std::function<void(size_t, uint32_t)>& awardScore);
private:
    bool interactiveEnabled_ = false;
    LevelIntroState levelIntro_;
    LevelOutroState levelOutro_;
};
}
