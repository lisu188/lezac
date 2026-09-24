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

std::string SoundDiagnostics::hex4(uint16_t value) {
    std::ostringstream oss;
    oss << "0x" << std::hex << std::nouppercase << std::setw(4)
        << std::setfill('0') << value;
    return oss.str();
}

void SoundDiagnostics::debugStaticSoundRequests() {
    struct StaticSoundWrite {
        uint16_t offset;
        uint16_t cursor;
    };
    struct MappedStaticSoundWrite {
        uint16_t offset;
        const char* label;
    };
    struct UnresolvedStaticSoundWrite {
        uint16_t offset;
        const char* label;
    };
    static const std::array<StaticSoundWrite, 27> kExpectedWrites{{
        {0x1857, 0x0078}, {0x1a44, 0x0008}, {0x1d9c, 0x003d},
        {0x202d, 0x0021}, {0x2083, 0x0024}, {0x2c04, 0x0078},
        {0x30b1, 0x0056}, {0x41a9, 0xea74}, {0x41ed, 0xea7e},
        {0x4231, 0xea88}, {0x431d, 0xeace}, {0x49bd, 0x0027},
        {0x4b2c, 0x0021}, {0x4d3c, 0x2710}, {0x4dd3, 0x2710},
        {0x557b, 0xea74}, {0x575d, 0x0027}, {0x5a0e, 0x001a},
        {0x5c9e, 0x003d}, {0x5e81, 0x0069}, {0x6844, 0x0024},
        {0x6924, 0x0035}, {0x6e34, 0x0012}, {0x6f82, 0x0008},
        {0x7386, 0x0021}, {0x789c, 0x0001}, {0x7f84, 0x002d},
    }};
    static const std::array<MappedStaticSoundWrite, 17> kMappedWrites{{
        {0x1857, "record_name_prompt"},
        {0x1a44, "record_name_commit"},
        {0x2083, "records_page"},
        {0x30b1, "player_death"},
        {0x41a9, "explosion_small"},
        {0x41ed, "explosion_medium"},
        {0x4231, "explosion_large"},
        {0x431d, "explosion_super"},
        {0x557b, "bomb_place"},
        {0x575d, "tile_trigger"},
        {0x5a0e, "portal_teleport"},
        {0x5c9e, "monster_death"},
        {0x6844, "weapon_switch"},
        {0x6924, "launch_pad"},
        {0x6e34, "bomb_object_high"},
        {0x6f82, "bonus_pickup"},
        {0x7f84, "player_damage"},
    }};
    static const std::array<UnresolvedStaticSoundWrite, 10> kUnresolvedWrites{{
        {0x1d9c, "post_end_flow_record_region"},
        {0x202d, "record_table_cursor_only"},
        {0x2c04, "cursor_0078_priority11"},
        {0x49bd, "cursor_0027_priority5"},
        {0x4b2c, "collapse_playback_rejected"},
        {0x4d3c, "cursor_2710"},
        {0x4dd3, "cursor_2710"},
        {0x5e81, "cursor_0069_priority4"},
        {0x7386, "cursor_0021_priority1"},
        {0x789c, "cursor_0001_no_latch"},
    }};

    std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
    if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
        throw std::runtime_error("LEZAC.EXE missing MZ header");
    }
    uint16_t headerParagraphs = le16(exeBytes, 0x08);
    size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
    if (imageBase != 0x0770) {
        throw std::runtime_error("LEZAC.EXE image base changed for sound scan");
    }
    size_t imageSize = exeBytes.size() - imageBase;
    std::vector<StaticSoundWrite> writes;
    for (size_t off = 0; off + 6 <= imageSize; ++off) {
        size_t p = imageBase + off;
        if (exeBytes[p] == 0xc7 && exeBytes[p + 1] == 0x06 &&
            exeBytes[p + 2] == 0x74 && exeBytes[p + 3] == 0x20) {
            writes.push_back({
                static_cast<uint16_t>(off),
                le16(exeBytes, p + 4),
            });
        }
    }
    if (writes.size() != kExpectedWrites.size()) {
        throw std::runtime_error("static sound request write count changed");
    }
    for (size_t i = 0; i < writes.size(); ++i) {
        if (writes[i].offset != kExpectedWrites[i].offset ||
            writes[i].cursor != kExpectedWrites[i].cursor) {
            throw std::runtime_error("static sound request table changed");
        }
    }

    auto nearLatchCallCount = [&](uint16_t offset) {
        int count = 0;
        for (size_t relOff = 0; relOff < 160; ++relOff) {
            size_t callOff = static_cast<size_t>(offset) + relOff;
            size_t p = imageBase + callOff;
            if (p + 3 > exeBytes.size() || exeBytes[p] != 0xe8) continue;
            uint16_t rawRel = le16(exeBytes, p + 1);
            int signedRel = rawRel >= 0x8000u
                                ? static_cast<int>(rawRel) - 0x10000
                                : static_cast<int>(rawRel);
            uint16_t target = static_cast<uint16_t>(callOff + 3 + signedRel);
            if (target == 0x165a) ++count;
        }
        return count;
    };
    auto nearPriorityWrite = [&](uint16_t offset) {
        for (size_t relOff = 0; relOff < 160; ++relOff) {
            size_t p = imageBase + static_cast<size_t>(offset) + relOff;
            if (p + 5 > exeBytes.size()) break;
            if (exeBytes[p] == 0xc6 && exeBytes[p + 1] == 0x06 &&
                exeBytes[p + 2] == 0x9f && exeBytes[p + 3] == 0x79) {
                return true;
            }
        }
        return false;
    };
    auto priorityAt = [&](uint16_t offset) {
        size_t p = imageBase + offset;
        if (p + 5 > exeBytes.size() || exeBytes[p] != 0xc6 ||
            exeBytes[p + 1] != 0x06 || exeBytes[p + 2] != 0x9f ||
            exeBytes[p + 3] != 0x79) {
            throw std::runtime_error("expected static priority write missing");
        }
        return exeBytes[p + 4];
    };

    int latchCandidates = 0;
    int latchRefs = 0;
    int priorityCandidates = 0;
    int directSweepWrites = 0;
    int mappedWrites = 0;
    std::ostringstream list;
    std::ostringstream mappedLabels;
    std::ostringstream unresolvedCandidates;
    std::ostringstream unresolvedLabels;
    for (size_t i = 0; i < writes.size(); ++i) {
        int calls = nearLatchCallCount(writes[i].offset);
        if (calls > 0) ++latchCandidates;
        latchRefs += calls;
        if (nearPriorityWrite(writes[i].offset)) ++priorityCandidates;
        if (sound_.isDirectSoundSweep(writes[i].cursor)) ++directSweepWrites;
        auto mappedIt = std::find_if(
            kMappedWrites.begin(), kMappedWrites.end(),
            [&](const MappedStaticSoundWrite& mapped) {
                return mapped.offset == writes[i].offset;
            });
        if (mappedIt != kMappedWrites.end()) {
            ++mappedWrites;
            if (mappedLabels.tellp() > 0) mappedLabels << ',';
            mappedLabels << hex4(mappedIt->offset) << ':' << mappedIt->label;
        } else {
            auto unresolvedIt = std::find_if(
                kUnresolvedWrites.begin(), kUnresolvedWrites.end(),
                [&](const UnresolvedStaticSoundWrite& unresolved) {
                    return unresolved.offset == writes[i].offset;
                });
            if (unresolvedIt == kUnresolvedWrites.end()) {
                throw std::runtime_error("unclassified static sound write");
            }
            if (unresolvedCandidates.tellp() > 0) unresolvedCandidates << ',';
            unresolvedCandidates << hex4(writes[i].offset);
            if (unresolvedLabels.tellp() > 0) unresolvedLabels << ',';
            unresolvedLabels << hex4(unresolvedIt->offset) << ':'
                             << unresolvedIt->label;
        }
        if (i != 0) list << ',';
        list << hex4(writes[i].offset) << ':' << hex4(writes[i].cursor);
    }
    if (latchCandidates != 21 || latchRefs != 22 ||
        priorityCandidates != 21 || directSweepWrites != 5 ||
        mappedWrites != static_cast<int>(kMappedWrites.size()) ||
        priorityAt(0x185d) != kRecordNamePromptSoundPriority ||
        nearLatchCallCount(0x1857) != 1 ||
        priorityAt(0x1a4a) != kRecordNameCommitSoundPriority ||
        nearLatchCallCount(0x1a44) != 1 ||
        priorityAt(0x2089) != kRecordsPageSoundPriority ||
        nearLatchCallCount(0x2083) != 1 ||
        priorityAt(0x5581) != kBombPlaceSoundPriority ||
        nearLatchCallCount(0x557b) != 1 ||
        priorityAt(0x5ca4) != kMonsterDeathSoundPriority ||
        nearLatchCallCount(0x5c9e) != 1) {
        throw std::runtime_error("static sound request summary changed");
    }
    auto remainingHookList = [] {
        std::ostringstream out;
        for (size_t i = 0; i < kRemainingSoundCompatibilityHooks.size(); ++i) {
            if (i != 0) out << ',';
            out << kRemainingSoundCompatibilityHooks[i].hook;
        }
        return out.str();
    };
    auto rejectedObjectiveCandidateList = [] {
        std::ostringstream out;
        for (size_t i = 0; i < kRejectedObjectiveSoundCandidates.size(); ++i) {
            if (i != 0) out << ',';
            const RejectedSoundCandidate& candidate =
                kRejectedObjectiveSoundCandidates[i];
            out << hex4(candidate.offset) << ':' << candidate.reason;
        }
        return out.str();
    };
    auto remainingCaptureBlockerList = [] {
        std::ostringstream out;
        for (size_t i = 0; i < kRemainingSoundCompatibilityHooks.size(); ++i) {
            if (i != 0) out << ',';
            const RemainingSoundCompatibilityHook& hook =
                kRemainingSoundCompatibilityHooks[i];
            out << hook.hook << ':' << hook.captureBlocker;
        }
        return out.str();
    };
    std::string remainingHooks = remainingHookList();
    std::string rejectedObjectiveCandidates = rejectedObjectiveCandidateList();
    std::string remainingCaptureBlockers = remainingCaptureBlockerList();
    std::string mappedLabelList = mappedLabels.str();
    std::string unresolvedCandidateList = unresolvedCandidates.str();
    std::string unresolvedLabelList = unresolvedLabels.str();
    if (remainingHooks != "objective_pickup,level_complete" ||
        rejectedObjectiveCandidates !=
            "0x4b2c:collapse_playback,0x6d75:bomb_object_high_gate,"
            "0x6924:non_objective_tile_gate" ||
        remainingCaptureBlockers !=
            "objective_pickup:rejected_static_candidates,"
            "level_complete:no_static_candidate") {
        throw std::runtime_error("sound compatibility recovery notes changed");
    }
    if (mappedLabelList !=
            "0x1857:record_name_prompt,0x1a44:record_name_commit,"
            "0x2083:records_page,0x30b1:player_death,"
            "0x41a9:explosion_small,0x41ed:explosion_medium,"
            "0x4231:explosion_large,0x431d:explosion_super,"
            "0x557b:bomb_place,0x575d:tile_trigger,"
            "0x5a0e:portal_teleport,0x5c9e:monster_death,"
            "0x6844:weapon_switch,0x6924:launch_pad,"
            "0x6e34:bomb_object_high,0x6f82:bonus_pickup,"
            "0x7f84:player_damage" ||
        unresolvedCandidateList !=
            "0x1d9c,0x202d,0x2c04,0x49bd,0x4b2c,0x4d3c,"
            "0x4dd3,0x5e81,0x7386,0x789c") {
        throw std::runtime_error("static sound mapping ledger changed");
    }
    if (unresolvedLabelList !=
            "0x1d9c:post_end_flow_record_region,"
            "0x202d:record_table_cursor_only,"
            "0x2c04:cursor_0078_priority11,"
            "0x49bd:cursor_0027_priority5,"
            "0x4b2c:collapse_playback_rejected,"
            "0x4d3c:cursor_2710,"
            "0x4dd3:cursor_2710,"
            "0x5e81:cursor_0069_priority4,"
            "0x7386:cursor_0021_priority1,"
            "0x789c:cursor_0001_no_latch") {
        throw std::runtime_error("static sound unresolved labels changed");
    }

    std::cout << "static_sound_requests=ok writes=" << writes.size()
              << " image_base=0x0770"
              << " latch=0x165a"
              << " latch_candidates=" << latchCandidates
              << " latch_refs=" << latchRefs
              << " priority_candidates=" << priorityCandidates
              << " direct_sweep=" << directSweepWrites
              << " mapped=" << mappedWrites
              << " unresolved=" << (static_cast<int>(writes.size()) - mappedWrites)
              << " record_prompt=" << hex4(0x1857) << ':'
              << hex4(kRecordNamePromptSoundCursor)
              << "/p" << static_cast<int>(kRecordNamePromptSoundPriority)
              << " record_commit=" << hex4(0x1a44) << ':'
              << hex4(kRecordNameCommitSoundCursor)
              << "/p" << static_cast<int>(kRecordNameCommitSoundPriority)
              << " records_page=" << hex4(0x2083) << ':'
              << hex4(kRecordsPageSoundCursor)
              << "/p" << static_cast<int>(kRecordsPageSoundPriority)
              << " bomb_place=" << hex4(0x557b) << ':' << hex4(kBombPlaceSoundCursor)
              << "/p" << static_cast<int>(kBombPlaceSoundPriority)
              << " monster_death=" << hex4(0x5c9e) << ':'
              << hex4(kMonsterDeathSoundCursor)
              << "/p" << static_cast<int>(kMonsterDeathSoundPriority)
              << " weapon_switch=" << hex4(0x6844) << ':'
              << hex4(kWeaponSwitchSoundCursor)
              << "/p" << static_cast<int>(kWeaponSwitchSoundPriority)
              << " launch_pad=" << hex4(0x6924) << ':'
              << hex4(kLaunchPadSoundCursor)
              << "/p" << static_cast<int>(kLaunchPadSoundPriority)
              << " mapped_labels=" << mappedLabelList
              << " unresolved_candidates=" << unresolvedCandidateList
              << " unresolved_labels=" << unresolvedLabelList
              << " remaining_compat_hooks=" << remainingHooks
              << " capture_blockers=" << remainingCaptureBlockers
              << " rejected_objective_candidates="
              << rejectedObjectiveCandidates
              << " cursor_writes=" << list.str() << '\n';
}

