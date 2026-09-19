#include "diagnostics/sound/sound_diagnostics.hpp"
#include "resources/binary.hpp"
#include "resources/io.hpp"
#include <algorithm>
#include <array>
#include <cctype>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace lezac::diagnostics {
using namespace sound;
using resources::SoundEffectRecord;
using resources::readFile;
using resources::readTextFile;
using resources::parseHexByteList;
using resources::le16;

void SoundDiagnostics::debugSounds() {
    std::cout << "sound_record_size=" << sound_.bank().recordSize
              << " records=" << sound_.bank().records.size()
              << " steps=" << sound_.bank().stepCount
              << " words_per_record=" << (sound_.bank().recordSize / 2)
              << " six_byte_steps=" << (sound_.bank().payload.size() / kSoundStepSize)
              << '\n';
    for (size_t i = 0; i < sound_.bank().records.size(); ++i) {
        const std::vector<uint8_t>& bytes = sound_.bank().records[i].bytes;
        std::cout << "sound_" << (i + 1)
                  << "=bytes:" << bytes.size()
                  << " zero_bytes:" << std::count(bytes.begin(), bytes.end(), 0)
                  << " first_words:";
        for (size_t off = 0; off + 1 < bytes.size() && off < 12; off += 2) {
            if (off != 0) std::cout << ',';
            std::cout << std::showbase << std::hex << le16(bytes, off)
                      << std::dec << std::noshowbase;
        }
        std::cout << " first_groups:";
        for (size_t group = 0; group < 3 && group * 5 + 4 < bytes.size(); ++group) {
            if (group != 0) std::cout << ';';
            for (size_t j = 0; j < 5; ++j) {
                if (j != 0) std::cout << '-';
                std::cout << std::hex << std::setw(2) << std::setfill('0')
                          << static_cast<int>(bytes[group * 5 + j])
                          << std::dec << std::setfill(' ');
            }
        }
        std::cout << '\n';
    }
}

void SoundDiagnostics::debugSoundRender() {
    size_t totalSamples = 0;
    size_t totalNonZero = 0;
    for (size_t i = 0; i < sound_.bank().records.size(); ++i) {
        std::vector<int16_t> samples = sound_.synthesizeSound(i);
        size_t nonZero = static_cast<size_t>(
            std::count_if(samples.begin(), samples.end(),
                          [](int16_t sample) { return sample != 0; }));
        if (samples.empty() || nonZero == 0) {
            throw std::runtime_error("sound " + std::to_string(i + 1) +
                                     " rendered no audible samples");
        }
        totalSamples += samples.size();
        totalNonZero += nonZero;
        auto range = std::minmax_element(samples.begin(), samples.end());
        std::cout << "sound_render_" << (i + 1)
                  << "=cursor:" << std::showbase << std::hex
                  << sound_.compatibilitySoundCursor(i) << std::dec << std::noshowbase
                  << " samples:" << samples.size()
                  << " nonzero:" << nonZero
                  << " min:" << *range.first
                  << " max:" << *range.second << '\n';
    }
    std::cout << "sound_render_total=samples:" << totalSamples
              << " nonzero:" << totalNonZero << '\n';
}

void SoundDiagnostics::debugSoundCursorSegments() {
    std::vector<uint16_t> stopCursors;
    for (size_t i = 0; i < sound_.bank().stepCount; ++i) {
        if (sound_.soundStepPeriodWord(i) == kSoundStopPeriod) {
            stopCursors.push_back(static_cast<uint16_t>(i + 1));
        }
    }
    if (stopCursors.size() != kExpectedSoundStopCursors.size() ||
        !std::equal(stopCursors.begin(), stopCursors.end(),
                    kExpectedSoundStopCursors.begin())) {
        throw std::runtime_error("PROEFS.SON stop cursor map changed");
    }

    std::cout << "sound_cursor_segments steps=" << sound_.bank().stepCount
              << " stops=" << stopCursors.size()
              << " stop_cursors=";
    for (size_t i = 0; i < stopCursors.size(); ++i) {
        if (i != 0) std::cout << ',';
        std::cout << std::showbase << std::hex << stopCursors[i]
                  << std::dec << std::noshowbase;
    }
    std::cout << '\n';

    for (uint16_t cursor : kDebugSoundCursors) {
        uint16_t stopCursor = sound_.soundStopCursorFor(cursor);
        std::vector<int16_t> samples = sound_.synthesizeSoundCursor(cursor);
        if (samples.empty()) {
            throw std::runtime_error("PROEFS.SON cursor rendered no samples");
        }
        std::cout << "sound_cursor cursor=" << std::showbase << std::hex
                  << cursor << " stop=" << stopCursor
                  << std::dec << std::noshowbase
                  << " steps=" << (stopCursor - cursor)
                  << " samples=" << samples.size() << '\n';
    }
    std::cout << "sound_cursor_segments=ok\n";
}

