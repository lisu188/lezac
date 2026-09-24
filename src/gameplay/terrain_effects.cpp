#include "gameplay/terrain_effects.hpp"
#include "gameplay/motion_math.hpp"
#include "core/progress.hpp"
#include <cmath>

namespace lezac::gameplay {
using namespace lezac::core;
using detail::clampI16;
using detail::integrateAxis8_8;

DamagePhaseLookup TerrainEffects::resolveDamagePhase(uint16_t flaggedWord, bool reverse) const {
        if ((flaggedWord & kDamagedWordBit) == 0) return {};
        uint16_t key = static_cast<uint16_t>(flaggedWord & ~kDamagedWordBit);
        if (key >= kDeferredThreshold) {
            for (size_t i = state_.debrisQueue_.size(); i > 0; --i) {
                const DebrisRecord& record = state_.debrisQueue_[i - 1];
                if (record.flaggedWord == flaggedWord) {
                    return {static_cast<int>(i),
                            static_cast<uint8_t>(reverse ? record.velocityY
                                                         : record.velocityX),
                            true};
                }
            }
            return {};
        }
        for (size_t i = state_.collapseQueue_.size(); i > 0; --i) {
            const CollapseRecord& record = state_.collapseQueue_[i - 1];
            if (record.flaggedWord == flaggedWord) {
                return {static_cast<int>(i),
                        reverse ? record.reversePhase : record.forwardPhase, false};
            }
        }
        return {};
    }

uint8_t TerrainEffects::explosionDispatcherState(int visualSelector) const {
        return static_cast<uint8_t>(std::clamp(visualSelector + 3, 4, 7));
    }

int TerrainEffects::explosionEffectTicks(int visualType) const {
        switch (visualType) {
            case 1: return 8;
            case 2: return 9;
            case 3: return 9;
            case 4: return 0x3a;
        }
        return 8;
    }

uint8_t TerrainEffects::explosionVariantByte(int visualType) const {
        switch (visualType) {
            case 1: return 5;
            case 2: return 5;
            case 3: return 3;
            case 4: return 0x0a;
        }
        return 5;
    }

uint16_t TerrainEffects::explosionSoundOffset(int visualType) const {
        if (visualType >= 1 &&
            visualType <= static_cast<int>(kExplosionDirectSweepSoundOffsets.size())) {
            return kExplosionDirectSweepSoundOffsets[static_cast<size_t>(visualType - 1)];
        }
        return kExplosionDirectSweepSoundOffsets[0];
    }

uint8_t TerrainEffects::explosionSoundSelector(int visualType) const {
        if (visualType >= 1 &&
            visualType <= static_cast<int>(kExplosionSoundSelectors.size())) {
            return kExplosionSoundSelectors[static_cast<size_t>(visualType - 1)];
        }
        return kExplosionSoundSelectors[0];
    }
void TerrainEffects::queueTileDamage(Level& level, int tx, int ty, uint8_t forwardPhase, uint8_t reversePhase, bool preserveCollapseGlyphs) {
        if (tx < 0 || ty < 0 || tx >= level.width || ty >= level.height) return;
        size_t start = static_cast<size_t>(ty) * level.width + tx;
        if (start >= level.wordLayer.size()) return;
        uint16_t word = level.wordLayer[start];
        if (word == 0 || (word & kDamagedWordBit) != 0) return;

        if (word >= kDeferredThreshold) {
            // Debris branch 374C..37F4: flags the word (3770/3780), copies the
            // object byte into the record (37B8/37BE) but never writes the
            // object plane — the glyph stays put until the fragment's first
            // move (CONFIRMED by the L2 capture; the earlier markDamagedTile
            // call here was unfaithful). Cap check 3753: refuse once slot
            // index base + record count reaches 0x640.
            uint8_t lookup = level.tiles[start] & 0xff;
            uint16_t flaggedWord = static_cast<uint16_t>(word | kDamagedWordBit);
            // The word is flagged (3770/3780) only after the cap check passes
            // (3753 jumps straight to the failure return when full).
            if (kDebrisRecordIndexBase + state_.debrisQueue_.size() < kDebrisCapacity) {
                level.wordLayer[start] = flaggedWord;
                DebrisRecord record;
                record.tileIndex = static_cast<int>(start);
                record.flaggedWord = flaggedWord;
                record.velocityX = static_cast<int8_t>(forwardPhase);
                record.velocityY = static_cast<int8_t>(reversePhase);
                record.lookup = lookup;
                state_.debrisQueue_.push_back(record);
            }
            return;
        }

        if (state_.collapseQueue_.size() >= kCollapseCapacity) return;
        std::vector<size_t> stack{start};
        std::vector<size_t> group;
        while (!stack.empty()) {
            size_t index = stack.back();
            stack.pop_back();
            if (index >= level.wordLayer.size() || level.wordLayer[index] != word) continue;
            level.wordLayer[index] = static_cast<uint16_t>(word | kDamagedWordBit);
            group.push_back(index);

            int x = static_cast<int>(index % static_cast<size_t>(level.width));
            int y = static_cast<int>(index / static_cast<size_t>(level.width));
            auto pushNeighbor = [&](int nx, int ny) {
                if (nx < 0 || ny < 0 || nx >= level.width || ny >= level.height) return;
                size_t next = static_cast<size_t>(ny) * level.width + nx;
                if (next < level.wordLayer.size() && level.wordLayer[next] == word) {
                    stack.push_back(next);
                }
            };
            pushNeighbor(x + 1, y);
            pushNeighbor(x - 1, y);
            pushNeighbor(x, y + 1);
            pushNeighbor(x, y - 1);
        }

        int minX = level.width;
        int minY = level.height;
        int maxX = 0;
        int maxY = 0;
        for (size_t index : group) {
            int x = static_cast<int>(index % static_cast<size_t>(level.width));
            int y = static_cast<int>(index / static_cast<size_t>(level.width));
            minX = std::min(minX, x);
            minY = std::min(minY, y);
            maxX = std::max(maxX, x);
            maxY = std::max(maxY, y);
            if (!preserveCollapseGlyphs && level.tiles[index] != level.objectiveTile) level.tiles[index] = 1;
        }
        if (!group.empty() && state_.collapseQueue_.size() < kCollapseCapacity) {
            CollapseRecord record;
            record.x = tx;
            record.y = ty;
            record.startOffsetBytes = static_cast<uint16_t>((minY * level.width + minX) * 2);
            record.endOffsetBytes = static_cast<uint16_t>((maxY * level.width + maxX) * 2);
            record.word = word;
            record.flaggedWord = static_cast<uint16_t>(word | kDamagedWordBit);
            record.forwardPhase = forwardPhase;
            record.reversePhase = reversePhase;
            int signedForward = static_cast<int>(static_cast<int8_t>(forwardPhase));
            int signedReverse = static_cast<int>(static_cast<int8_t>(reversePhase));
            record.argMagnitude = static_cast<uint16_t>(std::abs(signedForward) +
                                                        std::abs(signedReverse));
            record.affectedBytes = static_cast<uint8_t>((group.size() * 2) & 0xff);
            record.count = static_cast<int>(group.size());
            state_.collapseQueue_.push_back(record);
        }
    }

void TerrainEffects::expireVisualEffects() {
        for (Flash& f : state_.flashes_) --f.timer;
        state_.flashes_.erase(std::remove_if(state_.flashes_.begin(), state_.flashes_.end(),
                                      [](const Flash& f) { return f.timer <= 0; }),
                       state_.flashes_.end());
        for (ExplosionEffect& e : state_.explosionEffects_) --e.timer;
        state_.explosionEffects_.erase(std::remove_if(state_.explosionEffects_.begin(), state_.explosionEffects_.end(),
                                               [](const ExplosionEffect& e) { return e.timer <= 0; }),
                                state_.explosionEffects_.end());
}

void TerrainEffects::updateCameraShake(core::TurboRandom& random) {
        // 1000:806A..8091 advances once per game frame, never per render.
        if (state_.cameraShakeTicks_ == 0) return;
        state_.cameraShakeOffset_ = random.range(0, static_cast<uint16_t>(state_.cameraShakeTicks_ * 2));
        if (--state_.cameraShakeTicks_ == 0) state_.cameraShakeOffset_ = 0;
    }
}