void SoundDiagnostics::debugStaticSoundContexts() {
    std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
    if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
        throw std::runtime_error("LEZAC.EXE missing MZ header");
    }
    uint16_t headerParagraphs = le16(exeBytes, 0x08);
    size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
    if (imageBase != 0x0770) {
        throw std::runtime_error("LEZAC.EXE image base changed for sound context scan");
    }

    auto requireBytes = [&](uint16_t offset, const std::string& hex,
                            const std::string& label) {
        std::vector<uint8_t> expected = parseHexByteList(hex);
        size_t p = imageBase + offset;
        if (p + expected.size() > exeBytes.size()) {
            throw std::runtime_error(label + " context extends past LEZAC.EXE");
        }
        for (size_t i = 0; i < expected.size(); ++i) {
            if (exeBytes[p + i] != expected[i]) {
                throw std::runtime_error(label + " context bytes changed");
            }
        }
    };
    auto imageContainsAscii = [&](const std::string& needle) {
        std::vector<uint8_t> bytes(needle.begin(), needle.end());
        return std::search(exeBytes.begin() + static_cast<long>(imageBase),
                           exeBytes.end(), bytes.begin(), bytes.end()) != exeBytes.end();
    };
    auto priorityString = [](uint8_t priority) {
        if (priority == 0) return std::string("deferred");
        return std::string("p") + std::to_string(static_cast<int>(priority));
    };

    requireBytes(0x1857, "c7 06 74 20 78 00 c6 06 9f 79 0b e8 f5 fd",
                 "name-entry 0x1857 sound write");
    requireBytes(0x1a44, "c7 06 74 20 08 00 c6 06 9f 79 0b e8 08 fc",
                 "name-entry 0x1a44 sound write");
    requireBytes(0x1d42, "c2 02 00", "end-flow dispatcher return");
    requireBytes(0x1d45, "09 66 6f 6e 74 73 2e 73 70 72 0b 62 6f 6d 62 61 20 62 6f 6e 75 73",
                 "post-end-flow font/bonus strings");
    requireBytes(0x1d9c, "c7 06 74 20 3d 00 c6 06 9f 79 0a e8 b0 f8",
                 "post-end-flow 0x1d9c sound write");
    requireBytes(0x202d, "c7 06 74 20 21 00 e8 24 f6",
                 "record-table 0x202d sound write");
    requireBytes(0x2083, "c7 06 74 20 24 00 c6 06 9f 79 02 e8 c9 f5",
                 "record-table 0x2083 sound write");

    if (!imageContainsAscii("inserisci il tuo nome;") ||
        !imageContainsAscii("punteggi migliori") ||
        !imageContainsAscii("bomba bonus")) {
        throw std::runtime_error("record/menu sound context strings changed");
    }
    for (const StaticSoundContext& context : kRecordUiSoundContexts) {
        if (context.offset >= kEndFlowDispatcherStart &&
            context.offset <= kEndFlowDispatcherRet) {
            throw std::runtime_error("record UI sound context overlaps end-flow dispatcher");
        }
    }
    if (!(0x1d9c > kEndFlowDispatcherRet && 0x1d9c < 0x202d)) {
        throw std::runtime_error("post-end-flow sound context ordering changed");
    }

    std::ostringstream recordContexts;
    for (size_t i = 0; i < kRecordUiSoundContexts.size(); ++i) {
        if (i != 0) recordContexts << ',';
        const StaticSoundContext& context = kRecordUiSoundContexts[i];
        recordContexts << hex4(context.offset) << ':' << hex4(context.cursor)
                       << '/' << priorityString(context.priority) << ':'
                       << context.context;
    }

    std::cout << "static_sound_contexts=ok"
              << " image_base=0x0770"
              << " end_flow_dispatcher=" << hex4(kEndFlowDispatcherStart)
              << ".." << hex4(kEndFlowDispatcherRet)
              << " first_post_end_flow_sound=" << hex4(0x1d9c)
              << " level_complete_static_candidate=none"
              << " record_ui_writes=" << recordContexts.str()
              << " strings=inserisci_il_tuo_nome,punteggi_migliori,bomba_bonus"
              << " remaining_compat_hooks=objective_pickup,level_complete"
              << '\n';
}