void SoundDiagnostics::debugSonRawRoundtrip() {
    auto rawBytes = readFile("PROEFS.SON");
    if (rawBytes.size() < 2) {
        throw std::runtime_error("PROEFS.SON is too small");
    }
    uint16_t stepCount = le16(rawBytes, 0);
    size_t payloadSize = rawBytes.size() - 2;
    if (stepCount != 0x82 || payloadSize != static_cast<size_t>(stepCount) * 6) {
        throw std::runtime_error("PROEFS.SON raw step layout mismatch");
    }
    std::vector<uint8_t> jsonPayload;
    for (const SoundEffectRecord& record : sound_.bank().records) {
        jsonPayload.insert(jsonPayload.end(), record.bytes.begin(), record.bytes.end());
    }
    if (jsonPayload.size() != payloadSize ||
        !std::equal(jsonPayload.begin(), jsonPayload.end(), rawBytes.begin() + 2)) {
        throw std::runtime_error("PROEFS.SON raw/json payload mismatch");
    }
    std::cout << "son_raw_roundtrip=ok raw_size=" << rawBytes.size()
              << " step_count=" << stepCount
              << " payload_size=" << payloadSize
              << " json_chunks=" << sound_.bank().records.size() << '\n';
}

void SoundDiagnostics::debugSoundLoaderStaticModel() {
    std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
    if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
        throw std::runtime_error("LEZAC.EXE missing MZ header");
    }
    uint16_t headerParagraphs = le16(exeBytes, 0x08);
    size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
    if (imageBase != 0x0770) {
        throw std::runtime_error("LEZAC.EXE image base changed for sound loader scan");
    }
    constexpr uint16_t kFilenameAnchor = 0x0625;
    constexpr uint16_t kLoaderStart = 0x0630;
    constexpr uint16_t kCountConstant = 0x0633;
    constexpr uint16_t kFilenameCopy = 0x0644;
    constexpr uint16_t kCountRead = 0x065f;
    constexpr uint16_t kSoundBankRead = 0x0675;
    constexpr uint16_t kCountTimesSix = 0x067b;
    constexpr uint16_t kCloseFile = 0x0691;
    constexpr uint16_t kLoaderRet = 0x06aa;

    auto requireBytes = [&](uint16_t offset, const std::string& hex,
                            const std::string& label) {
        std::vector<uint8_t> expected = parseHexByteList(hex);
        size_t p = imageBase + offset;
        if (p + expected.size() > exeBytes.size()) {
            throw std::runtime_error(label + " extends past LEZAC.EXE");
        }
        for (size_t i = 0; i < expected.size(); ++i) {
            if (exeBytes[p + i] != expected[i]) {
                throw std::runtime_error(label + " bytes changed");
            }
        }
    };
    auto countBytes = [&](const std::string& hex) {
        std::vector<uint8_t> expected = parseHexByteList(hex);
        int count = 0;
        auto begin = exeBytes.begin() + static_cast<long>(imageBase + kLoaderStart);
        auto end = exeBytes.begin() + static_cast<long>(imageBase + kLoaderRet);
        for (auto it = begin; it != end;) {
            it = std::search(it, end, expected.begin(), expected.end());
            if (it == end) break;
            ++count;
            ++it;
        }
        return count;
    };

    requireBytes(kFilenameAnchor, "0a 70 72 6f 65 66 73 2e 73 6f 6e",
                 "PROEFS.SON filename anchor");
    requireBytes(kLoaderStart, "55 89 e5", "sound loader prologue");
    requireBytes(kCountConstant, "b8 82 00", "sound loader count constant");
    requireBytes(0x063b, "81 ec 82 00", "sound loader local buffer size");
    requireBytes(kFilenameCopy, "bf 25 06 0e 57 9a ca 15 20 09",
                 "sound loader filename copy");
    requireBytes(0x0653, "6a 01 9a f8 15 20 09", "sound loader open call");
    requireBytes(kCountRead, "8d be 7e ff 16 57 6a 02 31 c0 50 50 9a e3 16 20 09",
                 "sound loader count read");
    requireBytes(kSoundBankRead, "c4 3e c0 79 06 57",
                 "sound loader sound-bank pointer");
    requireBytes(kCountTimesSix, "8b 86 7e ff d1 e0 8b f0 d1 e0 01 f0 50",
                 "sound loader count times six");
    requireBytes(0x068c, "9a e3 16 20 09", "sound loader payload read");
    requireBytes(kCloseFile, "8d 7e 80 16 57 9a 79 16 20 09",
                 "sound loader close call");
    requireBytes(0x069b, "9a a2 04 20 09 09 c0 74 05 6a 01 e8 fa f9 c9 c3",
                 "sound loader io result tail");

    int readCalls = countBytes("9a e3 16 20 09");
    if (readCalls != 2) {
        throw std::runtime_error("sound loader read-call count changed");
    }

    std::cout << "sound_loader_static_model=ok"
              << " routine=" << hex4(kLoaderStart) << ".." << hex4(kLoaderRet)
              << " filename=proefs.son"
              << " filename_anchor=" << hex4(kFilenameAnchor)
              << " step_count=0x0082"
              << " step_size=6"
              << " payload_bytes=780"
              << " count_read_bytes=2"
              << " sound_bank_ptr=0x79c0"
              << " count_local=bp-0x82"
              << " count_times_six=1"
              << " read_calls=" << readCalls << '\n';
}

