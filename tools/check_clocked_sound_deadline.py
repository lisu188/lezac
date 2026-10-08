"""Guard live deadline assertions; compiled CTests exercise the actual loop."""
from pathlib import Path

from source_guardrails import function_ranges, mask_cpp


ROOT = Path(__file__).resolve().parents[1]


def check(app, cmake):
    ranges = function_ranges(app, ['debugClockedSoundLive'])
    if 'debugClockedSoundLive' not in ranges:
        raise RuntimeError('missing live diagnostic')
    first, last = ranges['debugClockedSoundLive']
    raw = ''.join(app.splitlines(keepends=True)[first - 1:last])
    live = mask_cpp(raw)
    required = (
        'if (stallAtDeadline && !stalled)', 'SDL_Delay(850);',
        'return SDL_GetTicks() - start >= 600;',
        'start = soundClockMilliseconds_;',
        'initialRemainder = soundSampleRemainder_;',
        'initialClock = sound_.clockState();',
        'const uint32_t elapsed = soundClockMilliseconds_ - start;',
        '(uint64_t{elapsed} * kAudioSampleRate + initialRemainder) / 1000',
        'initialClock.pitAccumulator +',
        'advancedSamples * lezac::sound::kPitClockRate',
        'uint64_t{kAudioSampleRate} * lezac::sound::kBiosTimerDivisor',
        'elapsed < 600',
        'uint32_t{soundClockMilliseconds_ - beforeFinalService} >',
        'uint32_t{afterFinalService - beforeFinalService}',
        'state.renderedSamples != initialClock.renderedSamples + advancedSamples',
        'state.interrupts != initialClock.interrupts + scaledPit / threshold',
        'state.pitAccumulator != scaledPit % threshold',
    )
    for snippet in required:
        if snippet not in live:
            raise RuntimeError('missing deadline contract: ' + snippet)
    final_service = (
        '        const uint32_t beforeFinalService = SDL_GetTicks();\n'
        '        serviceSoundClock();\n'
        '        const uint32_t afterFinalService = SDL_GetTicks();'
    )
    if final_service not in live or live.index(final_service) < live.index('runInteractive('):
        raise RuntimeError('missing bracketed final service')
    if 'SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);' not in raw:
        raise RuntimeError('audible diagnostic')
    if '12000' in live or '18000' in live or 'state.interrupts <' in live:
        raise RuntimeError('fixed wall-clock window restored')
    for snippet in (
        'foreach(clock_state IN ITEMS menu pause)',
        'NAME clocked_sound_live_${clock_state}_stalled',
        '"${CMAKE_CURRENT_BINARY_DIR}/clocked-sound-checks" --stall-at-deadline',
        'ENVIRONMENT "SDL_VIDEODRIVER=dummy;SDL_AUDIODRIVER=dummy"',
        'stalled_deadline=1',
    ):
        if snippet not in cmake:
            raise RuntimeError('missing compiled regression: ' + snippet)


def main():
    app = (ROOT / 'src/app/app.cpp').read_text(encoding='utf-8')
    cmake = (ROOT / 'CMakeLists.txt').read_text(encoding='utf-8')
    check(app, cmake)
    mutations = (
        (app.replace('        serviceSoundClock();\n        const uint32_t afterFinalService',
                     '        const uint32_t afterFinalService', 1), cmake),
        (app.replace('const uint32_t elapsed = soundClockMilliseconds_ - start;',
                     'const uint32_t elapsed = 600;', 1), cmake),
        (app.replace('+ initialRemainder) / 1000', ') / 1000', 1), cmake),
        (app.replace('initialClock.pitAccumulator +', 'uint64_t{0} +', 1), cmake),
        (app.replace('state.renderedSamples != initialClock.renderedSamples + advancedSamples',
                     'state.renderedSamples < 12000', 1), cmake),
        (app.replace('state.interrupts != initialClock.interrupts + scaledPit / threshold',
                     'state.interrupts < 10', 1), cmake),
        (app.replace('state.pitAccumulator != scaledPit % threshold', 'false', 1), cmake),
        (app.replace('uint32_t{soundClockMilliseconds_ - beforeFinalService} >',
                     'uint32_t{0} >', 1), cmake),
        (app.replace('SDL_Delay(850);', 'SDL_Delay(1);', 1), cmake),
        (app.replace('SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);', ';'), cmake),
        (app, cmake.replace('NAME clocked_sound_live_${clock_state}_stalled',
                            'NAME disabled_live_${clock_state}_stalled', 1)),
        (app, cmake.replace('"${CMAKE_CURRENT_BINARY_DIR}/clocked-sound-checks" --stall-at-deadline',
                            '"${CMAKE_CURRENT_BINARY_DIR}/clocked-sound-checks"', 1)),
    )
    for index, changed in enumerate(mutations):
        if changed == (app, cmake):
            raise RuntimeError(f'mutation {index} did not change source')
        try:
            check(*changed)
        except RuntimeError:
            continue
        raise RuntimeError(f'mutation {index} was accepted')
    print('clocked_sound_deadline_contract=ok mutations=12 compiled_live_claim=0 native_timing_claim=0')


if __name__ == '__main__':
    main()
