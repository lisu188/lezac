#pragma once
#include <SDL.h>
#include <cstdint>
#include <vector>

namespace lezac::sound {

// Owns the queued SDL device; logical latch state remains in SoundEngine.
class SdlAudioOutput {
public:
    SdlAudioOutput() = default;
    ~SdlAudioOutput();
    SdlAudioOutput(const SdlAudioOutput&) = delete;
    SdlAudioOutput& operator=(const SdlAudioOutput&) = delete;
    void open();
    void close() noexcept;
    bool enabled() const { return audioEnabled_ && audioDevice_ != 0; }
    void playSamples(const std::vector<int16_t>& samples);
    void playClockedSamples(const std::vector<int16_t>& samples);
    void discardClockedSamples();
    Uint32 queuedBytes() const;
    uint64_t droppedClockedBytes() const { return droppedClockedBytes_; }
private:
    void queueAudio(const void* data, Uint32 bytes);
    SDL_AudioDeviceID audioDevice_ = 0;
    SDL_AudioSpec audioSpec_{};
    bool audioEnabled_ = false;
    bool clockedPrimed_ = false;
    uint64_t droppedClockedBytes_ = 0;
};

}  // namespace lezac::sound