void SoundDiagnostics::debugStaticSoundUnresolvedContexts() {
    struct UnresolvedContext {
        uint16_t offset;
        uint16_t cursor;
        int priority;
        uint16_t priorityOffset;
        const char* priorityPlacement;
        int expectedLocalLatchCalls;
        const char* region;
        const char* captureClass;
        const char* label;
        const char* bytes;
    };
    static const std::array<UnresolvedContext, 10> kContexts{{
        {0x1d9c, 0x003d, 10, 0x1da2, "inline", 1,
         "record_ui", "record_ui_static", "post_end_flow_record_region",
         "c7 06 74 20 3d 00 c6 06 9f 79 0a e8 b0 f8"},
        {0x202d, 0x0021, -1, 0x0000, "none", 1,
         "record_ui", "record_ui_static", "record_table_cursor_only",
         "c7 06 74 20 21 00 e8 24 f6"},
        {0x2c04, 0x0078, 11, 0x2c0a, "inline", 1,
         "pre_new_game_setup", "pre_new_game_static", "cursor_0078_priority11",
         "c7 06 74 20 78 00 c6 06 9f 79 0b e8 48 ea"},
        {0x49bd, 0x0027, 5, 0x49c3, "inline", 1,
         "explosion_playback", "explosion_static", "cursor_0027_priority5",
         "c7 06 74 20 27 00 c6 06 9f 79 05 e8 8f cc"},
        {0x4b2c, 0x0021, 2, 0x4b27, "preceding", 1,
         "explosion_playback", "explosion_static", "collapse_playback_rejected",
         "c7 06 74 20 21 00 e8 25 cb"},
        {0x4d3c, 0x2710, -1, 0x0000, "none", 0,
         "effect_extent_scan", "effect_extent_static", "cursor_2710",
         "c7 06 74 20 10 27 c7 06 72 20 00 00 c6 06 1e 66 00"},
        {0x4dd3, 0x2710, -1, 0x0000, "none", 0,
         "effect_extent_scan", "effect_extent_static", "cursor_2710",
         "c7 06 74 20 10 27 c7 06 72 20 00 00 c6 06 1e 66 00"},
        {0x5e81, 0x0069, 4, 0x5e87, "inline", 1,
         "contact_scanner", "actor_contact_runtime", "cursor_0069_priority4",
         "c7 06 74 20 69 00 c6 06 9f 79 04 e8 cb b7"},
        {0x7386, 0x0021, 1, 0x7381, "preceding", 1,
         "actor_update", "actor_contact_runtime", "cursor_0021_priority1",
         "c7 06 74 20 21 00 e8 cb a2"},
        {0x789c, 0x0001, -1, 0x0000, "none", 0,
         "post_actor_update_no_latch", "post_actor_update_no_latch",
         "cursor_0001_no_latch",
         "c7 06 74 20 01 00 eb 04 ff 06 74 20"},
    }};

    std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
    if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
        throw std::runtime_error("LEZAC.EXE missing MZ header");
    }
    uint16_t headerParagraphs = le16(exeBytes, 0x08);
    size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
    if (imageBase != 0x0770) {
        throw std::runtime_error("LEZAC.EXE image base changed for unresolved sound scan");
    }

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
    auto localLatchCallCount = [&](uint16_t offset) {
        int count = 0;
        for (size_t relOff = 0; relOff < 24; ++relOff) {
            size_t callOff = static_cast<size_t>(offset) + relOff;
            size_t p = imageBase + callOff;
            if (p + 3 > exeBytes.size() || exeBytes[p] != 0xe8) continue;
            uint16_t rawRel = le16(exeBytes, p + 1);
            int signedRel = rawRel >= 0x8000u
                                ? static_cast<int>(rawRel) - 0x10000
                                : static_cast<int>(rawRel);
            uint16_t target = static_cast<uint16_t>(callOff + 3 + signedRel);
            if (target == 0x165a) ++count;
        }
        return count;
    };
    auto requirePriority = [&](const UnresolvedContext& context) {
        if (context.priority < 0) return;
        size_t p = imageBase + context.priorityOffset;
        if (p + 5 > exeBytes.size() || exeBytes[p] != 0xc6 ||
            exeBytes[p + 1] != 0x06 || exeBytes[p + 2] != 0x9f ||
            exeBytes[p + 3] != 0x79 ||
            exeBytes[p + 4] != static_cast<uint8_t>(context.priority)) {
            throw std::runtime_error(std::string(context.label) +
                                     " priority bytes changed");
        }
    };

    int localLatch = 0;
    int localLatchRefs = 0;
    int inlinePriority = 0;
    int precedingPriority = 0;
    int noPriority = 0;
    int noLatch = 0;
    int directSweep = 0;
    int cursor2710 = 0;
    std::map<std::string, int> regionCounts;
    std::map<std::string, int> captureClassCounts;
    std::ostringstream contexts;
    std::ostringstream actorContactCaptureCandidates;
    for (size_t i = 0; i < kContexts.size(); ++i) {
        const UnresolvedContext& context = kContexts[i];
        requireBytes(context.offset, context.bytes, context.label);
        requirePriority(context);
        ++regionCounts[context.region];
        ++captureClassCounts[context.captureClass];
        int calls = localLatchCallCount(context.offset);
        if (calls != context.expectedLocalLatchCalls) {
            throw std::runtime_error(std::string(context.label) +
                                     " local latch call count changed");
        }
        if (calls > 0) ++localLatch;
        else ++noLatch;
        localLatchRefs += calls;
        if (std::string(context.priorityPlacement) == "inline") {
            ++inlinePriority;
        } else if (std::string(context.priorityPlacement) == "preceding") {
            ++precedingPriority;
        } else {
            ++noPriority;
        }
        if (sound_.isDirectSoundSweep(context.cursor)) ++directSweep;
        if (context.cursor == 0x2710) ++cursor2710;
        if (std::string(context.captureClass) == "actor_contact_runtime") {
            if (actorContactCaptureCandidates.tellp() > 0) {
                actorContactCaptureCandidates << ',';
            }
            actorContactCaptureCandidates << hex4(context.offset) << ':'
                                          << context.region;
        }

        if (i != 0) contexts << ',';
        contexts << hex4(context.offset) << ':' << hex4(context.cursor) << '/';
        if (context.priority >= 0) {
            contexts << 'p' << context.priority;
        } else {
            contexts << "no_priority";
        }
        contexts << ':' << context.priorityPlacement
                 << ":latch" << calls << ':' << context.region << ':'
                 << context.label;
    }

    auto regionCountText = [&] {
        std::ostringstream out;
        bool first = true;
        for (const auto& entry : regionCounts) {
            if (!first) out << ',';
            first = false;
            out << entry.first << ':' << entry.second;
        }
        return out.str();
    };
    auto captureClassCountText = [&] {
        std::ostringstream out;
        bool first = true;
        for (const auto& entry : captureClassCounts) {
            if (!first) out << ',';
            first = false;
            out << entry.first << ':' << entry.second;
        }
        return out.str();
    };
    std::string contextList = contexts.str();
    std::string regionCountsList = regionCountText();
    std::string captureClassCountsList = captureClassCountText();
    std::string actorContactCaptureCandidateList =
        actorContactCaptureCandidates.str();
    if (localLatch != 7 || localLatchRefs != 7 || inlinePriority != 4 ||
        precedingPriority != 2 || noPriority != 4 || noLatch != 3 ||
        directSweep != 0 || cursor2710 != 2) {
        throw std::runtime_error("unresolved static sound context summary changed");
    }
    if (regionCountsList !=
            "actor_update:1,contact_scanner:1,effect_extent_scan:2,"
            "explosion_playback:2,post_actor_update_no_latch:1,"
            "pre_new_game_setup:1,record_ui:2") {
        throw std::runtime_error("unresolved static sound region counts changed");
    }
    if (captureClassCountsList !=
            "actor_contact_runtime:2,effect_extent_static:2,"
            "explosion_static:2,post_actor_update_no_latch:1,"
            "pre_new_game_static:1,record_ui_static:2") {
        throw std::runtime_error("unresolved static sound capture classes changed");
    }
    if (actorContactCaptureCandidateList !=
            "0x5e81:contact_scanner,0x7386:actor_update") {
        throw std::runtime_error(
            "unresolved static sound actor/contact capture list changed");
    }
    if (contextList !=
            "0x1d9c:0x003d/p10:inline:latch1:record_ui:post_end_flow_record_region,"
            "0x202d:0x0021/no_priority:none:latch1:record_ui:record_table_cursor_only,"
            "0x2c04:0x0078/p11:inline:latch1:pre_new_game_setup:cursor_0078_priority11,"
            "0x49bd:0x0027/p5:inline:latch1:explosion_playback:cursor_0027_priority5,"
            "0x4b2c:0x0021/p2:preceding:latch1:explosion_playback:collapse_playback_rejected,"
            "0x4d3c:0x2710/no_priority:none:latch0:effect_extent_scan:cursor_2710,"
            "0x4dd3:0x2710/no_priority:none:latch0:effect_extent_scan:cursor_2710,"
            "0x5e81:0x0069/p4:inline:latch1:contact_scanner:cursor_0069_priority4,"
            "0x7386:0x0021/p1:preceding:latch1:actor_update:cursor_0021_priority1,"
            "0x789c:0x0001/no_priority:none:latch0:post_actor_update_no_latch:cursor_0001_no_latch") {
        throw std::runtime_error("unresolved static sound context list changed");
    }

    std::cout << "static_sound_unresolved_contexts=ok"
              << " writes=" << kContexts.size()
              << " image_base=0x0770"
              << " latch=0x165a"
              << " local_latch=" << localLatch
              << " local_latch_refs=" << localLatchRefs
              << " inline_priority=" << inlinePriority
              << " preceding_priority=" << precedingPriority
              << " no_priority=" << noPriority
              << " no_latch=" << noLatch
              << " direct_sweep=" << directSweep
              << " cursor_2710=" << cursor2710
              << " region_counts=" << regionCountsList
              << " capture_classes=" << captureClassCountsList
              << " actor_contact_capture_candidates="
              << actorContactCaptureCandidateList
              << " contexts=" << contextList
              << '\n';
}

