#pragma once

#include "core/random.hpp"
#include "core/hud.hpp"
#include "gameplay/actor_models.hpp"
#include "rendering/hud_ammo.hpp"
#include "resources/types.hpp"
#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace lezac::resources {
struct DecodedLevelPlane;
}

namespace lezac::rendering {
class Canvas;

struct PresentationSnapshot {
    resources::Palette palette{};
    std::vector<uint8_t> backdrop;
    int pitch = 320;
    uint8_t redPhase = 0;
    std::array<uint8_t, 8> heapPadding{};
    size_t mapTileCount = 0;
    resources::Palette initialPalette{};
    std::array<core::HudScoreReel, 2> hudScores{};
    std::array<core::HudEnergyBar, 2> hudEnergy{};
    std::array<HudAmmoPanel, 2> hudAmmoPanels{};
    core::HudPaletteQueue hudPaletteQueue{};
    std::array<bool, 2> hudColumnReady{};
    int hudPreviousCollected = 20000;
    int hudPreviousDestruction = 200;
    int hudDestructionPercent = 0;
    bool originalPlayInitialized = false;
    bool hudBonusComplete = false;
    bool hudDestructionComplete = false;
    std::vector<uint32_t> outroBackdrop;
    std::vector<uint8_t> outroIndices;
    std::vector<uint8_t> outroIndexedPixels;
};

class PresentationState {
public:
    const resources::Palette& palette() const { return palette_; }
    const std::vector<uint8_t>& backdropBuffer() const { return backdropBuffer_; }
    int backdropPitch() const { return backdropPitch_; }
    uint8_t redPalettePhase() const { return redPalettePhase_; }
    void setPalette(const resources::Palette& palette) { palette_ = palette; }
    void initializeBackdropBuffer(int playerCount);
    void buildBackdropBuffer(int playerCount, core::TurboRandom& random);
    void beginLevel(size_t mapTileCount);
    std::vector<uint8_t> decodeLevelPlane(const std::vector<uint8_t>& encoded, size_t outputSize);
    resources::DecodedLevelPlane decodeLevelPlaneWithTail(const std::vector<uint8_t>& encoded, size_t outputSize);
    void updateRedPalette(uint16_t frame);
    void captureInitialPalette() { initialPalette_ = palette_; }
    void resetHudObjectivesForLevel();
    void resetHudForLevel();
    void clearHudScores() { hudScores_ = {}; }
    void beginOriginalPlay(bool fromMenu);
    void prepareHudObjectives(uint16_t frame, int collected, int destructionPercent,
                              int requiredBonus, int requiredDestruction);
    void updateHudScores(int playerCount, const std::array<uint32_t, 2>& scores,
                         const std::array<bool, 2>& dead, const std::array<int, 2>& deathTimers);
    void updateHudEnergy(size_t player, uint16_t value, uint8_t globalState);
    void sampleHudInventory(size_t player, gameplay::BombInventory& inventory, uint8_t globalState);
    void advanceHudPalette();
    void beginResultScore(size_t player, uint32_t value);
    void advanceResultScore(size_t player);
    void freezeOutroBackdrop(const Canvas& canvas);
    std::vector<uint32_t> resolveOutroBackdrop() const;
    const std::vector<uint32_t>& outroBackdrop() const { return outroBackdrop_; }
    const std::array<core::HudScoreReel, 2>& hudScores() const { return hudScores_; }
    const std::array<core::HudEnergyBar, 2>& hudEnergy() const { return hudEnergy_; }
    const std::array<HudAmmoPanel, 2>& hudAmmoPanels() const { return hudAmmoPanels_; }
    const core::HudPaletteQueue& hudPaletteQueue() const { return hudPaletteQueue_; }
    const std::array<bool, 2>& hudColumnReady() const { return hudColumnReady_; }
    int hudPreviousCollected() const { return hudPreviousCollected_; }
    int hudPreviousDestruction() const { return hudPreviousDestruction_; }
    int hudDestructionPercent() const { return hudDestructionPercent_; }
    bool hudBonusComplete() const { return hudBonusComplete_; }
    bool hudDestructionComplete() const { return hudDestructionComplete_; }
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
    std::array<core::HudEnergyBar, 2> hudEnergy_{};
    std::array<HudAmmoPanel, 2> hudAmmoPanels_{};
    core::HudPaletteQueue hudPaletteQueue_{};
    std::array<bool, 2> hudColumnReady_{};
    int hudPreviousCollected_ = 20000;
    int hudPreviousDestruction_ = 200;
    int hudDestructionPercent_ = 0;
    bool originalPlayInitialized_ = false;
    bool hudBonusComplete_ = false;
    bool hudDestructionComplete_ = false;
    std::vector<uint32_t> outroBackdrop_;
    std::vector<uint8_t> outroIndices_;
    std::vector<uint8_t> outroIndexedPixels_;
    std::vector<uint8_t> backdropBuffer_;
    int backdropPitch_ = 320;
    uint8_t redPalettePhase_ = 0;
    std::array<uint8_t, 8> backdropHeapPadding_{};
    size_t backdropMapTileCount_ = 0;
};

}
