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
private:
    void queueAudio(const void* data, Uint32 bytes);
    SDL_AudioDeviceID audioDevice_ = 0;
    SDL_AudioSpec audioSpec_{};
    bool audioEnabled_ = false;
};

}  // namespace lezac::sound
