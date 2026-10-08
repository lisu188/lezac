#pragma once
#include "sound/sound_models.hpp"
#include <vector>

namespace lezac::sound {

// The recovered sound latch and synthesis state have no SDL dependency.
// The bank must outlive the engine; loading may replace its value in place.
class SoundEngine {
public:
    explicit SoundEngine(const resources::SoundBank& sounds) : sounds_(sounds) {}
    const resources::SoundBank& bank() const { return sounds_; }
    SoundLatch latch() const { return soundLatch_; }
    SoundInterruptState interruptState() const { return soundInterrupt_; }
    SoundClockState clockState() const { return soundClock_; }
    SpeakerToneState speakerState() const { return speaker_; }
    SoundPlaybackSnapshot lastPumped() const {
        return {lastPumpedSoundRecord_, lastPumpedSoundOffset_, lastPumpedSoundSelector_};
    }
    const std::vector<CompatibilitySoundAttempt>& compatibilityAttempts() const {
        return compatibilitySoundAttempts_;
    }
    void setCompatibilityTracing(bool enabled) { traceCompatibilitySoundAttempts_ = enabled; }
    void clearCompatibilityAttempts() { compatibilitySoundAttempts_.clear(); }
    // Explicit replay operations preserve existing diagnostic seed boundaries.
    void restoreLatchForFixture(SoundLatch latch) { soundLatch_ = latch; }
    void restoreInterruptForFixture(SoundInterruptState state) { soundInterrupt_ = state; }
    void restorePlaybackForFixture(SoundPlaybackSnapshot playback) {
        lastPumpedSoundRecord_ = playback.record;
        lastPumpedSoundOffset_ = playback.offset;
        lastPumpedSoundSelector_ = playback.selector;
    }
    uint16_t compatibilitySoundCursor(size_t index) const;
    uint16_t soundStepPeriodWord(size_t stepIndex) const;
    uint8_t soundStepGateTick(size_t stepIndex) const;
    uint8_t soundStepPeriodTicks(size_t stepIndex) const;
    uint16_t soundStopCursorFor(uint16_t cursor) const;
    static uint16_t speakerDivisorForFrequency(uint16_t frequency);
    void appendToneSamples(std::vector<int16_t>& samples, uint16_t frequency,
                       int sampleCount, int amplitude, SpeakerToneState& tone) const;
    std::vector<int16_t> synthesizeSoundCursor(uint16_t cursor) const;
    std::vector<int16_t> synthesizeSound(size_t index) const;
    std::vector<int16_t> synthesizeDirectSweep(uint16_t startCursor) const;
    size_t soundIndexForSelector(uint8_t selector) const;
    bool isDirectSoundSweep(uint16_t offset) const;
    size_t soundIndexForOffsetFallback(uint16_t offset, uint8_t selector) const;
    bool latchSoundRequest(uint16_t cursor, uint8_t selector);
    bool requestSoundCursor(uint16_t cursor, uint8_t selector);
    bool requestSoundOffset(uint16_t offset, uint8_t selector);
    // One original INT 1Ch transition. Host scheduling is deliberately separate.
    SoundInterruptAction advanceSoundInterrupt();
    // Persistent default BIOS-clock playback; no SDL or gameplay-tick dependency.
    std::vector<int16_t> renderClockedSamples(size_t sampleCount);
    void clearSoundLatch();
    bool playCompatibilitySound(size_t hookSlot);
    std::vector<int16_t> pumpSoundLatch();
    std::vector<int16_t> playSound(size_t index, bool outputEnabled);

private:
    const resources::SoundBank& sounds_;
    SoundLatch soundLatch_;
    SoundInterruptState soundInterrupt_;
    SoundClockState soundClock_;
    SpeakerToneState speaker_;
    int lastPumpedSoundRecord_ = -1;
    uint16_t lastPumpedSoundOffset_ = 0;
    uint8_t lastPumpedSoundSelector_ = 0;
    bool traceCompatibilitySoundAttempts_ = false;
    std::vector<CompatibilitySoundAttempt> compatibilitySoundAttempts_;
};

}  // namespace lezac::sound
