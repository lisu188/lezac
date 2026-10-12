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

uint16_t SoundEngine::speakerDivisorForFrequency(uint16_t frequency) {
    // Original 084a:02c9: DX:AX=0x0012:34dd, BX=frequency; <=18 does no I/O.
    return frequency <= 0x12 ? 0 : static_cast<uint16_t>(0x1234ddUL / frequency);
}

void SoundEngine::appendToneSamples(std::vector<int16_t>& samples, uint16_t frequency,
                       int sampleCount, int amplitude, SpeakerToneState& tone) const {
    if (sampleCount <= 0) return;
    const uint16_t divisor = speakerDivisorForFrequency(frequency);
    if (divisor != 0) {
        tone.divisor = divisor;
        tone.enabled = true;
    }
    if (!tone.enabled || tone.divisor == 0) {
        samples.insert(samples.end(), static_cast<size_t>(sampleCount), 0);
        return;
    }
    const double step = 1193182.0 /
        (static_cast<double>(tone.divisor) * static_cast<double>(kAudioSampleRate));
    for (int i = 0; i < sampleCount; ++i) {
        tone.phase += step;
        if (tone.phase >= 1.0) tone.phase -= std::floor(tone.phase);
        samples.push_back(tone.phase < 0.5 ? static_cast<int16_t>(amplitude)
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
    SpeakerToneState tone;
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
                          7200, tone);
        samples.insert(samples.end(),
                       static_cast<size_t>(silentTicks * kAudioToneSamples), 0);
        if (silentTicks != 0) tone.enabled = false;
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
    SpeakerToneState tone;
    for (uint16_t cursor = startCursor; cursor > kDirectSoundThreshold;
         cursor = static_cast<uint16_t>(cursor - 4)) {
        const uint16_t frequency = static_cast<uint16_t>(cursor - kDirectSoundPeriodBase);
        appendToneSamples(samples, frequency, kAudioToneSamples / 2, 7200, tone);
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
    if (countRequestAttempts_) ++requestAttemptCount_;
    requestCursor_ = cursor;
    requestSelector_ = selector;
    // Original byte DEC followed by CMP/JGE compares signed byte values.
    const uint8_t previous = static_cast<uint8_t>(soundLatch_.currentSelector - 1u);
    bool accept = !soundLatch_.active ||
                  static_cast<uint8_t>(previous ^ 0x80u) <
                      static_cast<uint8_t>(selector ^ 0x80u);
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

SoundInterruptAction SoundEngine::advanceSoundInterrupt() {
    if (!soundLatch_.active) return {};
    if (soundLatch_.latchedOffset > kDirectSoundThreshold) {
        const uint16_t frequency = static_cast<uint16_t>(
            soundLatch_.latchedOffset - kDirectSoundPeriodBase);
        soundLatch_.latchedOffset = static_cast<uint16_t>(soundLatch_.latchedOffset - 4);
        const bool ended = soundLatch_.latchedOffset <= kDirectSoundThreshold;
        if (ended) soundLatch_.active = false;
        return {frequency, true, ended};
    }

    soundInterrupt_.accumulator = static_cast<uint8_t>(soundInterrupt_.accumulator + 1);
    if (soundInterrupt_.accumulator != soundInterrupt_.periodTicks) {
        return {0, false, soundInterrupt_.accumulator == soundInterrupt_.gateTick};
    }

    const size_t index = soundLatch_.latchedOffset;
    if (index >= sounds_.stepCount || index * kSoundStepSize + 3 >= sounds_.payload.size()) {
        throw std::runtime_error("sound interrupt reads outside the recovered bank extent");
    }
    soundLatch_.latchedOffset = static_cast<uint16_t>(soundLatch_.latchedOffset + 1);
    const uint16_t frequency = soundStepPeriodWord(index);
    soundInterrupt_.accumulator = 0;
    if (frequency == kSoundStopPeriod) {
        soundLatch_.active = false;
        soundInterrupt_.periodTicks = 1;
        return {0, false, true};
    }
    soundInterrupt_.gateTick = soundStepGateTick(index);
    soundInterrupt_.periodTicks = soundStepPeriodTicks(index);
    return {frequency, true, false};
}

std::vector<int16_t> SoundEngine::renderClockedSamples(size_t sampleCount) {
    constexpr uint64_t threshold = uint64_t{kAudioSampleRate} * kBiosTimerDivisor;
    std::vector<int16_t> samples;
    samples.reserve(sampleCount);
    while (samples.size() < sampleCount) {
        const uint64_t untilInterrupt =
            (threshold - soundClock_.pitAccumulator + kPitClockRate - 1) / kPitClockRate;
        const size_t count = std::min<size_t>(sampleCount - samples.size(), untilInterrupt);
        appendToneSamples(samples, 0, static_cast<int>(count), 7200, speaker_);
        soundClock_.pitAccumulator += count * uint64_t{kPitClockRate};
        soundClock_.renderedSamples += count;
        if (soundClock_.pitAccumulator < threshold) continue;
        soundClock_.pitAccumulator -= threshold;
        applyClockedInterrupt();
    }
    return samples;
}

void SoundEngine::applyClockedInterrupt() {
    ++soundClock_.interrupts;
    const SoundLatch before = soundLatch_;
    const SoundInterruptAction action = advanceSoundInterrupt();
    if (action.programTone) {
        lastPumpedSoundRecord_ = static_cast<int>(before.recordIndex);
        lastPumpedSoundOffset_ = before.latchedOffset;
        lastPumpedSoundSelector_ = before.currentSelector;
        const uint16_t divisor = speakerDivisorForFrequency(action.frequency);
        if (divisor != 0) {
            speaker_.divisor = divisor;
            speaker_.enabled = true;
        }
    }
    // A terminal direct sweep programs its last tone before disabling it.
    if (action.silence) speaker_.enabled = false;
}

void SoundEngine::advanceSpeakerPhase(uint64_t sampleCount) {
    if (!speaker_.enabled || speaker_.divisor == 0) return;
    double increment = 1193182.0 /
        (static_cast<double>(speaker_.divisor) * static_cast<double>(kAudioSampleRate));
    increment -= std::floor(increment);
    // Modular doubling avoids both a per-sample loop and a large floating
    // product. Skipped PCM is not emitted; accumulated roundoff can differ
    // from repeated sample additions, but the oscillator increment is unchanged.
    while (sampleCount != 0) {
        if (sampleCount & 1) {
            speaker_.phase += increment;
            if (speaker_.phase >= 1.0) speaker_.phase -= 1.0;
        }
        increment *= 2.0;
        if (increment >= 1.0) increment -= 1.0;
        sampleCount >>= 1;
    }
}

uint64_t SoundEngine::skipClockedSamples(uint64_t sampleCount) {
    constexpr uint64_t threshold = uint64_t{kAudioSampleRate} * kBiosTimerDivisor;
    uint64_t visitedInterrupts = 0;
    while (sampleCount != 0) {
        if (!soundLatch_.active) {
            advanceSpeakerPhase(sampleCount);
            // Split the product so even a uint64_t-sized interval cannot
            // overflow before division by the rational clock threshold.
            const uint64_t whole = sampleCount / threshold;
            const uint64_t partial = (sampleCount % threshold) * kPitClockRate + soundClock_.pitAccumulator;
            soundClock_.interrupts += whole * kPitClockRate + partial / threshold;
            soundClock_.pitAccumulator = partial % threshold;
            soundClock_.renderedSamples += sampleCount;
            break;
        }
        const uint64_t untilInterrupt =
            (threshold - soundClock_.pitAccumulator + kPitClockRate - 1) / kPitClockRate;
        const uint64_t count = std::min(sampleCount, untilInterrupt);
        advanceSpeakerPhase(count);
        soundClock_.pitAccumulator += count * kPitClockRate;
        soundClock_.renderedSamples += count;
        sampleCount -= count;
        if (soundClock_.pitAccumulator < threshold) continue;
        soundClock_.pitAccumulator -= threshold;
        applyClockedInterrupt();
        ++visitedInterrupts;
    }
    return visitedInterrupts;
}

std::vector<int16_t> SoundEngine::renderClockedTail(uint64_t sampleCount) {
    if (sampleCount > kMaximumClockedTailSamples) {
        skipClockedSamples(sampleCount - kMaximumClockedTailSamples);
        sampleCount = kMaximumClockedTailSamples;
    }
    return renderClockedSamples(static_cast<size_t>(sampleCount));
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
    // Live playback advances independently through renderClockedSamples().
    return requestSoundCursor(hook.capturedCursor, hook.capturedPriority);
}

std::vector<int16_t> SoundEngine::pumpSoundLatch() {
    // Legacy bounded diagnostic synthesis, never the live clocked path.
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
