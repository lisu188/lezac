#include "sound/sound_engine.hpp"
#include "resources/binary.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace lezac::sound {
using resources::le16;

uint16_t SoundEngine::compatibilitySoundCursor(size_t index) const {
    return kCompatibilitySoundCursors[index % kCompatibilitySoundCursors.size()];
}

uint16_t SoundEngine::soundStepPeriodWord(size_t stepIndex) const {
    size_t off = stepIndex * kSoundStepSize;
    if (off + 1 >= sounds_.payload.size()) return kSoundStopPeriod;
    return le16(sounds_.payload, off);
}

uint8_t SoundEngine::soundStepGateTick(size_t stepIndex) const {
    size_t off = stepIndex * kSoundStepSize;
    return off + 2 < sounds_.payload.size() ? sounds_.payload[off + 2] : 0;
}

uint8_t SoundEngine::soundStepPeriodTicks(size_t stepIndex) const {
    size_t off = stepIndex * kSoundStepSize;
    return off + 3 < sounds_.payload.size() ? sounds_.payload[off + 3] : 1;
}

uint16_t SoundEngine::soundStopCursorFor(uint16_t cursor) const {
    size_t stepIndex = cursor;
    while (stepIndex < sounds_.stepCount) {
        if (soundStepPeriodWord(stepIndex) == kSoundStopPeriod) {
            return static_cast<uint16_t>(stepIndex + 1);
        }
        ++stepIndex;
    }
    return static_cast<uint16_t>(sounds_.stepCount);
}

void SoundEngine::appendToneSamples(std::vector<int16_t>& samples, uint16_t period,
                       int sampleCount, int amplitude, double& phase) const {
    if (sampleCount <= 0) return;
    if (period < 0x20) {
        samples.insert(samples.end(), static_cast<size_t>(sampleCount), 0);
        return;
    }
    double frequency = std::clamp(1193182.0 / static_cast<double>(period),
                                  80.0, 4200.0);
    double step = frequency / static_cast<double>(kAudioSampleRate);
    for (int i = 0; i < sampleCount; ++i) {
        phase += step;
        if (phase >= 1.0) phase -= std::floor(phase);
        samples.push_back(phase < 0.5 ? static_cast<int16_t>(amplitude)
                                       : static_cast<int16_t>(-amplitude));
    }
}

std::vector<int16_t> SoundEngine::synthesizeSoundCursor(uint16_t cursor) const {
    if (cursor > kDirectSoundThreshold) return synthesizeDirectSweep(cursor);
    std::vector<int16_t> samples;
    if (sounds_.payload.empty() || cursor >= sounds_.stepCount) return samples;

    uint16_t stopCursor = soundStopCursorFor(cursor);
    samples.reserve(static_cast<size_t>(std::max<int>(1, stopCursor - cursor)) *
                    kAudioToneSamples * 2);
    double phase = 0.0;
    for (size_t stepIndex = cursor; stepIndex < sounds_.stepCount; ++stepIndex) {
        uint16_t period = soundStepPeriodWord(stepIndex);
        if (period == kSoundStopPeriod) break;
        uint8_t gateTick = soundStepGateTick(stepIndex);
        uint8_t periodTicksRaw = soundStepPeriodTicks(stepIndex);
        int periodTicks = periodTicksRaw == 0 ? 256 : periodTicksRaw;
        int audibleTicks = periodTicks;
        if (gateTick != 0 && gateTick < periodTicks) {
            audibleTicks = gateTick;
        }
        int silentTicks = std::max(0, periodTicks - audibleTicks);
        appendToneSamples(samples, period,
                          std::max(1, audibleTicks * kAudioToneSamples),
                          7200, phase);
        samples.insert(samples.end(),
                       static_cast<size_t>(silentTicks * kAudioToneSamples), 0);
    }
    return samples;
}

std::vector<int16_t> SoundEngine::synthesizeSound(size_t index) const {
    if (sounds_.records.empty()) return {};
    return synthesizeSoundCursor(compatibilitySoundCursor(index));
}

std::vector<int16_t> SoundEngine::synthesizeDirectSweep(uint16_t startCursor) const {
    std::vector<int16_t> samples;
    if (startCursor <= kDirectSoundThreshold) return samples;
    double phase = 0.0;
    for (uint16_t cursor = startCursor; cursor > kDirectSoundThreshold;
         cursor = static_cast<uint16_t>(cursor - 4)) {
        uint16_t period = static_cast<uint16_t>(cursor - kDirectSoundPeriodBase);
        uint16_t clampedPeriod = std::max<uint16_t>(1, period);
        appendToneSamples(samples, clampedPeriod, kAudioToneSamples / 2, 7200, phase);
    }
    return samples;
}