void SoundDiagnostics::debugSonStepFields() {
    if (sound_.bank().stepCount != 0x82 ||
        sound_.bank().payload.size() != sound_.bank().stepCount * kSoundStepSize) {
        throw std::runtime_error("PROEFS.SON step field layout mismatch");
    }

    auto hex2 = [](uint8_t value) {
        std::ostringstream oss;
        oss << "0x" << std::hex << std::nouppercase << std::setw(2)
            << std::setfill('0') << static_cast<int>(value);
        return oss.str();
    };
    auto hex4 = [](uint16_t value) {
        std::ostringstream oss;
        oss << "0x" << std::hex << std::nouppercase << std::setw(4)
            << std::setfill('0') << value;
        return oss.str();
    };

    struct StepFields {
        uint16_t periodWord = 0;
        uint8_t gateTick = 0;
        uint8_t periodTicks = 0;
        uint8_t tail4 = 0;
        uint8_t tail5 = 0;
    };

    auto step = [&](size_t stepIndex) {
        size_t off = stepIndex * kSoundStepSize;
        if (off + 5 >= sound_.bank().payload.size()) {
            throw std::runtime_error("PROEFS.SON step index out of range");
        }
        return StepFields{le16(sound_.bank().payload, off), sound_.bank().payload[off + 2],
                          sound_.bank().payload[off + 3], sound_.bank().payload[off + 4],
                          sound_.bank().payload[off + 5]};
    };

    std::vector<uint16_t> stopCursors;
    int tailPairNonzeroSteps = 0;
    for (size_t i = 0; i < sound_.bank().stepCount; ++i) {
        StepFields fields = step(i);
        if (fields.periodWord == kSoundStopPeriod) {
            stopCursors.push_back(static_cast<uint16_t>(i + 1));
        }
        if (fields.tail4 != 0 || fields.tail5 != 0) {
            ++tailPairNonzeroSteps;
        }
    }
    if (stopCursors.size() != kExpectedSoundStopCursors.size() ||
        !std::equal(stopCursors.begin(), stopCursors.end(),
                    kExpectedSoundStopCursors.begin())) {
        throw std::runtime_error("PROEFS.SON step stop cursor map changed");
    }

    auto printStep = [&](const std::string& label, size_t stepIndex) {
        StepFields fields = step(stepIndex);
        std::cout << "son_step_fields " << label
                  << " step_index=" << stepIndex
                  << " cursor=" << hex4(static_cast<uint16_t>(stepIndex + 1))
                  << " period_word=" << hex4(fields.periodWord)
                  << " gate_tick=" << static_cast<int>(fields.gateTick)
                  << " period_ticks=" << static_cast<int>(fields.periodTicks)
                  << " tail4=" << hex2(fields.tail4)
                  << " tail5=" << hex2(fields.tail5)
                  << " stop=" << (fields.periodWord == kSoundStopPeriod ? 1 : 0)
                  << '\n';
    };

    std::cout << "son_step_fields=summary steps=" << sound_.bank().stepCount
              << " step_size=" << kSoundStepSize
              << " stop_sentinels=" << stopCursors.size()
              << " tail_pair_nonzero_steps=" << tailPairNonzeroSteps
              << " period_word=bytes0-1"
              << " gate_tick=byte2"
              << " period_ticks=byte3"
              << " tail4=byte4"
              << " tail5=byte5"
              << " tail_behavior=preserved_playback_unused\n";
    printStep("first", 0);
    printStep("first_stop", stopCursors.front() - 1);
    printStep("final_stop", stopCursors.back() - 1);
    std::cout << "son_step_fields=ok steps=" << sound_.bank().stepCount
              << " first_period=" << hex4(step(0).periodWord)
              << " first_stop_cursor=" << hex4(stopCursors.front())
              << " final_stop_cursor=" << hex4(stopCursors.back())
              << " tail_pair_nonzero_steps=" << tailPairNonzeroSteps
              << " tail_behavior=preserved_playback_unused"
              << '\n';
}

