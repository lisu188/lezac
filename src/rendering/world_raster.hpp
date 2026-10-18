#pragma once

#include "gameplay/actor_storage.hpp"
#include "rendering/render_views.hpp"
#include "resources/asset_catalog.hpp"

#include <array>
#include <bitset>
#include <cstdint>
#include <vector>

namespace lezac::rendering {
class Canvas;
class PresentationState;

struct WorldRasterWork {
    uint64_t dispatchedInstructions = 0;
    uint64_t transferredWords = 0;
    bool physicalVisuals = false;
};

// Persistent driver storage. Live level planes and physical actor visuals are
// borrowed for one draw; they are never serialized into a diagnostic RAM image.
class WorldRaster {
public:
    explicit WorldRaster(const resources::AssetCatalog& assets);
    WorldRaster(const WorldRaster&) = delete;
    WorldRaster& operator=(const WorldRaster&) = delete;
    WorldRaster(WorldRaster&&) = delete;
    WorldRaster& operator=(WorldRaster&&) = delete;
    void drawGame(const WorldRenderView& world, const PresentationState& presentation, Canvas& canvas);
    const WorldRasterWork& lastCompletedWork() const noexcept { return work_; }
    void drawView(const WorldRenderView& world, const gameplay::Player& camera,
                  int x, int y, int width, int height,
                  const PresentationState& presentation, Canvas& canvas);

private:
    struct SpritePixels {
        std::vector<uint8_t> pixels;
        std::vector<gameplay::ActorStorage::Descriptor> descriptors;
        uint16_t blank = 0;
        SpritePixels() = default;
        explicit SpritePixels(const resources::SpriteBank& bank);
    };
    static constexpr uint16_t Game = 0x1000, Data = 0x1aa2, Stack = 0x3000;
    static constexpr uint16_t Map = 0x4800, Buffer = 0x6000, Backdrop = 0x7800, Sprites = 0xd000;
    static constexpr uint16_t TileBase = 0x7f74, MaskDelta = 0x2136;
    const resources::AssetCatalog& assets_;
    bool assetsReady_ = false;
    std::vector<uint8_t> data_ = std::vector<uint8_t>(65537);
    std::bitset<65537> defined_;
    std::vector<uint8_t> buffer_ = std::vector<uint8_t>(65537);
    std::array<uint8_t, 128> stack_{};
    std::array<uint8_t, 1537> overscan_{};
    SpritePixels normal_, alternate_;
    const SpritePixels* sprites_ = nullptr;
    const gameplay::ActorStorage::State* physical_ = nullptr;
    WorldRasterWork work_;

    void byte(uint16_t offset, uint8_t value);
    void word(uint16_t offset, uint16_t value);
    void visual(size_t row, int x, int y, const gameplay::ActorStorage::Descriptor& descriptor);
    gameplay::ActorStorage::Descriptor descriptor(size_t index) const;
    void initializeAssets();
    void prepare(const WorldRenderView& world, const PresentationState& presentation, int pitch);
    void execute(const WorldRenderView& world, const PresentationState& presentation, Canvas& canvas,
                 const gameplay::Player* camera = nullptr);
    uint8_t read(uint16_t segment, uint32_t offset, const WorldRenderView& world,
                 const PresentationState& presentation, const Canvas& canvas) const;
    void write(uint16_t segment, uint32_t offset, uint8_t value,
               const PresentationState& presentation, Canvas& canvas);
};

} // namespace lezac::rendering
