#include "diagnostics/ui_diagnostics.hpp"
#include "resources/io.hpp"
#include "resources/json.hpp"
#include "resources/binary.hpp"
#include <algorithm>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>

namespace lezac::diagnostics {
using namespace resources;
namespace {
constexpr uint16_t kEndFlowDispatcherStart = 0x1b14;
constexpr uint16_t kEndFlowDispatcherRet = 0x1d42;
std::string hex4(uint16_t value) {
    std::ostringstream oss;
    oss << "0x" << std::hex << std::nouppercase << std::setw(4) << std::setfill('0') << value;
    return oss.str();
}
}

void UiDiagnostics::debugRecordUpdate(const ui::RecordStore& store, const std::string& path) {
    std::vector<Record> testRecords = store.records();
    bool changed = ui::RecordStore::insertRecord(testRecords, makeRecord(999999u, 9u, "TEST"));
    if (!changed) {
        throw std::runtime_error("test record was not inserted");
    }
    saveRecords(path, testRecords);
    auto reloaded = loadRecords(path);
    if (reloaded.empty() || reloaded[0].score != 999999u ||
        reloaded[0].level != 9u || reloaded[0].name != "TEST") {
        throw std::runtime_error("saved test record did not round-trip");
    }
    int binary = isJsonRecordPath(path) ? 0 : 1;
    size_t rawSize = 0;
    std::string encodedName = encodeRecordName(reloaded[0].name);
    if (binary) {
        auto bytes = readFile(path);
        rawSize = bytes.size();
        if (bytes.size() != 92 || bytes[0] != 7 || le32(bytes, 1) != 999999u ||
            bytes[5] != 9u) {
            throw std::runtime_error("saved raw test record layout changed");
        }
        encodedName = std::string(bytes.begin() + 6, bytes.begin() + 14);
        if (encodedName != "TEST::::") {
            throw std::runtime_error("saved raw test record name encoding changed");
        }
    }
    std::cout << "record_update=ok top=" << reloaded[0].score
              << " level=" << static_cast<int>(reloaded[0].level)
              << " name=" << reloaded[0].name
              << " binary=" << binary
              << " raw_size=" << rawSize
              << " encoded=" << encodedName << '\n';
}

void UiDiagnostics::debugRecordsRawRoundtrip(const ui::RecordStore& store) {
    auto rawBytes = readFile("RECS.DAT");
    constexpr size_t kRecordSize = 13;
    if (rawBytes.empty()) {
        throw std::runtime_error("RECS.DAT raw file is empty");
    }
    uint8_t rawCount = rawBytes[0];
    if (rawCount != 7 ||
        rawBytes.size() != 1 + static_cast<size_t>(rawCount) * kRecordSize) {
        throw std::runtime_error("RECS.DAT raw layout mismatch");
    }

    auto jsonRecords = extractObjectArray(readTextFile("RECS.DAT.json"), "records");
    if (jsonRecords.size() != rawCount || store.records().size() != rawCount) {
        throw std::runtime_error("RECS.DAT JSON record count mismatch");
    }
    auto decodeRawName = [](std::string encoded) {
        std::replace(encoded.begin(), encoded.end(), ':', ' ');
        while (!encoded.empty() && encoded.back() == ' ') {
            encoded.pop_back();
        }
        return encoded.empty() ? std::string("nessuno") : encoded;
    };

    uint64_t scoreSum = 0;
    int level8Count = 0;
    int decodedAgaCount = 0;
    int encodedColonPaddedCount = 0;
    int byteSum = 0;
    int weightedSum = 0;
    uint8_t xorValue = 0;
    uint32_t previousScore = UINT32_MAX;
    for (size_t i = 0; i < rawBytes.size(); ++i) {
        uint8_t byte = rawBytes[i];
        byteSum += byte;
        weightedSum += static_cast<int>((i + 1) * byte);
        xorValue = static_cast<uint8_t>(xorValue ^ byte);
    }

    for (size_t i = 0; i < rawCount; ++i) {
        size_t off = 1 + i * kRecordSize;
        uint32_t rawScore = le32(rawBytes, off);
        uint8_t rawLevel = rawBytes[off + 4];
        std::string rawEncoded(rawBytes.begin() + static_cast<std::ptrdiff_t>(off + 5),
                               rawBytes.begin() + static_cast<std::ptrdiff_t>(off + 13));
        std::string rawDecoded = decodeRawName(rawEncoded);

        const std::string& recJson = jsonRecords[i];
        uint32_t jsonScore = static_cast<uint32_t>(extractInt(recJson, "score"));
        uint8_t jsonLevel = static_cast<uint8_t>(extractInt(recJson, "level"));
        std::string jsonEncoded = extractString(recJson, "encoded_name");
        std::string jsonDecoded = extractString(recJson, "decoded_name");
        if (rawScore != jsonScore || rawLevel != jsonLevel ||
            rawEncoded != jsonEncoded || rawDecoded != jsonDecoded ||
            store.records()[i].score != rawScore || store.records()[i].level != rawLevel ||
            store.records()[i].name != rawDecoded) {
            throw std::runtime_error("RECS.DAT raw/json record mismatch");
        }
        if (i != 0 && rawScore > previousScore) {
            throw std::runtime_error("RECS.DAT scores are no longer descending");
        }
        previousScore = rawScore;
        scoreSum += rawScore;
        if (rawLevel == 8) ++level8Count;
        if (rawDecoded == "aga") ++decodedAgaCount;
        if (rawEncoded == "aga:::::") ++encodedColonPaddedCount;
    }
    if (scoreSum != 3508890 || byteSum != 6047 ||
        weightedSum != 278918 || xorValue != 0xdd ||
        level8Count != 7 || decodedAgaCount != 7 ||
        encodedColonPaddedCount != 7) {
        throw std::runtime_error("RECS.DAT raw aggregate changed");
    }

    std::cout << "records_raw_roundtrip=ok raw_size=" << rawBytes.size()
              << " count=" << static_cast<int>(rawCount)
              << " record_size=" << kRecordSize
              << " score_sum=" << scoreSum
              << " top=" << store.records().front().score
              << " cutoff=" << store.records().back().score
              << " level8_count=" << level8Count
              << " decoded_aga=" << decodedAgaCount
              << " encoded_colon_padded=" << encodedColonPaddedCount
              << " byte_sum=" << byteSum
              << " weighted_sum=" << weightedSum
              << " xor=0x" << std::hex << std::setw(2) << std::setfill('0')
              << static_cast<int>(xorValue) << std::dec << std::setfill(' ')
              << '\n';
}

void UiDiagnostics::debugRecordEntryStaticModel() {
    std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
    if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
        throw std::runtime_error("LEZAC.EXE missing MZ header");
    }
    uint16_t headerParagraphs = le16(exeBytes, 0x08);
    size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
    if (imageBase != 0x0770) {
        throw std::runtime_error("LEZAC.EXE image base changed for record entry scan");
    }
    constexpr uint16_t kTemplate = 0x183c;
    constexpr uint16_t kRoutineStart = 0x1845;
    constexpr uint16_t kPromptSound = 0x1857;
    constexpr uint16_t kBackspaceCheck = 0x1a07;
    constexpr uint16_t kEnterCheck = 0x1a3a;
    constexpr uint16_t kCommitSound = 0x1a44;
    constexpr uint16_t kRecordShift = 0x1a76;
    constexpr uint16_t kStoredRecordPointer = 0x1a9e;
    constexpr uint16_t kNameCopy = 0x1aab;
    constexpr uint16_t kScoreWrite = 0x1ac0;
    constexpr uint16_t kRoutineRet = 0x1ad6;

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
        auto begin = exeBytes.begin() + static_cast<long>(imageBase + kRoutineStart);
        auto end = exeBytes.begin() + static_cast<long>(imageBase + kRoutineRet + 1);
        for (auto it = begin; it != end;) {
            it = std::search(it, end, expected.begin(), expected.end());
            if (it == end) break;
            ++count;
            ++it;
        }
        return count;
    };

    requireBytes(kTemplate, "08 3a 3a 3a 3a 3a 3a 3a 3a",
                 "record empty-name template");
    requireBytes(kRoutineStart, "55 89 e5 b8 10 02 9a df 04 20 09",
                 "record entry prologue");
    requireBytes(kPromptSound,
                 "c7 06 74 20 78 00 c6 06 9f 79 0b e8 f5 fd",
                 "record prompt sound request");
    requireBytes(kBackspaceCheck, "80 3e 58 20 08",
                 "record backspace key check");
    requireBytes(kEnterCheck, "80 3e 58 20 0d 74 03 e9 3c ff",
                 "record enter key check");
    requireBytes(kCommitSound,
                 "c7 06 74 20 08 00 c6 06 9f 79 0b e8 08 fc",
                 "record commit sound request");
    requireBytes(kRecordShift,
                 "6b f8 0d 81 c7 f7 1a 1e 57 6b 3e 82 20 0d "
                 "81 c7 f7 1a 1e 57 6a 0d 9a 0e 09 20 09",
                 "record table shift copy");
    requireBytes(kStoredRecordPointer, "6b f8 0d 81 c7 f7 1a",
                 "record stored pointer stride");
    requireBytes(kNameCopy,
                 "8d 7e f0 16 57 c4 7e ec 81 c7 04 00 06 57 "
                 "6a 08 9a f4 09 20 09",
                 "record name copy");
    requireBytes(kScoreWrite,
                 "8b 46 08 8b 56 0a c4 7e ec 26 89 05 26 89 55 02",
                 "record score dword write");
    requireBytes(kRoutineRet - 3, "c9 c2 08 00", "record entry return");

    int strideImulCount = countBytes("6b f8 0d");
    int copy13Count = countBytes("6a 0d 9a 0e 09 20 09");
    int copy8Count = countBytes("6a 08 9a f4 09 20 09");
    if (strideImulCount != 3 || copy13Count != 1 || copy8Count != 2) {
        throw std::runtime_error("record entry stride/copy model changed");
    }

    std::cout << "record_entry_static_model=ok"
              << " routine=" << hex4(kRoutineStart) << ".." << hex4(kRoutineRet)
              << " template=" << hex4(kTemplate)
              << " template_len=8"
              << " template_byte=0x3a"
              << " record_stride=13"
              << " stride_imuls=" << strideImulCount
              << " shift_copy_bytes=13"
              << " shift_copies=" << copy13Count
              << " name_offset=4"
              << " name_copy_bytes=8"
              << " name_copies=" << copy8Count
              << " score_offset=0"
              << " score_bytes=4"
              << " backspace_key=0x08"
              << " enter_key=0x0d"
              << " prompt_sound=0x0078/p11"
              << " commit_sound=0x0008/p11\n";
}

