"""Keep the recovered clock on live paths, with the legacy pump diagnostic-only."""
from pathlib import Path
from functools import lru_cache

from source_guardrails import function_ranges, mask_cpp


ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=128)
def body(text, name):
    ranges = function_ranges(text, [name])
    if name not in ranges:
        raise RuntimeError(f"missing function {name}")
    first, last = ranges[name]
    return mask_cpp("".join(text.splitlines(keepends=True)[first - 1:last]))


def require(text, name, *snippets):
    function = body(text, name)
    for snippet in snippets:
        if snippet not in function:
            raise RuntimeError(f"{name} missing {snippet}")


def replace_in_function(text, name, before, after):
    ranges = function_ranges(text, [name])
    if name not in ranges:
        raise RuntimeError(f"missing mutation function {name}")
    lines = text.splitlines(keepends=True)
    first, last = ranges[name]
    function = "".join(lines[first - 1:last])
    if not before or before == after or function.count(before) != 1:
        raise RuntimeError(f"mutation target must occur once in {name}: {before}")
    return "".join(lines[:first - 1]) + function.replace(before, after, 1) + "".join(lines[last:])


def require_changed_mutation(original, changed, index):
    if changed == original:
        raise RuntimeError(f"routing mutation {index} is a no-op")


def check(app, engine, audio):
    require(app, "debugLevel1Replay", "startClockedSound();", "clockedSoundEnabled_ = false;")
    require(app, "runInteractive", "startClockedSound();")
    for name in ("processEvents", "latchSoundRequest", "requestSoundCursor",
                 "requestSoundOffset", "playCompatibilitySound"):
        require(app, name, "serviceSoundClock();")
    require(app, "pumpSoundLatch", "if (clockedSoundEnabled_)", "serviceSoundClock();", "return;")
    require(app, "serviceSoundClock", "if (!clockedSoundEnabled_) return;",
            "presentationMilliseconds()", "now - soundClockMilliseconds_", "scaled % 1000",
            "audioOutput_.playClockedSamples(sound_.renderClockedTail(remaining))",
            "remaining > lezac::sound::kMaximumClockedTailSamples", "audioOutput_.discardClockedSamples();")
    require(engine, "renderClockedSamples", "uint64_t{kAudioSampleRate} * kBiosTimerDivisor",
            "applyClockedInterrupt();")
    require(engine, "applyClockedInterrupt", "advanceSoundInterrupt()", "speakerDivisorForFrequency(action.frequency)",
            "if (action.silence) speaker_.enabled = false;")
    require(engine, "renderClockedTail", "sampleCount > kMaximumClockedTailSamples",
            "skipClockedSamples(sampleCount - kMaximumClockedTailSamples);",
            "sampleCount = kMaximumClockedTailSamples;")
    require(engine, "skipClockedSamples", "if (!soundLatch_.active)",
            "advanceSpeakerPhase(sampleCount);", "advanceSpeakerPhase(count);",
            "soundClock_.pitAccumulator = partial % threshold;", "applyClockedInterrupt();")
    if "clearSoundLatch(" in body(engine, "renderClockedSamples"):
        raise RuntimeError("clock renderer clears the latch")
    require(audio, "open", "SDL_OpenAudioDevice(nullptr, 0, &want, &have, 0)")
    require(audio, "playClockedSamples", "discardClockedSamples();", "maximumBytes")
    require(audio, "discardClockedSamples", "SDL_ClearQueuedAudio(audioDevice_)", "clockedPrimed_ = false;")


def main():
    app = (ROOT / "src/app/app.cpp").read_text(encoding="utf-8")
    engine = (ROOT / "src/sound/sound_engine.cpp").read_text(encoding="utf-8")
    audio = (ROOT / "src/sound/sdl_audio_output.cpp").read_text(encoding="utf-8")
    check(app, engine, audio)
    mutations = [
        (replace_in_function(app, "debugLevel1Replay", "startClockedSound();", ";"), engine, audio),
        (replace_in_function(app, "runInteractive", "startClockedSound();", ";"), engine, audio),
        (app.replace("void processEvents(bool& running) {\n        serviceSoundClock();",
                     "void processEvents(bool& running) {"), engine, audio),
        (app.replace("if (clockedSoundEnabled_)", "if (false)"), engine, audio),
        (app.replace("audioOutput_.playClockedSamples(sound_.renderClockedTail(remaining))",
                     "audioOutput_.playSamples(sound_.pumpSoundLatch())"), engine, audio),
        (app, engine.replace("uint64_t{kAudioSampleRate} * kBiosTimerDivisor",
                             "uint64_t{kAudioSampleRate} * 28"), audio),
        (app, engine.replace("if (action.silence) speaker_.enabled = false;", ";"), audio),
        (app, engine.replace("skipClockedSamples(sampleCount - kMaximumClockedTailSamples);", ";"), audio),
        (app, engine.replace("sampleCount = kMaximumClockedTailSamples;", ";"), audio),
        (app, engine.replace("soundClock_.pitAccumulator = partial % threshold;", ";"), audio),
        (app.replace("audioOutput_.discardClockedSamples();", ";"), engine, audio),
        (app, engine.replace("advanceSpeakerPhase(sampleCount);", ";"), audio),
    ]
    rejected = 0
    for index, changed in enumerate(mutations):
        require_changed_mutation((app, engine, audio), changed, index)
        try:
            check(*changed)
        except RuntimeError:
            rejected += 1
    if rejected != len(mutations):
        raise RuntimeError(f"routing mutations accepted: {len(mutations) - rejected}")
    print("clocked_sound_routing=ok live_paths=2 request_paths=4 mutations=12 native_timing_claim=0")


if __name__ == "__main__":
    main()
