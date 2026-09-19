#pragma once

#include "core/random.hpp"
#include "core/hud.hpp"
#include "resources/types.hpp"
#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace lezac::rendering {

struct PresentationSnapshot {
    resources::Palette palette{};
    std::vector<uint8_t> backdrop;
    int pitch = 320;
    uint8_t redPhase = 0;
    std::array<uint8_t, 8> heapPadding{};
    size_t mapTileCount = 0;
    resources::Palette initialPalette{};
    std::array<core::HudScoreReel, 2> hudScores{};
    core::HudPaletteQueue hudPaletteQueue{};
    std::array<bool, 2> hudColumnReady{};
    int hudPreviousCollected = 20000;
    int hudPreviousDestruction = 200;
    int hudDestructionPercent = 0;
    bool originalPlayInitialized = false;
};

class PresentationState {
public:
    const resources::Palette& palette() const { return palette_; }
    const std::vector<uint8_t>& backdropBuffer() const { return backdropBuffer_; }
    int backdropPitch() const { return backdropPitch_; }
    uint8_t redPalettePhase() const { return redPalettePhase_; }
    void setPalette(const resources::Palette& palette) { palette_ = palette; }
    void buildBackdropBuffer(int playerCount, core::TurboRandom& random);
    void beginLevel(size_t mapTileCount);
    std::vector<uint8_t> decodeLevelPlane(const std::vector<uint8_t>& encoded, size_t outputSize);
    void updateRedPalette(uint16_t frame);
    void captureInitialPalette() { initialPalette_ = palette_; }
    void resetHudForLevel();
    void clearHudScores() { hudScores_ = {}; }
    void beginOriginalPlay(bool fromMenu);
    void prepareHudObjectives(uint16_t frame, int collected, int destructionPercent);
    void updateHudScores(int playerCount, const std::array<uint32_t, 2>& scores,
                         const std::array<bool, 2>& dead, const std::array<int, 2>& deathTimers);
    void advanceHudPalette();
    const std::array<core::HudScoreReel, 2>& hudScores() const { return hudScores_; }
    const core::HudPaletteQueue& hudPaletteQueue() const { return hudPaletteQueue_; }
    const std::array<bool, 2>& hudColumnReady() const { return hudColumnReady_; }
    int hudPreviousCollected() const { return hudPreviousCollected_; }
    int hudPreviousDestruction() const { return hudPreviousDestruction_; }
    int hudDestructionPercent() const { return hudDestructionPercent_; }
    uint32_t backdropColor(uint8_t index) const;
    uint8_t backdropByte(size_t offset, const std::vector<uint8_t>& liveTiles) const;
    PresentationSnapshot snapshot() const;
    void restore(const PresentationSnapshot& snapshot);
    void restoreBackdrop(const std::vector<uint8_t>& bytes) { backdropBuffer_ = bytes; }
    void restoreRedPalettePhase(uint8_t phase) { redPalettePhase_ = phase; }
    void writeBackdropPrefix(const std::vector<uint8_t>& bytes);
private:
    resources::Palette palette_{};
    resources::Palette initialPalette_{};
    std::array<core::HudScoreReel, 2> hudScores_{};
    core::HudPaletteQueue hudPaletteQueue_{};
    std::array<bool, 2> hudColumnReady_{};
    int hudPreviousCollected_ = 20000;
    int hudPreviousDestruction_ = 200;
    int hudDestructionPercent_ = 0;
    bool originalPlayInitialized_ = false;
    std::vector<uint8_t> backdropBuffer_;
    int backdropPitch_ = 320;
    uint8_t redPalettePhase_ = 0;
    std::array<uint8_t, 8> backdropHeapPadding_{};
    size_t backdropMapTileCount_ = 0;
};

}
