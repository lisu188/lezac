#include "sound/sdl_audio_output.hpp"
#include "sound/sound_models.hpp"
#include <algorithm>
#include <cstring>

namespace lezac::sound {

SdlAudioOutput::~SdlAudioOutput() { close(); }

void SdlAudioOutput::close() noexcept {
    if (audioDevice_ != 0) SDL_CloseAudioDevice(audioDevice_);
    audioDevice_ = 0;
    audioEnabled_ = false;
    audioSpec_ = {};
    clockedPrimed_ = false;
    droppedClockedBytes_ = 0;
}

void SdlAudioOutput::open() {
    close();
    if (SDL_InitSubSystem(SDL_INIT_AUDIO) != 0) {
        SDL_ClearError();
        return;
    }
    SDL_AudioSpec want{};
    want.freq = kAudioSampleRate;
    want.format = AUDIO_S16SYS;
    want.channels = 1;
    want.samples = 1024;
    SDL_AudioSpec have{};
    // SDL performs any hardware conversion continuously, not per small chunk.
    audioDevice_ = SDL_OpenAudioDevice(nullptr, 0, &want, &have, 0);
    if (audioDevice_ == 0) {
        SDL_ClearError();
        return;
    }
    audioSpec_ = have;
    audioEnabled_ = true;
    SDL_PauseAudioDevice(audioDevice_, 0);
}

void SdlAudioOutput::playSamples(const std::vector<int16_t>& samples) {
    if (!audioEnabled_ || audioDevice_ == 0 || samples.empty()) return;
    Uint32 bytes = static_cast<Uint32>(samples.size() * sizeof(int16_t));
    if (audioSpec_.format == AUDIO_S16SYS && audioSpec_.channels == 1 &&
        audioSpec_.freq == kAudioSampleRate) {
        queueAudio(samples.data(), bytes);
        return;
    }

    SDL_AudioCVT cvt{};
    int build = SDL_BuildAudioCVT(&cvt, AUDIO_S16SYS, 1, kAudioSampleRate,
                                  audioSpec_.format, audioSpec_.channels,
                                  audioSpec_.freq);
    if (build < 0) {
        SDL_ClearError();
        return;
    }
    if (build == 0) {
        queueAudio(samples.data(), bytes);
        return;
    }

    cvt.len = static_cast<int>(bytes);
    std::vector<uint8_t> converted(static_cast<size_t>(cvt.len) * cvt.len_mult);
    std::memcpy(converted.data(), samples.data(), bytes);
    cvt.buf = converted.data();
    if (SDL_ConvertAudio(&cvt) != 0) {
        SDL_ClearError();
        return;
    }
    queueAudio(converted.data(), static_cast<Uint32>(cvt.len_cvt));
}

void SdlAudioOutput::queueAudio(const void* data, Uint32 bytes) {
    if (SDL_QueueAudio(audioDevice_, data, bytes) != 0) {
        SDL_ClearError();
        audioEnabled_ = false;
    }
}

Uint32 SdlAudioOutput::queuedBytes() const {
    return audioDevice_ == 0 ? 0 : SDL_GetQueuedAudioSize(audioDevice_);
}

void SdlAudioOutput::playClockedSamples(const std::vector<int16_t>& samples) {
    if (!enabled() || samples.empty()) return;
    constexpr size_t leadSamples = kAudioSampleRate / 20;
    constexpr size_t maximumSamples = kMaximumClockedTailSamples;
    constexpr Uint32 maximumBytes = (leadSamples + maximumSamples) * sizeof(int16_t);
    const size_t count = std::min(samples.size(), maximumSamples);
    const Uint32 bytes = static_cast<Uint32>(count * sizeof(int16_t));
    const Uint32 queued = queuedBytes();
    if (queued + bytes > maximumBytes) {
        discardClockedSamples();
    }
    droppedClockedBytes_ += (samples.size() - count) * sizeof(int16_t);
    if (!clockedPrimed_) {
        // Buffer elapsed PCM behind a short initial lead; do not predict future requests.
        const std::vector<int16_t> silence(leadSamples, 0);
        queueAudio(silence.data(), static_cast<Uint32>(silence.size() * sizeof(int16_t)));
        clockedPrimed_ = true;
    }
    if (enabled()) queueAudio(samples.data() + samples.size() - count, bytes);
}

void SdlAudioOutput::discardClockedSamples() {
    droppedClockedBytes_ += queuedBytes();
    if (audioDevice_ != 0) SDL_ClearQueuedAudio(audioDevice_);
    clockedPrimed_ = false;
}

}  // namespace lezac::sound
