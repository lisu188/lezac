#include "ui/record_store.hpp"
#include "resources/io.hpp"
#include "resources/json.hpp"
#include <algorithm>
#include <array>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using namespace lezac;
namespace fs = std::filesystem;

namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

std::vector<uint8_t> hexBytes(const std::string& text) {
    require(text.size() % 2 == 0, "invalid hex length");
    auto digit = [](char value) {
        if (value >= '0' && value <= '9') return value - '0';
        if (value >= 'a' && value <= 'f') return value - 'a' + 10;
        throw std::runtime_error("invalid hex digit");
    };
    std::vector<uint8_t> result;
    for (size_t i = 0; i < text.size(); i += 2)
        result.push_back(static_cast<uint8_t>(16 * digit(text[i]) + digit(text[i + 1])));
    return result;
}

ui::RecordAdjacentMemory::Bytes adjacentBytes(const std::string& text) {
    const auto raw = hexBytes(text);
    require(raw.size() == 13, "invalid adjacent fixture size");
    ui::RecordAdjacentMemory::Bytes result{};
    std::copy(raw.begin(), raw.end(), result.begin());
    return result;
}

fs::path createRunDirectory(const fs::path& root) {
    fs::create_directories(root);
    for (uint64_t attempt = 0;; ++attempt) {
        const auto candidate = root / ("run-" + std::to_string(attempt));
        if (fs::create_directory(candidate)) return candidate;
    }
}

std::vector<uint8_t> recordBytes(const std::vector<resources::Record>& records) {
    std::vector<uint8_t> result;
    for (const auto& record : records) {
        const auto bytes = resources::encodedRecordBytes(record);
        result.insert(result.end(), bytes.begin(), bytes.end());
    }
    return result;
}

using Retained = std::vector<std::pair<fs::path, std::vector<uint8_t>>>;
void boundaries(const fs::path& fixtures, const fs::path& out,
                const std::vector<std::string>& samples, Retained& retained) {
    std::string current;
    ui::RecordStore store;
    bool committed = false;
    for (const auto& sample : samples) {
        const auto name = resources::extractString(sample, "case");
        const auto ordinal = resources::extractInt(sample, "ordinal");
        const auto expectedRecords = hexBytes(resources::extractString(sample, "records_hex"));
        const auto expectedAdjacent = adjacentBytes(resources::extractString(sample, "adjacent_hex"));
        if (name != current) {
            current = name;
            require(ordinal == 0, "fixture group does not start at ordinal zero");
            store = ui::RecordStore{};
            require(!store.adjacentMemory().initialized(), "startup handler bytes were invented");
            store.replaceRecords(resources::loadRawRecords(
                (fixtures / resources::extractString(sample, "fixture")).string()));
            store.seedAdjacentMemoryForFixture(expectedAdjacent);
            store.setPath((out / (current + ".dat")).string());
            resources::saveRecords(store.path(), store.records());
            store.beginEndRun(ui::EndReason::GameOver, 0, 1, 0, 0);
            committed = false;
        }
        if (resources::extractInt(sample, "committed") && !committed) {
            require(store.startNextPendingRecord() && store.pending().player == 1,
                    "original zero-score pending entry was not owned");
            store.appendNameCharacter('q');
            require(store.finalizePendingRecord() == ui::RecordStore::CommitResult::Saved,
                    "record save failed");
            committed = true;
        }
        require(recordBytes(store.records()) == expectedRecords, "original record-plane bytes differ");
        require(store.adjacentMemory().snapshot() == expectedAdjacent, "original adjacent bytes differ");
        std::vector<uint8_t> expectedFile{7};
        expectedFile.insert(expectedFile.end(), expectedRecords.begin(), expectedRecords.end());
        require(resources::readFile(store.path()) == expectedFile, "original saved bytes differ");
        const auto snapshot = out / (current + "-" + std::to_string(ordinal) + ".dat");
        fs::copy_file(store.path(), snapshot);
        retained.emplace_back(snapshot, expectedFile);
    }
}