void SoundDiagnostics::debugSoundRuntimeCaptureQueue() {
    std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
    if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
        throw std::runtime_error("LEZAC.EXE missing MZ header");
    }
    uint16_t headerParagraphs = le16(exeBytes, 0x08);
    size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
    if (imageBase != 0x0770) {
        throw std::runtime_error("LEZAC.EXE image base changed for sound runtime queue");
    }

    auto requireBytes = [&](const RuntimeSoundCaptureTarget& target) {
        std::vector<uint8_t> expected = parseHexByteList(target.bytes);
        size_t p = imageBase + target.offset;
        if (p + expected.size() > exeBytes.size()) {
            throw std::runtime_error(std::string(target.scenario) +
                                     " bytes extend past LEZAC.EXE");
        }
        for (size_t i = 0; i < expected.size(); ++i) {
            if (exeBytes[p + i] != expected[i]) {
                throw std::runtime_error(std::string(target.scenario) +
                                         " bytes changed");
            }
        }
    };

    std::ostringstream targets;
    std::map<std::string, int> regionCounts;
    std::map<std::string, int> routeClassCounts;
    for (size_t i = 0; i < kActorContactSoundCaptureTargets.size(); ++i) {
        const RuntimeSoundCaptureTarget& target =
            kActorContactSoundCaptureTargets[i];
        requireBytes(target);
        ++regionCounts[target.region];
        ++routeClassCounts[target.routeClass];
        if (i != 0) targets << ',';
        targets << target.scenario << ':' << hex4(target.offset) << ':'
                << hex4(target.cursor) << "/p"
                << static_cast<int>(target.priority) << ':' << target.region
                << ':' << target.label << ':' << target.status << ':'
                << target.routeClass << ':' << target.captureBlocker;
    }

    std::ostringstream regionText;
    bool first = true;
    for (const auto& entry : regionCounts) {
        if (!first) regionText << ',';
        first = false;
        regionText << entry.first << ':' << entry.second;
    }

    std::ostringstream routeClassText;
    first = true;
    for (const auto& entry : routeClassCounts) {
        if (!first) routeClassText << ',';
        first = false;
        routeClassText << entry.first << ':' << entry.second;
    }

    const std::string targetText = targets.str();
    const std::string regionList = regionText.str();
    const std::string routeClassList = routeClassText.str();
    if (targetText !=
            "actor_update_runtime_cursor_0024_sound:0x6844:0x0024/p2:actor_update:cursor_0024_priority2:staged:natural:normalized_fixture_required,"
            "actor_update_runtime_cursor_0035_sound:0x6924:0x0035/p5:actor_update:launch_pad:staged:natural:level6_route_required,"
            "actor_update_runtime_cursor_0021_sound:0x7386:0x0021/p1:actor_update:cursor_0021_priority1:staged:natural:semantic_event_unknown,"
            "contact_scanner_runtime_sound:0x5e81:0x0069/p4:contact_scanner:cursor_0069_priority4:seeded_only:runtime_seeded:shipped_actor_modes_exclude_6") {
        throw std::runtime_error("sound runtime capture target queue changed");
    }
    if (regionList != "actor_update:3,contact_scanner:1") {
        throw std::runtime_error("sound runtime capture region summary changed");
    }
    if (routeClassList != "natural:3,runtime_seeded:1") {
        throw std::runtime_error("sound runtime capture route classes changed");
    }

    std::cout << "sound_runtime_capture_queue=ok"
              << " capture_class=actor_contact_runtime"
              << " targets=" << kActorContactSoundCaptureTargets.size()
              << " first_target=actor_update_runtime_cursor_0024_sound"
              << " helper=tools/capture_original_sound_callsite_procmem.sh"
              << " route_sweep=tools/sweep_original_sound_callsite_routes.py"
              << " oracle=--debug-sound-callsite-oracle"
              << " fixture_prefix=sound_callsite_oracle_original"
              << " promotion_status=runtime_fixture_required"
              << " approval_flags=LEZAC_SOUND_CALLSITE_APPROVE_PROCMEM,"
              << "LEZAC_SOUND_CALLSITE_APPROVE_RUNTIME_INSTRUMENTATION"
              << " original_cursor_priority_claim=0"
              << " regions=" << regionList
              << " route_classes=" << routeClassList
              << " state6_capture_blocker=shipped_actor_modes_exclude_6"
              << " target_queue=" << targetText
              << '\n';
}