void SoundDiagnostics::debugSonTailFieldMutation() {
    resources::SoundBank sounds_ = sound_.bank();
    sound::SoundEngine fixture(sounds_);
    if (sounds_.stepCount != 0x82 ||
        sounds_.payload.size() != sounds_.stepCount * kSoundStepSize) {
        throw std::runtime_error("PROEFS.SON step field layout mismatch");
    }

    std::vector<std::vector<int16_t>> baseline;
    baseline.reserve(kDebugSoundCursors.size());
    size_t baselineSamples = 0;
    for (uint16_t cursor : kDebugSoundCursors) {
        baseline.push_back(fixture.synthesizeSoundCursor(cursor));
        baselineSamples += baseline.back().size();
        if (baseline.back().empty()) {
            throw std::runtime_error("PROEFS.SON cursor rendered no samples");
        }
    }

    std::vector<uint8_t> originalPayload = sounds_.payload;
    int tailPairNonzeroSteps = 0;
    int mutatedSteps = 0;
    for (size_t step = 0; step < sounds_.stepCount; ++step) {
        size_t off = step * kSoundStepSize;
        if (sounds_.payload[off + 4] != 0 || sounds_.payload[off + 5] != 0) {
            ++tailPairNonzeroSteps;
        }
        sounds_.payload[off + 4] =
            static_cast<uint8_t>(sounds_.payload[off + 4] ^ 0xffu);
        sounds_.payload[off + 5] =
            static_cast<uint8_t>(sounds_.payload[off + 5] ^ 0xa5u);
        ++mutatedSteps;
    }

    size_t mutatedSamples = 0;
    for (size_t i = 0; i < kDebugSoundCursors.size(); ++i) {
        std::vector<int16_t> mutated = fixture.synthesizeSoundCursor(kDebugSoundCursors[i]);
        mutatedSamples += mutated.size();
        if (mutated != baseline[i]) {
            std::ostringstream oss;
            oss << "PROEFS.SON tail field mutation changed cursor 0x"
                << std::hex << std::setw(4) << std::setfill('0')
                << kDebugSoundCursors[i];
            throw std::runtime_error(oss.str());
        }
    }
    sounds_.payload = std::move(originalPayload);

    std::cout << "son_tail_fields_mutation=ok steps=" << sounds_.stepCount
              << " mutated_steps=" << mutatedSteps
              << " compared_cursors=" << kDebugSoundCursors.size()
              << " baseline_samples=" << baselineSamples
              << " mutated_samples=" << mutatedSamples
              << " tail_pair_nonzero_steps=" << tailPairNonzeroSteps
              << " ignored_tail_bytes=4,5"
              << " tail_behavior=preserved_playback_unused\n";
}