size_t SoundEngine::soundIndexForSelector(uint8_t selector) const {
    if (sounds_.records.empty()) return 0;
    if (selector >= 4) {
        return static_cast<size_t>(selector - 4) % sounds_.records.size();
    }
    return static_cast<size_t>(selector) % sounds_.records.size();
}

bool SoundEngine::isDirectSoundSweep(uint16_t offset) const {
    return offset > kDirectSoundThreshold;
}

size_t SoundEngine::soundIndexForOffsetFallback(uint16_t offset, uint8_t selector) const {
    if (sounds_.records.empty()) return 0;
    for (size_t i = 0; i < kExplosionDirectSweepSoundOffsets.size(); ++i) {
        if (offset == kExplosionDirectSweepSoundOffsets[i]) {
            return i % sounds_.records.size();
        }
    }
    return soundIndexForSelector(selector);
}

bool SoundEngine::latchSoundRequest(uint16_t cursor, uint8_t selector) {
    bool accept = !soundLatch_.active ||
                  static_cast<uint8_t>(soundLatch_.currentSelector - 1u) < selector;
    if (!accept) return false;
    soundLatch_.active = true;
    soundLatch_.currentSelector = selector;
    soundLatch_.latchedOffset = cursor;
    soundLatch_.directSweep = isDirectSoundSweep(cursor);
    soundLatch_.recordIndex = sounds_.records.empty()
                                  ? 0
                                  : soundIndexForOffsetFallback(cursor, selector);
    return true;
}

bool SoundEngine::requestSoundCursor(uint16_t cursor, uint8_t selector) {
    return latchSoundRequest(cursor, selector);
}

bool SoundEngine::requestSoundOffset(uint16_t offset, uint8_t selector) {
    return requestSoundCursor(offset, selector);
}

void SoundEngine::clearSoundLatch() {
    soundLatch_ = {};
}

bool SoundEngine::playCompatibilitySound(size_t hookSlot) {
    if (hookSlot >= kRemainingSoundCompatibilityHooks.size()) {
        throw std::runtime_error("unknown compatibility sound hook");
    }
    const RemainingSoundCompatibilityHook& hook =
        kRemainingSoundCompatibilityHooks[hookSlot];
    // Submit the captured pair through the recovered priority latch, the
    // same route every other in-game sound callsite uses, instead of
    // queueing samples directly: the pair was sampled from the ACCEPTED
    // words (cursor DS:0x78C0, priority DS:0x799E), and in the original
    // the latch at 1000:165a is the only writer of those words, so the
    // faithful replay is a latch submission whose priority can lose to a
    // louder sound already pending. Cursor and priority both matter here;
    // the index->kCompatibilitySoundCursors lookup is deliberately not
    // used because its level-complete entry is 0x0027 while the original
    // latches 0x003d, an audibly different sound. The table itself is
    // left alone because the selector path and the sound_render
    // diagnostics depend on it.
    if (traceCompatibilitySoundAttempts_) {
        compatibilitySoundAttempts_.push_back({hook.index, hook.capturedCursor});
    }
    // No audio-device early-out: the latch is game state, not audio
    // state, so a headless run must reach the same latch as an audio run.
    // pumpSoundLatch() performs the synthesis once per tick.
    return requestSoundCursor(hook.capturedCursor, hook.capturedPriority);
}

std::vector<int16_t> SoundEngine::pumpSoundLatch() {
    if (!soundLatch_.active) return {};
    size_t recordIndex = soundLatch_.recordIndex;
    lastPumpedSoundRecord_ = static_cast<int>(recordIndex);
    lastPumpedSoundOffset_ = soundLatch_.latchedOffset;
    lastPumpedSoundSelector_ = soundLatch_.currentSelector;
    bool directSweep = soundLatch_.directSweep;
    uint16_t offset = soundLatch_.latchedOffset;
    clearSoundLatch();
    if (directSweep) {
        return synthesizeDirectSweep(offset);
    } else {
        return synthesizeSoundCursor(offset);
    }
}

std::vector<int16_t> SoundEngine::playSound(size_t index, bool outputEnabled) {
    if (traceCompatibilitySoundAttempts_) {
        compatibilitySoundAttempts_.push_back(
            {index, compatibilitySoundCursor(index)});
    }
    if (!outputEnabled || sounds_.records.empty()) return {};
    std::vector<int16_t> samples = synthesizeSound(index % sounds_.records.size());
    if (samples.empty()) return {};
    return samples;
}

}  // namespace lezac::sound