int SoundDiagnostics::debugSoundCallsiteOracle(const std::string& path, bool expectError) {
    auto fixtureName = [](const std::string& inputPath) {
        size_t slash = inputPath.find_last_of("/\\");
        std::string name =
            slash == std::string::npos ? inputPath : inputPath.substr(slash + 1);
        size_t dot = name.find_last_of('.');
        if (dot != std::string::npos) name = name.substr(0, dot);
        return name;
    };
    const std::string fixture = fixtureName(path);

    auto bareHex4 = [](uint16_t value) {
        std::ostringstream oss;
        oss << std::hex << std::nouppercase << std::setw(4)
            << std::setfill('0') << value;
        return oss.str();
    };
    auto hex4 = [&](uint16_t value) { return "0x" + bareHex4(value); };
    auto trim = [](std::string value) {
        while (!value.empty() &&
               std::isspace(static_cast<unsigned char>(value.front()))) {
            value.erase(value.begin());
        }
        while (!value.empty() &&
               std::isspace(static_cast<unsigned char>(value.back()))) {
            value.pop_back();
        }
        return value;
    };
    auto fail = [&](const std::string& reason) {
        throw std::runtime_error("sound_callsite_oracle=error fixture=" +
                                 fixture + " reason=" + reason);
    };
    auto parseHex16 = [&](std::string token,
                          const std::string& field) -> uint16_t {
        token = trim(token);
        if (token.rfind("0x", 0) == 0 || token.rfind("0X", 0) == 0) {
            token = token.substr(2);
        }
        if (token.empty() || token.size() > 4 ||
            !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                return std::isxdigit(ch) != 0;
            })) {
            fail("bad_hex16 field=" + field + " token=" + token);
        }
        return static_cast<uint16_t>(std::stoul(token, nullptr, 16));
    };
    auto parseHexByte = [&](const std::string& token,
                            uint16_t address) -> uint8_t {
        if (token.size() != 2 ||
            !std::all_of(token.begin(), token.end(), [](unsigned char ch) {
                return std::isxdigit(ch) != 0;
            })) {
            fail("non_hex_byte token=" + token + " address=" +
                 bareHex4(address));
        }
        return static_cast<uint8_t>(std::stoul(token, nullptr, 16));
    };
    auto parseIntAuto = [&](const std::string& token,
                            const std::string& field) -> int {
        try {
            size_t parsed = 0;
            long value = std::stol(token, &parsed, 0);
            if (parsed != token.size()) {
                fail("bad_int field=" + field + " token=" + token);
            }
            return static_cast<int>(value);
        } catch (const std::exception&) {
            fail("bad_int field=" + field + " token=" + token);
        }
        return 0;
    };
    auto parseFields = [&](const std::string& body,
                           const std::string& record) {
        std::map<std::string, std::string> fields;
        std::istringstream stream(body);
        std::string token;
        while (stream >> token) {
            size_t equals = token.find('=');
            if (equals == std::string::npos || equals == 0 ||
                equals + 1 >= token.size()) {
                fail("bad_field record=" + record + " token=" + token);
            }
            fields[token.substr(0, equals)] = token.substr(equals + 1);
        }
        return fields;
    };
    auto requireField = [&](const std::map<std::string, std::string>& fields,
                            const std::string& name,
                            const std::string& record) -> std::string {
        auto found = fields.find(name);
        if (found == fields.end()) {
            fail("missing_field record=" + record + " field=" + name);
        }
        return found->second;
    };
    auto parseFarPointer = [&](const std::string& token,
                               const std::string& field) {
        size_t colon = token.find(':');
        if (colon == std::string::npos || colon == 0 ||
            colon + 1 >= token.size()) {
            fail("bad_far_pointer field=" + field + " token=" + token);
        }
        return std::pair<uint16_t, uint16_t>{
            parseHex16(token.substr(0, colon), field + ".segment"),
            parseHex16(token.substr(colon + 1), field + ".offset")};
    };

    struct SoundRequestRecord {
        bool present = false;
        std::string label;
        uint16_t callsiteSegment = 0;
        uint16_t callsiteOffset = 0;
        uint16_t latchSegment = 0;
        uint16_t latchOffset = 0;
        uint16_t cursor = 0;
        int priority = 0;
        int activeBefore = 0;
        int currentPriorityBefore = 0;
        uint16_t pendingCursor = 0;
        int pendingPriority = 0;
        int accepted = 0;
        int activeAfter = 0;
        int currentPriorityAfter = 0;
        uint16_t currentCursorAfter = 0;
        int directSweep = 0;
    };

    try {
        std::string text = readTextFile(path);
        std::vector<uint8_t> memory(0x10000);
        std::vector<bool> present(0x10000, false);
        uint16_t runtimeCs = 0;
        uint16_t runtimeDs = 0;
        bool haveRuntimeCs = false;
        bool haveRuntimeDs = false;
        bool tempCopy = false;
        bool visualClaim = false;
        bool haveScenario = false;
        bool haveLevel = false;
        std::string scenario;
        int level = 0;
        SoundRequestRecord request;
        std::set<uint16_t> breakOffsets;
        int breakCount = 0;
        int dumpBytes = 0;

        std::istringstream lines(text);
        std::string line;
        std::regex keyRe("^([A-Za-z0-9_]+)=(.*)$");
        std::regex breakRe(
            "^break\\s+ghidra=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+"
            "runtime=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+label=([^\\s]+).*$");
        std::regex dumpRe("^dump\\s+DS:([0-9A-Fa-f]{4}).*$");
        std::regex rowRe("^([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\\s+(.+)$");
        uint16_t currentDump = 0;
        bool inDump = false;
        while (std::getline(lines, line)) {
            line = trim(line);
            if (line.empty() || line[0] == '#') continue;

            std::smatch match;
            if (std::regex_match(line, match, keyRe)) {
                std::string key = match[1].str();
                std::string value = trim(match[2].str());
                if (key == "runtime_cs") {
                    runtimeCs = parseHex16(value, key);
                    haveRuntimeCs = true;
                } else if (key == "runtime_ds") {
                    runtimeDs = parseHex16(value, key);
                    haveRuntimeDs = true;
                } else if (key == "temp_copy") {
                    tempCopy = value == "1";
                } else if (key == "visual_claim") {
                    visualClaim = value != "0";
                } else if (key == "scenario") {
                    scenario = value;
                    haveScenario = true;
                } else if (key == "level") {
                    level = parseIntAuto(value, key);
                    haveLevel = true;
                }
                continue;
            }

            if (line.rfind("sound_request ", 0) == 0) {
                auto fields = parseFields(line.substr(14), "sound_request");
                request.present = true;
                request.label = requireField(fields, "label", "sound_request");
                auto callsite = parseFarPointer(
                    requireField(fields, "callsite", "sound_request"),
                    "sound_request.callsite");
                request.callsiteSegment = callsite.first;
                request.callsiteOffset = callsite.second;
                auto latch = parseFarPointer(
                    requireField(fields, "latch", "sound_request"),
                    "sound_request.latch");
                request.latchSegment = latch.first;
                request.latchOffset = latch.second;
                request.cursor = parseHex16(
                    requireField(fields, "cursor", "sound_request"),
                    "sound_request.cursor");
                request.priority = parseIntAuto(
                    requireField(fields, "priority", "sound_request"),
                    "sound_request.priority");
                request.activeBefore = parseIntAuto(
                    requireField(fields, "active_before", "sound_request"),
                    "sound_request.active_before");
                request.currentPriorityBefore = parseIntAuto(
                    requireField(fields, "current_priority_before",
                                 "sound_request"),
                    "sound_request.current_priority_before");
                request.pendingCursor = parseHex16(
                    requireField(fields, "pending_cursor", "sound_request"),
                    "sound_request.pending_cursor");
                request.pendingPriority = parseIntAuto(
                    requireField(fields, "pending_priority", "sound_request"),
                    "sound_request.pending_priority");
                request.accepted = parseIntAuto(
                    requireField(fields, "accepted", "sound_request"),
                    "sound_request.accepted");
                request.activeAfter = parseIntAuto(
                    requireField(fields, "active_after", "sound_request"),
                    "sound_request.active_after");
                request.currentPriorityAfter = parseIntAuto(
                    requireField(fields, "current_priority_after",
                                 "sound_request"),
                    "sound_request.current_priority_after");
                request.currentCursorAfter = parseHex16(
                    requireField(fields, "current_cursor_after", "sound_request"),
                    "sound_request.current_cursor_after");
                request.directSweep = parseIntAuto(
                    requireField(fields, "direct_sweep", "sound_request"),
                    "sound_request.direct_sweep");
                continue;
            }

            if (std::regex_match(line, match, breakRe)) {
                if (!haveRuntimeCs) fail("runtime_cs_missing_before_break");
                uint16_t ghidraSegment = parseHex16(match[1].str(), "ghidra");
                uint16_t ghidraOffset = parseHex16(match[2].str(), "ghidra");
                uint16_t runtimeSegment = parseHex16(match[3].str(), "runtime");
                uint16_t runtimeOffset = parseHex16(match[4].str(), "runtime");
                if (ghidraSegment != 0x1000) {
                    fail("breakpoint_ghidra_segment expected=0x1000 actual=" +
                         hex4(ghidraSegment));
                }
                if (runtimeSegment != runtimeCs) {
                    fail("breakpoint_segment_mismatch expected=" + hex4(runtimeCs) +
                         " actual=" + hex4(runtimeSegment));
                }
                if (runtimeOffset != ghidraOffset) {
                    fail("breakpoint_offset_mismatch expected=" +
                         bareHex4(ghidraOffset) + " actual=" +
                         bareHex4(runtimeOffset));
                }
                breakOffsets.insert(ghidraOffset);
                ++breakCount;
                continue;
            }

            if (std::regex_match(line, match, dumpRe)) {
                currentDump = parseHex16(match[1].str(), "dump");
                inDump = true;
                continue;
            }

            if (std::regex_match(line, match, rowRe)) {
                if (!inDump) fail("dump_row_without_header");
                if (!haveRuntimeDs) fail("runtime_ds_missing_before_dump");
                uint16_t segment = parseHex16(match[1].str(), "row_segment");
                uint16_t address = parseHex16(match[2].str(), "row_address");
                if (segment != runtimeDs) {
                    fail("dump_segment_mismatch expected=" + hex4(runtimeDs) +
                         " actual=" + hex4(segment) +
                         " address=" + bareHex4(address));
                }
                if (address < currentDump) {
                    fail("dump_address_before_header header=" + bareHex4(currentDump) +
                         " address=" + bareHex4(address));
                }
                std::istringstream byteStream(match[3].str());
                std::string token;
                uint16_t cursor = address;
                while (byteStream >> token) {
                    memory[cursor] = parseHexByte(token, cursor);
                    present[cursor] = true;
                    ++cursor;
                    ++dumpBytes;
                }
                continue;
            }

            fail("unrecognized_line");
        }

        auto requireByteIfPresent = [&](uint16_t address,
                                        uint8_t expected,
                                        const std::string& reason) {
            if (present[address] && memory[address] != expected) {
                fail(reason + " expected=" + hex4(expected) +
                     " actual=" + hex4(memory[address]));
            }
        };
        auto requireWordIfPresent = [&](uint16_t address,
                                        uint16_t expected,
                                        const std::string& reason) {
            if (present[address] && present[static_cast<uint16_t>(address + 1)]) {
                uint16_t actual = static_cast<uint16_t>(
                    memory[address] |
                    (memory[static_cast<uint16_t>(address + 1)] << 8));
                if (actual != expected) {
                    fail(reason + " expected=" + hex4(expected) +
                         " actual=" + hex4(actual));
                }
            }
        };

        if (!haveRuntimeCs) fail("runtime_cs_missing");
        if (!haveRuntimeDs) fail("runtime_ds_missing");
        if (!haveScenario) fail("scenario_missing");
        if (!haveLevel) fail("level_missing");
        if (visualClaim) fail("visual_claim_not_supported");
        if (!request.present) fail("sound_request_missing");
        if (request.callsiteSegment != 0x1000) {
            fail("callsite_segment_not_1000 actual=" + hex4(request.callsiteSegment));
        }
        if (request.latchSegment != 0x1000 || request.latchOffset != 0x165a) {
            fail("latch_address_mismatch actual=" + hex4(request.latchSegment) +
                 ":" + bareHex4(request.latchOffset));
        }
        if (breakOffsets.count(request.callsiteOffset) == 0) {
            fail("missing_breakpoint offset=" + bareHex4(request.callsiteOffset));
        }
        if (breakOffsets.count(request.latchOffset) == 0) {
            fail("missing_breakpoint offset=" + bareHex4(request.latchOffset));
        }
        if (request.pendingCursor != request.cursor) {
            fail("pending_cursor_mismatch expected=" + hex4(request.cursor) +
                 " actual=" + hex4(request.pendingCursor));
        }
        if (request.pendingPriority != request.priority) {
            fail("pending_priority_mismatch expected=" +
                 std::to_string(request.priority) + " actual=" +
                 std::to_string(request.pendingPriority));
        }
        if (request.accepted != 0) {
            if (request.activeAfter == 0) fail("accepted_but_inactive_after");
            if (request.currentPriorityAfter != request.priority) {
                fail("accepted_priority_mismatch expected=" +
                     std::to_string(request.priority) + " actual=" +
                     std::to_string(request.currentPriorityAfter));
            }
            if (request.currentCursorAfter != request.cursor) {
                fail("accepted_cursor_mismatch expected=" + hex4(request.cursor) +
                     " actual=" + hex4(request.currentCursorAfter));
            }
        }
        int expectedDirectSweep = request.cursor > 0xea60 ? 1 : 0;
        if (request.directSweep != expectedDirectSweep) {
            fail("direct_sweep_mismatch expected=" +
                 std::to_string(expectedDirectSweep) + " actual=" +
                 std::to_string(request.directSweep));
        }

        requireWordIfPresent(0x2074, request.pendingCursor,
                             "pending_cursor_dump_mismatch");
        requireByteIfPresent(0x799f, static_cast<uint8_t>(request.pendingPriority),
                             "pending_priority_dump_mismatch");
        requireByteIfPresent(0x799e,
                             static_cast<uint8_t>(request.currentPriorityAfter),
                             "current_priority_dump_mismatch");
        requireWordIfPresent(0x78c0, request.currentCursorAfter,
                             "current_cursor_dump_mismatch");
        requireByteIfPresent(0x79c4, static_cast<uint8_t>(request.activeAfter),
                             "active_flag_dump_mismatch");

        std::cout << "sound_callsite_oracle=ok fixture=" << fixture
                  << " scenario=" << scenario
                  << " level=" << level
                  << " runtime_cs=" << hex4(runtimeCs)
                  << " runtime_ds=" << hex4(runtimeDs)
                  << " label=" << request.label
                  << " callsite=" << hex4(request.callsiteSegment) << ':'
                  << bareHex4(request.callsiteOffset)
                  << " latch=" << hex4(request.latchSegment) << ':'
                  << bareHex4(request.latchOffset)
                  << " cursor=" << hex4(request.cursor)
                  << " priority=" << request.priority
                  << " active_before=" << request.activeBefore
                  << " current_priority_before=" << request.currentPriorityBefore
                  << " accepted=" << request.accepted
                  << " active_after=" << request.activeAfter
                  << " current_priority_after=" << request.currentPriorityAfter
                  << " current_cursor_after=" << hex4(request.currentCursorAfter)
                  << " direct_sweep=" << request.directSweep
                  << " breaks=" << breakCount
                  << " dump_bytes=" << dumpBytes
                  << " temp_copy=" << (tempCopy ? 1 : 0)
                  << " visual_claim=0\n";
        if (expectError) {
            std::cout << "sound_callsite_oracle=error fixture=" << fixture
                      << " reason=expected_error_missing\n";
            return 1;
        }
        return 0;
    } catch (const std::exception& e) {
        std::cout << e.what() << '\n';
        return expectError ? 0 : 1;
    }
}

