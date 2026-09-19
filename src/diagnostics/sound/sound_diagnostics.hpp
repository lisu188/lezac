#pragma once
#include "sound/sound_engine.hpp"
#include <string>

namespace lezac::diagnostics {

class SoundDiagnostics {
public:
    explicit SoundDiagnostics(sound::SoundEngine& sound) : sound_(sound) {}
    void debugSounds();
    void debugSoundRender();
    void debugSoundCursorSegments();
    void debugSonRawRoundtrip();
    void debugSoundLoaderStaticModel();
    void debugSonStepFields();
    void debugSonTailFieldMutation();
    void debugSoundTickStaticModel();
    void debugSoundLatchStaticModel();
    void debugSoundPriorityLatch();
    void debugSoundSelectorMap();
    void debugStaticSoundRequests();
    void debugStaticSoundContexts();
    void debugStaticSoundUnresolvedContexts();
    void debugSoundRuntimeCaptureQueue();
    int debugSoundCallsiteOracle(const std::string& path, bool expectError);
    void debugSoundHookEvidence(const std::string& fixturePath);
private:
    static std::string hex4(uint16_t value);
    sound::SoundEngine& sound_;
};

}  // namespace lezac::diagnostics