void SoundDiagnostics::debugSoundTickStaticModel() {
    std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
    if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
        throw std::runtime_error("LEZAC.EXE missing MZ header");
    }
    uint16_t headerParagraphs = le16(exeBytes, 0x08);
    size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
    if (imageBase != 0x0770) {
        throw std::runtime_error("LEZAC.EXE image base changed for sound tick scan");
    }
    constexpr uint16_t kTickStart = 0x0fbe;
    constexpr uint16_t kTickRet = 0x1088;
    constexpr uint16_t kDirectSweepBranch = 0x0fd9;
    constexpr uint16_t kStepAdvance = 0x1014;
    constexpr uint16_t kStepAddress = 0x1023;
    constexpr uint16_t kStopCompare = 0x1033;
    constexpr uint16_t kPeriodPush = 0x1053;
    constexpr uint16_t kGateByteRead = 0x105e;
    constexpr uint16_t kPeriodByteRead = 0x1068;

    auto requireBytes = [&](uint16_t offset, const std::string& hex,
                            const std::string& label) {
        std::vector<uint8_t> expected = parseHexByteList(hex);
        size_t p = imageBase + offset;
        if (p + expected.size() > exeBytes.size()) {
            throw std::runtime_error(label + " extends past LEZAC.EXE");
        }
        for (size_t i = 0; i < expected.size(); ++i) {
            if (exeBytes[p + i] != expected[i]) {
                throw std::runtime_error(label + " bytes changed");
            }
        }
    };
    auto containsBytes = [&](const std::vector<uint8_t>& expected) {
        auto begin = exeBytes.begin() + static_cast<long>(imageBase + kTickStart);
        auto end = exeBytes.begin() + static_cast<long>(imageBase + kTickRet);
        return std::search(begin, end, expected.begin(), expected.end()) != end;
    };
    auto countBytes = [&](const std::string& hex) {
        std::vector<uint8_t> expected = parseHexByteList(hex);
        int count = 0;
        auto begin = exeBytes.begin() + static_cast<long>(imageBase + kTickStart);
        auto end = exeBytes.begin() + static_cast<long>(imageBase + kTickRet);
        for (auto it = begin; it != end;) {
            it = std::search(it, end, expected.begin(), expected.end());
            if (it == end) break;
            ++count;
            ++it;
        }
        return count;
    };

    requireBytes(kTickStart, "50 53 51 52 56 57 1e 06 c8 04 00 00",
                 "sound tick prologue");
    requireBytes(kDirectSweepBranch,
                 "81 3e c0 78 60 ea 76 26 a1 c0 78 2d 42 ea 50",
                 "sound tick direct sweep branch");
    requireBytes(kStepAdvance,
                 "ff 06 c0 78 a1 c0 78 d1 e0 8b f0 d1 e0 01 f0",
                 "sound tick cursor stride");
    requireBytes(kStepAddress, "c4 3e c0 79 03 f8 81 c7 fa ff",
                 "sound tick step address");
    requireBytes(kStopCompare, "c4 7e fc 26 81 3d 30 75",
                 "sound tick stop compare");
    requireBytes(kPeriodPush, "c4 7e fc 26 ff 35 9a c9 02 4a 08",
                 "sound tick period push");
    requireBytes(kGateByteRead, "c4 7e fc 26 8a 45 02 a2 a1 79",
                 "sound tick gate byte read");
    requireBytes(kPeriodByteRead, "c4 7e fc 26 8a 45 03 a2 a2 79",
                 "sound tick period byte read");
    requireBytes(kTickRet - 1, "c9", "sound tick leave");

    int byteReads = countBytes("26 8a 45");
    int wordReads = countBytes("26 81 3d") + countBytes("26 ff 35");
    int tailReadPatterns = 0;
    for (const std::string& pattern : {
             "26 8a 45 04", "26 8a 45 05", "26 8b 45 04",
             "26 8b 45 05", "26 ff 75 04", "26 ff 75 05",
         }) {
        if (containsBytes(parseHexByteList(pattern))) ++tailReadPatterns;
    }
    if (byteReads != 2 || wordReads != 2 || tailReadPatterns != 0) {
        throw std::runtime_error("sound tick step read model changed");
    }

    std::cout << "sound_tick_static_model=ok"
              << " routine=" << hex4(kTickStart) << ".." << hex4(kTickRet)
              << " direct_sweep_threshold=0xea60"
              << " direct_sweep_subtract=0xea42"
              << " direct_sweep_step=4"
              << " cursor_increment=" << hex4(kStepAdvance)
              << " entry_stride=6"
              << " entry_base=sound_bank+cursor*6-6"
              << " stop_sentinel=0x7530"
              << " period_word_offsets=0"
              << " gate_byte_offset=2"
              << " period_byte_offset=3"
              << " word_entry_reads=" << wordReads
              << " byte_entry_reads=" << byteReads
              << " tail_read_patterns=" << tailReadPatterns
              << " ignored_tail_bytes=4,5"
              << " tail_behavior=preserved_playback_unused\n";
}