void UiDiagnostics::debugEndFlowStaticModel() {
    std::vector<uint8_t> exeBytes = readFile("LEZAC.EXE");
    if (exeBytes.size() < 0x0770 || exeBytes[0] != 'M' || exeBytes[1] != 'Z') {
        throw std::runtime_error("LEZAC.EXE missing MZ header");
    }
    uint16_t headerParagraphs = le16(exeBytes, 0x08);
    size_t imageBase = static_cast<size_t>(headerParagraphs) * 16;
    if (imageBase != 0x0770) {
        throw std::runtime_error("LEZAC.EXE image base changed for end-flow scan");
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
    auto nearTarget = [&](uint16_t offset, const std::string& label) {
        size_t p = imageBase + offset;
        if (p + 3 > exeBytes.size() || exeBytes[p] != 0xe8) {
            throw std::runtime_error(label + " is not a near call");
        }
        int rel = static_cast<int>(le16(exeBytes, p + 1));
        if (rel >= 0x8000) rel -= 0x10000;
        return static_cast<uint16_t>(offset + 3 + rel);
    };

    requireBytes(0x1ae1, "09 67 61 6d 65 20 6f 76 65 72",
                 "game-over string");
    requireBytes(0x1aeb, "0d 65 63 63 65 6c 6c 65 6e 74 65 3e 3e 3e",
                 "completed-game title string");
    requireBytes(0x1af9,
                 "17 68 61 69 20 63 6f 6d 70 6c 65 74 61 74 6f "
                 "20 69 6c 20 67 69 6f 63 6f",
                 "completed-game body string");
    requireBytes(kEndFlowDispatcherStart,
                 "55 89 e5 b8 0c 03 9a df 04 20 09 81 ec 0c 03",
                 "end-flow dispatcher prologue");
    requireBytes(0x1b63,
                 "8a 46 04 3c 01 75 1e 6a 3c 6a 4d bf e1 1a",
                 "end-flow mode-1 branch");
    requireBytes(0x1b88,
                 "3c 02 75 3d 6a 3c 6a 37 bf eb 1a",
                 "end-flow mode-2 branch");
    requireBytes(0x1bc4, "c6 06 8c 20 01", "completed-game flag write");
    requireBytes(0x1bf8,
                 "c7 46 fc 01 00 eb 03 ff 46 fc 83 7e fc 01 75 13 "
                 "b8 5a 78 8c da a3 b6 78 89 16 b8 78 c6 06 58 "
                 "20 31 eb 11 b8 88 78 8c da a3 b6 78 89 16 b8 "
                 "78 c6 06 58 20 32",
                 "end-flow player score pointer setup");
    requireBytes(0x1c4b,
                 "83 bb f2 fe 00 7f 0f 7d 03 e9 98 00 83 bb f0 "
                 "fe 00 77 03 e9 8e 00",
                 "end-flow zero-score skip");
    requireBytes(0x1cf8, "9a 0f 03 4a 08 a2 58 20",
                 "end-flow key wait");
    requireBytes(0x1d00, "c7 46 fc 01 00 eb 03 ff 46 fc",
                 "end-flow record loop");
    requireBytes(0x1d18,
                 "3b 16 54 1b 7f 08 7c 1b 3b 06 52 1b 72 15",
                 "end-flow seventh-record cutoff compare");
    requireBytes(0x1d2c,
                 "ff b3 f2 fe ff b3 f0 fe ff 76 fc 55 e8 0a fb",
                 "end-flow record-entry call setup");
    requireBytes(0x1d3b, "83 7e fc 02 75 c6 c9 c2 02 00",
                 "end-flow record loop return");

    uint16_t recordEntryTarget = nearTarget(0x1d38, "end-flow record-entry call");
    if (recordEntryTarget != 0x1845) {
        throw std::runtime_error("end-flow record-entry target changed");
    }

    std::cout << "end_flow_static_model=ok"
              << " routine=" << hex4(kEndFlowDispatcherStart)
              << ".." << hex4(kEndFlowDispatcherRet)
              << " game_over_string=0x1ae1"
              << " completed_strings=0x1aeb,0x1af9"
              << " mode_param=bp+4"
              << " completed_flag=0x208c"
              << " player_score_ptrs=0x785a,0x7888"
              << " player_markers=0x31,0x32"
              << " key_latch=0x2058"
              << " record_cutoff=0x1b52/0x1b54"
              << " record_stride=13"
              << " record_entry_call=" << hex4(recordEntryTarget)
              << " strict_cutoff=1"
              << " player_order=1,2\n";
}
}