void SoundDiagnostics::debugSoundHookEvidence(const std::string& fixturePath) {
    std::ifstream in(fixturePath);
    if (!in) throw std::runtime_error("cannot open " + fixturePath);
    std::map<std::string, std::string> kv;
    std::map<std::string, std::pair<uint16_t, int>> hooks;
    std::string line;
    while (std::getline(in, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || line[0] == '#') continue;
        if (line.rfind("hook ", 0) == 0) {
            std::istringstream hs(line.substr(5));
            std::string name, curTok, priTok;
            hs >> name >> curTok >> priTok;
            if (curTok.rfind("cursor=", 0) != 0 ||
                priTok.rfind("priority=", 0) != 0) {
                throw std::runtime_error("malformed hook row: " + line);
            }
            hooks[name] = {static_cast<uint16_t>(
                               std::stoul(curTok.substr(7), nullptr, 16)),
                           std::stoi(priTok.substr(9))};
            continue;
        }
        auto eq = line.find('=');
        if (eq == std::string::npos) continue;
        kv[line.substr(0, eq)] = line.substr(eq + 1);
    }
    auto req = [&](const char* key) -> std::string {
        auto it = kv.find(key);
        if (it == kv.end()) {
            throw std::runtime_error(std::string("missing key ") + key);
        }
        return it->second;
    };
    if (req("sound_callsite_original") != "level1" ||
        req("runtime_ds") != "0c8f" || req("visual_claim") != "0" ||
        req("accepted_cursor_offset") != "0x78c0" ||
        req("accepted_priority_offset") != "0x799e") {
        throw std::runtime_error("sound hook fixture header mismatch");
    }
    // Every live compatibility hook must carry the captured cursor and
    // priority; a mismatch means the port would play a different sound
    // than the original.
    for (const RemainingSoundCompatibilityHook& hook :
         kRemainingSoundCompatibilityHooks) {
        auto it = hooks.find(hook.hook);
        if (it == hooks.end()) {
            throw std::runtime_error(std::string("fixture lacks hook ") +
                                     hook.hook);
        }
        if (hook.capturedCursor != it->second.first ||
            static_cast<int>(hook.capturedPriority) != it->second.second) {
            throw std::runtime_error(std::string("hook ") + hook.hook +
                                     " diverges from captured evidence");
        }
        // The synthesized audio must come from the captured cursor.
        if (sound_.synthesizeSoundCursor(hook.capturedCursor).empty() &&
            hook.capturedCursor != 0) {
            throw std::runtime_error(std::string("hook ") + hook.hook +
                                     " captured cursor yields no audio");
        }
    }
    std::cout << "sound_hook_evidence=ok hooks="
              << kRemainingSoundCompatibilityHooks.size()
              << " objective_pickup=" << hex4(hooks["objective_pickup"].first)
              << "/p" << hooks["objective_pickup"].second
              << " level_complete=" << hex4(hooks["level_complete"].first)
              << "/p" << hooks["level_complete"].second
              << " accepted_pair=0x78c0/0x799e visual_claim=0\n";
}

}  // namespace lezac::diagnostics