void SoundDiagnostics::debugSoundLatchStaticModel() {
    std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
    if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
        throw std::runtime_error("LEZAC.EXE missing MZ header");
    }
    uint16_t headerParagraphs = le16(exeBytes, 0x08);
    size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
    if (imageBase != 0x0770) {
        throw std::runtime_error("LEZAC.EXE image base changed for sound latch scan");
    }
    constexpr uint16_t kLatchStart = 0x165a;
    constexpr uint16_t kInactiveAcceptBranch = 0x165f;
    constexpr uint16_t kRejectBranch = 0x166a;
    constexpr uint16_t kAcceptPath = 0x166c;
    constexpr uint16_t kRejectRet = 0x167d;

    auto requireBytes = [&](uint16_t offset, const std::string& hex,
                            const std::string& label) {
        std::vector<uint8_t> expected = parseHexByteList(hex);
        size_t p = imageBase + offset;
        if (p + expected.size() > exeBytes.size()) {
            throw std::runtime_error(label + " extends past LEZAC.EXE");
        }
        for (size_t i = 0; i < expected.size(); ++i) {
            if (exeBytes[p + i] != expected[i]) {
                throw std::runtime_error(label + " bytes changed");
            }
        }
    };
    auto shortJumpTarget = [&](uint16_t offset, const std::string& label) {
        size_t p = imageBase + offset;
        if (p + 2 > exeBytes.size()) {
            throw std::runtime_error(label + " jump extends past LEZAC.EXE");
        }
        uint8_t raw = exeBytes[p + 1];
        int displacement = raw < 0x80 ? raw : static_cast<int>(raw) - 0x100;
        return static_cast<uint16_t>(offset + 2 + displacement);
    };

    requireBytes(kLatchStart,
                 "a0 c4 79 3c 00 74 0b a0 9e 79 fe c8 3a 06 9f 79 "
                 "7d 11 a0 9f 79 a2 9e 79 a1 74 20 a3 c0 78 c6 06 "
                 "c4 79 01 c3",
                 "sound latch routine");
    requireBytes(kLatchStart, "a0 c4 79 3c 00 74 0b",
                 "sound latch active gate");
    requireBytes(0x1661, "a0 9e 79 fe c8 3a 06 9f 79 7d 11",
                 "sound latch priority compare");
    requireBytes(kAcceptPath, "a0 9f 79 a2 9e 79",
                 "sound latch priority copy");
    requireBytes(0x1672, "a1 74 20 a3 c0 78",
                 "sound latch cursor copy");
    requireBytes(0x1678, "c6 06 c4 79 01 c3",
                 "sound latch active flag set");

    uint16_t inactiveAcceptTarget =
        shortJumpTarget(kInactiveAcceptBranch, "sound latch inactive accept");
    uint16_t rejectTarget = shortJumpTarget(kRejectBranch, "sound latch reject");
    if (inactiveAcceptTarget != kAcceptPath || rejectTarget != kRejectRet) {
        throw std::runtime_error("sound latch branch target changed");
    }

    std::cout << "sound_latch_static_model=ok"
              << " routine=" << hex4(kLatchStart) << ".." << hex4(kRejectRet)
              << " active_flag=0x79c4"
              << " current_priority=0x799e"
              << " pending_priority=0x799f"
              << " pending_cursor=0x2074"
              << " current_cursor=0x78c0"
              << " inactive_accept=1"
              << " reject_branch=" << hex4(rejectTarget)
              << " accept_branch=" << hex4(inactiveAcceptTarget)
              << " current_minus_one_compare=1"
              << " copies_priority=1"
              << " copies_cursor=1"
              << " sets_active=1\n";
}