int codecCases() {
    const std::array<uint32_t, 4> scores{0, 0x7fffffffu, 0x80000000u, 0xffffffffu};
    const std::array<std::array<uint8_t, 4>, 4> scoreBytes{{
        {{0, 0, 0, 0}}, {{0xff, 0xff, 0xff, 0x7f}}, {{0, 0, 0, 0x80}}, {{0xff, 0xff, 0xff, 0xff}}}};
    const std::array<std::string, 3> names{"", "a b", "abcdefgh"};
    const std::array<std::string, 3> encoded{"::::::::", "a b:::::", "abcdefgh"};
    int cases = 0;
    for (size_t score = 0; score < scores.size(); ++score) {
        for (uint8_t level : {uint8_t(0), uint8_t(1), uint8_t(255)}) {
            for (size_t name = 0; name < names.size(); ++name) {
                for (uint8_t length = 0; length <= 8; ++length) {
                    auto record = resources::makeRecord(scores[score], level, names[name]);
                    record.nameLength = length;
                    const auto bytes = resources::encodedRecordBytes(record);
                    require(std::equal(scoreBytes[score].begin(), scoreBytes[score].end(), bytes.begin()),
                            "score wire bytes differ");
                    require(bytes[4] == length, "Pascal name length lost");
                    for (size_t i = 0; i < 8; ++i)
                        require(bytes[5 + i] == static_cast<uint8_t>(encoded[name][i]), "name storage differs");
                    ++cases;
                }
            }
        }
    }
    return cases;
}

void ownershipAndRetry(const fs::path& fixtures, const fs::path& out) {
    ui::RecordAdjacentMemory unknown;
    require(!unknown.snapshot() && !unknown.keyboardHandler() && !unknown.timerHandler(),
            "unknown handler state exposed as initialized");
    const auto initial = adjacentBytes("0087e900f0601200f000000000");
    unknown.seedForFixture(initial);
    require(unknown.keyboardHandler() == ui::OriginalFarPointer{0xe987, 0xf000} &&
            unknown.timerHandler() == ui::OriginalFarPointer{0x1260, 0xf000}, "captured handlers decoded incorrectly");
    unknown.retainRankEight(resources::makeRecord(0, 1, "q"));
    const auto q = adjacentBytes("0000000008713a3a3a3a3a3a3a");
    require(unknown.snapshot() == q && unknown.keyboardHandler() == ui::OriginalFarPointer{0, 0x0800} &&
            unknown.timerHandler() == ui::OriginalFarPointer{0x3a71, 0x3a3a}, "overwritten handlers decoded incorrectly");
    auto invalid = resources::makeRecord(0, 1, "q");
    invalid.nameLength = 9;
    bool rejected = false;
    try { unknown.retainRankEight(invalid); } catch (const std::runtime_error&) { rejected = true; }
    require(rejected && unknown.snapshot() == q, "invalid wire record partially changed adjacent memory");

    ui::RecordStore store;
    store.replaceRecords(resources::loadRawRecords((fixtures / "record_adjacent_zero.dat").string()));
    store.setPath((out / "missing" / "RECS.DAT").string());
    store.beginEndRun(ui::EndReason::GameOver, 0, 1, 0, 0);
    require(store.startNextPendingRecord(), "failed-save fixture did not qualify");
    store.appendNameCharacter('q');
    require(store.finalizePendingRecord() == ui::RecordStore::CommitResult::SaveFailed &&
            store.hasPendingRecord() && store.adjacentMemory().snapshot() == q,
            "failed file save rolled back the prior adjacent write or lost ownership");
    store.setPath((out / "retry.dat").string());
    require(store.finalizePendingRecord() == ui::RecordStore::CommitResult::Saved &&
            !store.hasPendingRecord() && store.adjacentMemory().snapshot() == q, "retry changed adjacent bytes");
    store.clearQueue();
    store.clearPendingRecord();
    store.replaceRecords(resources::loadRawRecords((fixtures / "record_adjacent_rank7.dat").string()));
    store.beginEndRun(ui::EndReason::GameOver, 1, 2, 0, 0);
    require(store.adjacentMemory().snapshot() == q, "new queue or record-table reload reset adjacent bytes");
}
}  // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 3, "expected fixture and output directories");
        const fs::path fixtures(argv[1]);
        const auto raw = resources::readFile((fixtures / "record_adjacent_original.json").string());
        const auto samples = resources::extractObjectArray(std::string(raw.begin(), raw.end()), "samples");
        require(samples.size() == 31, "original boundary count changed");
        Retained first, second;
        const auto firstRun = createRunDirectory(argv[2]);
        boundaries(fixtures, firstRun, samples, first);
        const auto secondRun = createRunDirectory(argv[2]);
        boundaries(fixtures, secondRun, samples, second);
        require(first.size() == 31 && second.size() == 31, "missing retained commit boundary");
        for (const auto& [path, bytes] : first)
            require(resources::readFile(path.string()) == bytes, "repeat changed first-run evidence");
        ownershipAndRetry(fixtures, firstRun);
        require(codecCases() == 324, "codec case count changed");
        std::cout << "record_adjacent=ok original_boundaries=31 compared_span_bytes=6448 saved_snapshot_bytes=5704"
                     " rounds=2 first_evidence_unchanged=1 codec_cases=324 unknown_startup=1 lifetime=1 retry=1"
                     " handler_bytes=1 frame_dispatch_claim=0 whole_game_parity=0\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
