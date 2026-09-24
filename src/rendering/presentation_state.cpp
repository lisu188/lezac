#include "rendering/presentation_state.hpp"
#include "rendering/color.hpp"
#include "resources/palette.hpp"
#include "resources/levels.hpp"
#include <algorithm>
#include <stdexcept>

namespace lezac::rendering {
using resources::vga6To8;

// The original backdrop is a pre-rendered byte buffer (far
// pointer DS:0xC498) blitted under the tiles with a linear copy whose
// source starts at (camY/8 + vy)*pitch + camX/4 -- a 1/8 vertical and
// 1/4 horizontal parallax, with rows bleeding linearly into the next
// buffer row (recovered from the driver blit at file 0x9324 and byte
// dumps of the live buffer). The driver init (file 0x9252) programs DAC
// entries 176..214 with a computed ramp from (0,0,14) and fills the
// buffer with 4-row bands buffer[n] = byte(176 + n/(4*pitch)); the game then paints
// a city skyline (buildings of palette 176 = night blue, star dots of
// palette 22) from the live RNG at each game start (file 0x7f64).
// Pitch is latched at initialization: 320 for P1, 160 for split-screen.
// Later viewport narrowing does not regenerate or repack this buffer.
void PresentationState::buildBackdropBuffer(int playerCount, core::TurboRandom& random) {
    backdropPitch_ = playerCount > 1 ? 160 : 320;
    backdropBuffer_.resize(60000);
    // Driver init fills exactly 60000 bytes, including byte wrap past 255.
    for (int k = 0; k < 60000; ++k) {
        backdropBuffer_[static_cast<size_t>(k)] =
            static_cast<uint8_t>(176 + k / (4 * backdropPitch_));
    }
    // City skyline: the original generates ten buildings from the live
    // Turbo Pascal RNG on each game start (file 0x7f64). Building 1 is
    // the fixed wide base (cols 0..160, top row 130); each of the others
    // rolls Random(120) for its left edge, Random(20) for width-20..39,
    // Random(50)+80 for its top row, is filled down to row 160 with the
    // night colour (176), and gets 20 star dots (palette 22) at
    // Random-picked interior spots. The RNG draw order matches the
    // disassembly exactly; a runtime buffer dump verified the fill and
    // star semantics byte-for-byte.
    auto put = [&](int r, int c, uint8_t v) {
        size_t n = static_cast<size_t>(r) * backdropPitch_ + static_cast<size_t>(c);
        if (n < backdropBuffer_.size()) backdropBuffer_[n] = v;
    };
    for (int b = 1; b <= 10; ++b) {
        int left = random.range(0, 120);
        int width = random.range(0, 20);
        int top = random.range(0, 50) + 80;
        int right = left + 20 + width;
        if (b == 1) {
            left = 0;
            right = 160;
            top = 130;
        }
        for (int r = top; r <= 160; ++r) {
            for (int c = left; c <= right; ++c) put(r, c, 176);
        }
        if (b == 1) continue;
        for (int s = 0; s < 20; ++s) {
            int sr = top + random.range(
                               0, static_cast<uint16_t>(160 - top));
            int sc = left + random.range(
                                0, static_cast<uint16_t>(right - left));
            put(sr, sc, 22);
        }
    }
}

// Palette lookup for backdrop bytes: DAC 176..214 use the driver's
// computed ramp from (0,0,14) -- component j*43/38, j*23/38, 14-j*12/38
// in 6-bit VGA levels -- everything else resolves through BOMPAL.
uint32_t PresentationState::backdropColor(uint8_t idx) const {
    if (idx >= 176 && idx <= 214) {
        const int j = idx - 176;
        const int r6 = j * 43 / 38;
        const int g6 = j * 23 / 38;
        const int b6 = 14 - j * 12 / 38;
        auto up = [](int v) {
            return static_cast<uint32_t>(((v << 2) | (v >> 4)) & 0xff);
        };
        return 0xff000000u | (up(r6) << 16) | (up(g6) << 8) | up(b6);
    }
    return argb(palette_, idx);
}

uint8_t PresentationState::backdropByte(size_t offset, const std::vector<uint8_t>& liveTiles) const {
    // Original far pointer is segment:0008. Tall views overrun its 60000
    // bytes into an 8-byte allocation gap, then the aligned live tile map.
    const size_t address = (offset + 8) & 0xffff;
    if (address < 8) return 0;
    offset = address - 8;
    if (offset < backdropBuffer_.size()) return backdropBuffer_[offset];
    if (offset < 60008) return backdropHeapPadding_[offset - 60000];
    const size_t tile = offset - 60008;
    return tile < liveTiles.size() ? liveTiles[tile] : 0;
}

void PresentationState::updateRedPalette(uint16_t frame) {
    if (frame % 5 != 0) return;
    uint8_t red = redPalettePhase_;
    for (size_t i = 230; i < 236; ++i) {
        palette_[i] = {vga6To8(static_cast<uint8_t>(red & 63)), 0, 0};
        red = static_cast<uint8_t>(red + 7);
        // The writer's signed comparison differs from the unsigned phase update.
        if (red > 63 && red < 128) red = 20;
    }
    redPalettePhase_ = static_cast<uint8_t>(redPalettePhase_ + 7);
    if (redPalettePhase_ > 63) redPalettePhase_ = 20;
}

void PresentationState::resetHudForLevel() {
    hudPaletteQueue_ = {};
    hudColumnReady_ = {};
    hudPreviousCollected_ = 20000;
    hudPreviousDestruction_ = 200;
    hudDestructionPercent_ = 0;
    for (int index : {224, 245, 246}) palette_[index] = initialPalette_[index];
}

void PresentationState::beginOriginalPlay(bool fromMenu) {
    if (fromMenu && !originalPlayInitialized_) {
        std::fill(backdropBuffer_.begin(), backdropBuffer_.end(), 0);
        originalPlayInitialized_ = true;
    }
}

void PresentationState::prepareHudObjectives(uint16_t frame, int collected, int destructionPercent) {
    if ((frame % 30) == 0) hudDestructionPercent_ = destructionPercent;
    if (collected != hudPreviousCollected_) {
        hudPreviousCollected_ = collected;
        hudPaletteQueue_.request(245, {63, 63, 63}, {1, 1, 41});
    }
    if (hudDestructionPercent_ != hudPreviousDestruction_) {
        hudPreviousDestruction_ = hudDestructionPercent_;
        hudPaletteQueue_.request(246, {63, 63, 63}, {1, 1, 41});
    }
}

void PresentationState::updateHudScores(int playerCount, const std::array<uint32_t, 2>& scores,
                                       const std::array<bool, 2>& dead, const std::array<int, 2>& deathTimers) {
    for (int i = 0; i < playerCount; ++i) {
        hudScores_[i].setValue(scores[i]);
        if (dead[i] && deathTimers[i] == 0) continue;
        hudScores_[i].advance();
        hudColumnReady_[i] = true;
    }
}

void PresentationState::advanceHudPalette() {
    hudPaletteQueue_.advance([&](uint8_t index, const std::array<uint8_t, 3>& color) {
        palette_[index] = {vga6To8(color[0] & 63), vga6To8(color[1] & 63), vga6To8(color[2] & 63)};
    });
}

void PresentationState::beginLevel(size_t mapTileCount) {
    // Preserve the original heap alignment gap across map replacement.
    if (backdropMapTileCount_ != 0) {
        const size_t rounded = (backdropMapTileCount_ + 23) & ~size_t(7);
        backdropHeapPadding_[4] = static_cast<uint8_t>(rounded & 15);
        backdropHeapPadding_[6] = static_cast<uint8_t>(rounded >> 4);
        backdropHeapPadding_[7] = static_cast<uint8_t>(rounded >> 12);
    }
    backdropMapTileCount_ = mapTileCount;
}

std::vector<uint8_t> PresentationState::decodeLevelPlane(const std::vector<uint8_t>& encoded, size_t outputSize) {
    if (backdropBuffer_.size() != 60000 || encoded.size() > backdropBuffer_.size()) {
        throw std::runtime_error("level decoder background buffer bounds");
    }
    std::copy(encoded.begin(), encoded.end(), backdropBuffer_.begin());
    return resources::decodeLevelRle3(backdropBuffer_, outputSize);
}

void PresentationState::writeBackdropPrefix(const std::vector<uint8_t>& bytes) {
    if (bytes.size() > backdropBuffer_.size()) throw std::runtime_error("backdrop prefix exceeds buffer");
    std::copy(bytes.begin(), bytes.end(), backdropBuffer_.begin());
}

PresentationSnapshot PresentationState::snapshot() const {
    return {palette_, backdropBuffer_, backdropPitch_, redPalettePhase_, backdropHeapPadding_, backdropMapTileCount_,
            initialPalette_, hudScores_, hudPaletteQueue_, hudColumnReady_, hudPreviousCollected_,
            hudPreviousDestruction_, hudDestructionPercent_, originalPlayInitialized_};
}

void PresentationState::restore(const PresentationSnapshot& state) {
    palette_ = state.palette;
    backdropBuffer_ = state.backdrop;
    backdropPitch_ = state.pitch;
    redPalettePhase_ = state.redPhase;
    backdropHeapPadding_ = state.heapPadding;
    backdropMapTileCount_ = state.mapTileCount;
    initialPalette_ = state.initialPalette;
    hudScores_ = state.hudScores;
    hudPaletteQueue_ = state.hudPaletteQueue;
    hudColumnReady_ = state.hudColumnReady;
    hudPreviousCollected_ = state.hudPreviousCollected;
    hudPreviousDestruction_ = state.hudPreviousDestruction;
    hudDestructionPercent_ = state.hudDestructionPercent;
    originalPlayInitialized_ = state.originalPlayInitialized;
}

}
