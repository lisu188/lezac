#include "rendering/world_raster.hpp"

#include "core/frame_render.hpp"
#include "gameplay/map_plane_memory.hpp"
#include "rendering/canvas.hpp"
#include "rendering/color.hpp"
#include "rendering/presentation_state.hpp"

#include <algorithm>
#include <stdexcept>
#include <string>

namespace lezac::rendering {

WorldRaster::SpritePixels::SpritePixels(const resources::SpriteBank& bank) {
    for (const auto& sprite : bank.sprites) {
        if (sprite.width <= 0 || sprite.width > 255 || sprite.height <= 0 || sprite.height > 255 ||
                sprite.pixels.size() != static_cast<size_t>(sprite.width * sprite.height) ||
                pixels.size() + sprite.pixels.size() >= 65536)
            throw std::invalid_argument("World raster sprite bank differs");
        const auto offset = static_cast<uint16_t>(pixels.size());
        descriptors.push_back({static_cast<uint8_t>(sprite.width), static_cast<uint8_t>(sprite.height),
            static_cast<uint8_t>(offset), static_cast<uint8_t>(offset >> 8)});
        pixels.insert(pixels.end(), sprite.pixels.begin(), sprite.pixels.end());
    }
    blank = static_cast<uint16_t>(pixels.size());
    pixels.push_back(0);
}

WorldRaster::WorldRaster(const resources::AssetCatalog& assets)
    : assets_(assets) {}

void WorldRaster::initializeAssets() {
    if (assetsReady_) return;
    const auto& pixels = assets_.tiles().pixels;
    if (assets_.tiles().count != 132 || pixels.size() != 132 * 64)
        throw std::invalid_argument("World raster tile bank differs");
    normal_ = SpritePixels(assets_.sprites());
    alternate_ = SpritePixels(assets_.altSprites());
    for (size_t index = 0; index < pixels.size(); ++index) {
        byte(static_cast<uint16_t>(TileBase + index), pixels[index]);
        byte(static_cast<uint16_t>(TileBase + MaskDelta + index), pixels[index] ? 0 : 255);
    }
    assetsReady_ = true;
}

void WorldRaster::byte(uint16_t offset, uint8_t value) {
    data_[offset] = value;
    defined_.set(offset);
}
void WorldRaster::word(uint16_t offset, uint16_t value) {
    byte(offset, static_cast<uint8_t>(value));
    byte(static_cast<uint16_t>(offset + 1), static_cast<uint8_t>(value >> 8));
}
void WorldRaster::visual(size_t row, int x, int y, const gameplay::ActorStorage::Descriptor& value) {
    if (row >= 32) throw std::out_of_range("World raster visual pool exceeds original capacity");
    const auto at = static_cast<uint16_t>(0xc21e + row * 8);
    word(at, static_cast<uint16_t>(x));
    word(static_cast<uint16_t>(at + 2), static_cast<uint16_t>(y));
    for (size_t i = 0; i < value.size(); ++i) byte(static_cast<uint16_t>(at + 4 + i), value[i]);
}
gameplay::ActorStorage::Descriptor WorldRaster::descriptor(size_t index) const {
    if (index >= sprites_->descriptors.size())
        throw std::out_of_range("World raster sprite descriptor differs");
    return sprites_->descriptors[index];
}

void WorldRaster::prepare(const WorldRenderView& world, const PresentationState& presentation, int pitch) {
    initializeAssets();
    if (!world.seededDiagnostic && (!world.mapMemory || !world.physicalVisuals))
        throw std::invalid_argument("Production world raster requires live map and physical visual owners");
    if (world.playerCount < 1 || world.playerCount > 2 || pitch < 160 || pitch > 320 || pitch % 8 ||
            world.level.width <= 0 || world.level.height <= 0)
        throw std::invalid_argument("World raster geometry differs");
    sprites_ = world.levelIndex == 6 || normal_.descriptors.empty() ? &alternate_ : &normal_;
    physical_ = world.physicalVisuals;
    const int center = ((pitch / 8 - 2) / 2) * 8;
    struct Word { uint16_t offset, value; };
    for (const auto& [offset, value] : std::array<Word, 20>{{
            {0x1afa,0x200},{0x78bc,static_cast<uint16_t>(center)}, {0x78be,static_cast<uint16_t>(center/8)},
            {0x2094,static_cast<uint16_t>((world.level.width-pitch/8)*8)},
            {0x2096,static_cast<uint16_t>((world.level.height-21)*8)},{0x2098,world.cameraShakeOffset},
            {0xc1ea,static_cast<uint16_t>(pitch/8)},{0xc1ec,static_cast<uint16_t>(pitch)},{0xc1ee,160},
            {0xc1f6,static_cast<uint16_t>(presentation.backdropPitch()-pitch)},
            {0xc1f8,static_cast<uint16_t>(presentation.backdropPitch())},{0xc1fa,Sprites},{0xc1fe,Map},
            {0xc204,static_cast<uint16_t>(world.level.width)},{0xc206,static_cast<uint16_t>(320-pitch)},
            {0xc208,TileBase},{0xc212,Buffer},{0xc214,8},{0xc498,8},{0xc49a,Backdrop}}})
        word(offset, value);
    byte(0xc49c, world.showBackground && !presentation.backdropBuffer().empty() ? 1 : 0);
    for (size_t i = 0; i < 2; ++i) {
        const auto& view = world.players[i];
        const bool visible = i < static_cast<size_t>(world.playerCount) &&
            (!view.dead || (view.lives >= 0 && view.state2Cursor.active));
        auto image = visible ? descriptor(view.player.spriteIndex) : gameplay::ActorStorage::Descriptor{
            1,1,static_cast<uint8_t>(sprites_->blank),static_cast<uint8_t>(sprites_->blank>>8)};
        if (visible && view.player.singlePixelSprite) { image[0] = 1; image[1] = 1; }
        visual(i, static_cast<int>(view.player.x), static_cast<int>(view.player.y), image);
        byte(static_cast<uint16_t>(0x79e6+i), i < static_cast<size_t>(world.playerCount) ? view.globalState : 0);
    }
    size_t count = 2;
    if (physical_) {
        if (physical_->count > gameplay::ActorStorage::capacity || physical_->visualCount != physical_->count + 2)
            throw std::invalid_argument("World raster physical visual count differs");
        count = physical_->visualCount;
    } else {
        // Explicitly seeded standalone views have no physical actor owner.
        for (const auto& entry : world.visualOrder) {
            int x = 0, y = 0;
            size_t sprite = 0;
            switch (entry.kind) {
            case gameplay::SharedActorKind::Bomb: {
                const auto& actor = world.bombs.at(entry.index);
                x = actor.moving ? actor.pixelX : actor.x*8;
                y = actor.moving ? actor.pixelY : actor.y*8;
                sprite = gameplay::bombProfile(actor.type).spriteBase;
                break;
            }
            case gameplay::SharedActorKind::Monster: {
                const auto& actor = world.monsters.at(entry.index);
                if (!actor.alive) continue;
                x = actor.x; y = static_cast<int16_t>(actor.y + actor.hotspotY);
                sprite = actor.behavior == 2 && !actor.bossDebris ? actor.corpseSprite : actor.animFrame;
                break;
            }
            case gameplay::SharedActorKind::Reward: {
                const auto& actor = world.bonusDrops.at(entry.index);
                x = static_cast<int>(actor.x); y = static_cast<int>(actor.y);
                sprite = static_cast<size_t>(gameplay::bonusSpriteIndex(actor.type));
                break;
            }
            case gameplay::SharedActorKind::Effect: {
                const auto& actor = world.transientActors.at(entry.index);
                x = actor.x; y = actor.y; sprite = actor.spriteIndex;
                break;
            }
            case gameplay::SharedActorKind::Marker: {
                const auto& actor = world.launchPadMarkers.at(entry.index);
                x = actor.x; y = actor.y; sprite = static_cast<size_t>(actor.frame-1);
                break;
            }
            }
            visual(count++, x, y, descriptor(sprite));
        }
    }
    byte(0xc496, static_cast<uint8_t>(count));
    stack_.fill(0);
}

uint8_t WorldRaster::read(uint16_t segment, uint32_t offset, const WorldRenderView& world,
                          const PresentationState& presentation, const Canvas& canvas) const {
    if (offset > 65536) throw std::out_of_range("World raster word exceeds adjacent byte");
    if (segment == Data) {
        if (physical_ && offset >= 0xc22e && offset < 0xc21e + physical_->visualCount*8u)
            return physical_->visuals[(offset-0xc21e)/8][(offset-0xc21e)%8];
        if (!defined_[offset])
            throw std::out_of_range("World raster reached unrecovered data byte " + std::to_string(offset));
        return data_[offset];
    }
    if (segment == Stack) {
        if (offset < 0x3f80 || offset >= 0x4000) throw std::out_of_range("World raster left owned stack");
        return stack_[offset-0x3f80];
    }
    if (segment == Buffer) return buffer_[offset];
    if (segment == Map) {
        if (world.mapMemory) return world.mapMemory->readObjectAddress(offset, world.level.tiles, world.level.wordLayer);
        return offset < world.level.tiles.size() ? world.level.tiles[offset] : 0;
    }
    if (segment == Backdrop)
        return presentation.backdropAddress(offset, world.level.tiles, world.level.wordLayer, world.mapMemory);
    if (segment == Sprites) {
        if (offset >= sprites_->pixels.size()) throw std::out_of_range("World raster reached unrecovered sprite heap byte");
        return sprites_->pixels[offset];
    }
    if (segment == 0xa000)
        return offset < 64000 ? canvas.paletteIndices()[offset] : overscan_[offset-64000];
    throw std::out_of_range("World raster read an unowned segment");
}

void WorldRaster::write(uint16_t segment, uint32_t offset, uint8_t value,
                        const PresentationState& presentation, Canvas& canvas) {
    if (offset > 65536) throw std::out_of_range("World raster word exceeds adjacent byte");
    if (segment == Data) {
        if (offset < 0xc1e8 || offset >= 0xc21e)
            throw std::out_of_range("World raster wrote outside driver scratch");
        data_[offset] = value; defined_.set(offset);
    } else if (segment == Stack) {
        if (offset < 0x3f80 || offset >= 0x4000) throw std::out_of_range("World raster left owned stack");
        stack_[offset-0x3f80] = value;
    } else if (segment == Buffer) {
        buffer_[offset] = value;
    } else if (segment == 0xa000) {
        if (offset < 64000) {
            const int x = static_cast<int>(offset%320), y = static_cast<int>(offset/320);
            const auto color = presentation.backdropColor(value);
            canvas.indexedPixel(x, y, value, color);
            if (value >= 176 && value <= 214) canvas.pixel(x, y, color);
        } else overscan_[offset-64000] = value;
    } else throw std::out_of_range("World raster wrote an unowned segment");
}

void WorldRaster::execute(const WorldRenderView& world, const PresentationState& presentation, Canvas& canvas) {
    core::TimerIrqBus bus;
    bus.readByte = [&](uint16_t segment, uint16_t offset) { return read(segment,offset,world,presentation,canvas); };
    bus.readWord = [&](uint16_t segment, uint16_t offset) {
        return static_cast<uint16_t>(read(segment,offset,world,presentation,canvas) |
            (uint16_t{read(segment,uint32_t{offset}+1,world,presentation,canvas)}<<8));
    };
    bus.writeByte = [&](uint16_t segment, uint16_t offset, uint8_t value) { write(segment,offset,value,presentation,canvas); };
    bus.writeWord = [&](uint16_t segment, uint16_t offset, uint16_t value) {
        write(segment,offset,static_cast<uint8_t>(value),presentation,canvas);
        write(segment,uint32_t{offset}+1,static_cast<uint8_t>(value>>8),presentation,canvas);
    };
    core::DosGetTimeRegisters registers;
    registers.cs = Game; registers.ds = Data; registers.ss = Stack;
    registers.sp = 0x3fe4; registers.bp = 0x3ffe; registers.ip = 0x7a13;
    core::FrameRenderOperation operation(registers,Game);
    operation.advance(5000000,bus,[](uint16_t requested) { return requested; });
    if (!operation.returned() || operation.snapshot().registers.sp != 0x3fe4)
        throw std::runtime_error("World raster did not return to its owned caller");
    work_ = {operation.snapshot().dispatchedInstructions,operation.snapshot().transferredWords,physical_ != nullptr};
}

void WorldRaster::drawGame(const WorldRenderView& world, const PresentationState& presentation, Canvas& canvas) {
    const auto initial = ViewportLayout::initialize(world.playerCount,world.viewWidth);
    const auto& layout = world.viewportLayout ? *world.viewportLayout : initial;
    prepare(world,presentation,layout.pitch);
    word(0x79f0,static_cast<uint16_t>(1284+layout.left[0]));
    word(0x79f2,static_cast<uint16_t>(1284+layout.left[1]));
    execute(world,presentation,canvas);
}

void WorldRaster::drawView(const WorldRenderView& world, const gameplay::Player& camera,
                           int x, int y, int width, int height,
                           const PresentationState& presentation, Canvas& canvas) {
    if (height != 152) throw std::invalid_argument("World raster view height differs");
    prepare(world,presentation,width+8);
    word(0xc21e,static_cast<uint16_t>(static_cast<int>(camera.x)));
    word(0xc220,static_cast<uint16_t>(static_cast<int>(camera.y)));
    byte(0x79e6,1); byte(0x79e7,0);
    word(0x79f0,static_cast<uint16_t>(y*320+x));
    execute(world,presentation,canvas);
}

} // namespace lezac::rendering
