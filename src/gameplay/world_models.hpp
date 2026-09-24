#pragma once

#include <array>
#include <vector>
#include <cstdint>
#include <cstddef>
#include <limits>
#include <algorithm>
#include "gameplay/actor_models.hpp"
#include "gameplay/frame_controls.hpp"
#include "gameplay/compatibility_constants.hpp"
#include "resources/types.hpp"
#include "resources/levels.hpp"
#include "sound/sound_models.hpp"

namespace lezac::gameplay {
using namespace lezac::resources;
using namespace lezac::sound;
struct ExplosionEffect {
    int x = 0;
    int y = 0;
    uint8_t visualSelector = 1;
    uint8_t dispatcherState = 4;
    uint8_t slotIndex = 1;
    uint8_t sourceIndex = 0;
    bool inactive = false;
    int timer = 8;
    int totalTimer = 8;
    uint16_t soundOffset = kExplosionDirectSweepSoundOffsets[0];
    uint8_t soundSelector = kExplosionSoundSelectors[0];
    uint8_t seedTicksByte = 8;
    uint8_t detailByte = 0x75;
    uint8_t variantByte = 5;
    int computedX = 0;
    int computedY = 0;
    int finalSignedOffset = 0;
};

struct DebrisRecord {
    int tileIndex = 0;         // +0 u16: cell index (y*width + x)
    uint16_t flaggedWord = 0;  // +2 u16: word | 0x8000 while airborne
    int8_t velocityX = 0;      // +4 s8: vx, 128 sub-units per tile (lane DS:78D2)
    int8_t velocityY = 0;      // +5 s8: vy (lane DS:78D4)
    int8_t subX = 0;           // +6 s8: x sub-accumulator (lane DS:78D3)
    int8_t subY = 0;           // +7 s8: y sub-accumulator (lane DS:78D5)
    uint8_t restTicks = 0;     // +8 u8: no-move ticks; retire when increment reaches 100
    uint8_t lookup = 0;        // +9 u8: carried tile code (objectByte at seed)
    uint8_t aux = 0;           // +A u8: bit 7 = "my move spawned a cascade" (4C19)
};

struct CollapseRecord {
    int x = 0;
    int y = 0;
    uint16_t startOffsetBytes = 0;
    uint16_t endOffsetBytes = 0;
    uint16_t word = 0;
    uint16_t flaggedWord = 0;
    uint8_t forwardPhase = 0;
    uint8_t reversePhase = 0;
    int8_t subX = 0;
    int8_t subY = 0;
    uint8_t flags = 0;
    uint8_t restTicks = 0;
    uint16_t argMagnitude = 0;
    uint8_t affectedBytes = 0;
    int count = 0;
};

struct DamagePhaseLookup {
    int slotIndex = 0;
    uint8_t phase = 0;
    bool debris = false;
};

struct FlameRecord {
    uint16_t cell = 0;
    int8_t vx = 0, vy = 0, subX = 0, subY = 0;
    uint8_t timer = 0, glyph = 0x75, variant = 0, mass = 1;
};

struct SpawnerState {
    int remaining = 0;
    int availableSlots = 0;
    // Live countdown byte (original record +0x1B). MUST stay uint8_t: the
    // original decrements it before any gate (1000:7A9B `dec es:[di+0x1b]`),
    // so a shipped 0 wraps to 255 and the first spawn lands 256 ticks in
    // (capture: cd=0xE5 at frame 28, first walker at frame 257, 1458/1458
    // byte transitions fit the dec-then-reload model).
    uint8_t cooldown = 0;
};

struct BossMotionLink {
    uint8_t targetVisual = 0;
    uint8_t selfVisual = 0;
    uint8_t gain = 0;
    uint8_t mode = 0;
    uint8_t radiusX = 0;
    uint8_t radiusY = 0;
    uint8_t phase = 0;
    int16_t offX = 0;
    int16_t offY = 0;
    int16_t outX = 0;
    int16_t outY = 0;
    int8_t biasY = 0;
};

struct BossHeadEdges {
    bool top = false;
    bool bottom = false;
    bool left = false;
    bool right = false;
};
}