void SoundDiagnostics::debugSoundPriorityLatch() {
    auto printCase = [&](const std::string& name, bool accepted) {
        std::cout << "sound_latch case=" << name
                  << " accepted=" << (accepted ? 1 : 0)
                  << " active=" << (sound_.latch().active ? 1 : 0)
                  << " priority=" << static_cast<int>(sound_.latch().currentSelector)
                  << " offset=" << std::showbase << std::hex
                  << sound_.latch().latchedOffset << std::dec << std::noshowbase
                  << '\n';
    };

    sound_.clearSoundLatch();
    printCase("inactive_accept",
              sound_.latchSoundRequest(kExplosionDirectSweepSoundOffsets[0], 4));
    printCase("lower_rejected",
              sound_.latchSoundRequest(kExplosionDirectSweepSoundOffsets[1], 2));
    printCase("same_refresh",
              sound_.latchSoundRequest(kExplosionDirectSweepSoundOffsets[2], 4));
    printCase("higher_replaces",
              sound_.latchSoundRequest(kExplosionDirectSweepSoundOffsets[3], 7));
    printCase("one_below_high_rejected",
              sound_.latchSoundRequest(kExplosionDirectSweepSoundOffsets[2], 6));
    sound_.clearSoundLatch();
    printCase("cleared_accepts",
              sound_.latchSoundRequest(kExplosionDirectSweepSoundOffsets[1], 1));

    if (!sound_.latch().active || sound_.latch().currentSelector != 1 ||
        sound_.latch().latchedOffset != kExplosionDirectSweepSoundOffsets[1] ||
        !sound_.latch().directSweep) {
        throw std::runtime_error("sound latch final state mismatch");
    }
    sound_.pumpSoundLatch();
    if (sound_.latch().active || sound_.lastPumped().record != 1 ||
        sound_.lastPumped().offset != kExplosionDirectSweepSoundOffsets[1] ||
        sound_.lastPumped().selector != 1) {
        throw std::runtime_error("sound latch pump mismatch");
    }
    std::cout << "sound_pump active=" << (sound_.latch().active ? 1 : 0)
              << " last_record=" << sound_.lastPumped().record
              << " last_offset=" << std::showbase << std::hex
              << sound_.lastPumped().offset << std::dec << std::noshowbase
              << " last_selector=" << static_cast<int>(sound_.lastPumped().selector)
              << '\n';
    std::cout << "sound_latch=ok\n";
}

void SoundDiagnostics::debugSoundSelectorMap() {
    std::cout << "sound_selector_map records=" << sound_.bank().records.size() << '\n';
    for (uint8_t selector = 4; selector <= 7; ++selector) {
        uint16_t offset = kExplosionDirectSweepSoundOffsets[static_cast<size_t>(selector - 4)];
        size_t fallbackIndex = sound_.soundIndexForOffsetFallback(offset, selector);
        std::vector<int16_t> samples = sound_.synthesizeDirectSweep(offset);
        if (samples.empty()) {
            throw std::runtime_error("mapped direct sweep rendered no samples");
        }
        std::cout << "sound_selector_map selector=" << static_cast<int>(selector)
                  << " offset=" << std::showbase << std::hex << offset
                  << std::dec << std::noshowbase
                  << " direct_sweep=1"
                  << " fallback_record_index=" << fallbackIndex
                  << " samples=" << samples.size() << '\n';
    }
    if (!std::all_of(kExplosionDirectSweepSoundOffsets.begin(),
                     kExplosionDirectSweepSoundOffsets.end(),
                     [&](uint16_t offset) { return sound_.isDirectSoundSweep(offset); }) ||
        sound_.soundIndexForOffsetFallback(kExplosionDirectSweepSoundOffsets[0], 4) != 0 ||
        sound_.soundIndexForOffsetFallback(kExplosionDirectSweepSoundOffsets[1], 5) != 1 ||
        sound_.soundIndexForOffsetFallback(kExplosionDirectSweepSoundOffsets[2], 6) != 2 ||
        sound_.soundIndexForOffsetFallback(kExplosionDirectSweepSoundOffsets[3], 7) != 3) {
        throw std::runtime_error("explosion selector map mismatch");
    }
    std::cout << "sound_selector_map=ok\n";
}

}  // namespace lezac::diagnostics
