#include "ui/ui_controller.hpp"
#include "resources/io.hpp"
#include <filesystem>
#include <iostream>
#include <stdexcept>

using namespace lezac;
namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

int64_t signedScore(uint32_t value) {
    return value < 0x80000000u ? int64_t(value) : int64_t(value) - 0x100000000LL;
}

void flow(const std::filesystem::path& fixture, const std::filesystem::path& out,
          bool mixed, const std::string& first, const std::string& second,
          int players, ui::EndReason reason) {
    using namespace ui;
    UiController controller;
    RecordStore records;
    records.replaceRecords(resources::loadRawRecords((fixture / (mixed ? "end_run_mixed-cutoff-fixture.dat" :
        "record_entry_negative-cutoff-fixture.dat")).string()));
    records.setPath((out / "records.dat").string());
    std::vector<std::string> events;
    UiActions actions;
    actions.resetAfterEndRun = [&] { events.push_back("end"); };
    actions.prepareNameEntryPage = [&] { events.push_back("background"); };
    actions.recordPromptSound = [&] { events.push_back("prompt"); };
    actions.recordCommitSound = [&] { events.push_back("commit"); };
    actions.clearScores = [&] { events.push_back("clear"); };
    actions.prepareNewGame = [&](int) { throw std::runtime_error("acknowledgement started a new game"); };
    actions.recordsPageSound = [&] { throw std::runtime_error("end flow entered the records browser"); };
    actions.prepareRecordsPage = actions.recordsPageSound;
    controller.beginEndRun(reason, 0, players, 0, 0, records, actions);
    require(controller.snapshot().page == UiController::endMenuPage(reason) && !records.hasPendingRecord() &&
            events == std::vector<std::string>{"end"}, "record prompt preceded Game Over acknowledgement");
    bool running = true;
    controller.onKey(Key::One, running, 0, players, records, actions);
    for (int player = 1; player <= 2; ++player) {
        require(running && controller.snapshot().page == MenuPage::NameEntry && records.hasPendingRecord() &&
                records.pending().score == 0 && records.pending().player == player && records.pending().level == 1,
                "zero-score or one-player second-slot entry was lost");
        const auto beforeEscape = events;
        controller.onKey(Key::Escape, running, 0, players, records, actions);
        require(records.hasPendingRecord() && records.pending().player == player && records.pending().name.empty() &&
                events == beforeEscape, "Escape cancelled the pending zero-score entry");
        for (char letter : (player == 1 ? first : second)) {
            const auto key = letter == ' ' ? Key::Space : static_cast<Key>(int(Key::A) + letter - 'a');
            controller.onKey(key, running, 0, players, records, actions);
        }
        controller.onKey(Key::Return, running, 0, players, records, actions);
        const auto expected = fixture / (mixed ? (player == 1 ? "end_run_after-player1-file.dat" : "end_run_saved-original.dat") :
            (player == 1 ? "record_entry_after-player1-file.dat" : "record_entry_saved-original.dat"));
        require(resources::readFile(records.path()) == resources::readFile(expected.string()),
                "actual UI/RecordStore saved bytes differ from the original");
    }
    require(running && controller.snapshot().page == MenuPage::Main && !records.hasPendingRecord(),
            "last record did not return directly to Main");
    require(events == std::vector<std::string>{"end", "background", "prompt", "commit",
            "background", "prompt", "commit", "clear"}, "original end-run callback order changed");
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 3, "expected fixture and new output directories");
        const std::filesystem::path fixture(argv[1]), out(argv[2]);
        require(!std::filesystem::exists(out), "output directory already exists");
        std::filesystem::create_directories(out);
        int flows = 0;
        for (int players : {1, 2}) for (auto reason : {ui::EndReason::GameOver, ui::EndReason::CompletedGame}) {
            for (bool mixed : {false, true}) {
                const auto path = out / std::to_string(flows++);
                std::filesystem::create_directories(path);
                flow(fixture, path, mixed, mixed ? "q" : "a c",
                     mixed ? "r" : "z", players, reason);
            }
        }
        ui::RecordStore records;
        const uint32_t values[]{0, 1, 0x7fffffffu, 0x80000000u, 0xffffffffu, 0xffff0000u, 0x00010000u};
        int signedCases = 0;
        for (uint32_t cutoff : values) {
            records.replaceRecords(std::vector<resources::Record>(7, resources::makeRecord(cutoff, 1, "cutoff")));
            for (uint32_t candidate : values) {
                require(records.scoreQualifies(candidate) == (signedScore(candidate) >= signedScore(cutoff)),
                        "signed cutoff or inclusive equality changed");
                ++signedCases;
            }
        }
        std::vector<resources::Record> unsorted;
        for (uint32_t score : {100u, 0xffffffffu, 200u, 0xfffffffeu, 0u, 0xfffffffdu, 0xfffffffcu})
            unsorted.push_back(resources::makeRecord(score, 1, "old"));
        require(ui::RecordStore::insertRecord(unsorted, resources::makeRecord(0, 1, "new")), "insertion failed");
        require(unsorted.size() == 7 && unsorted[0].score == 100 && unsorted[1].score == 0xffffffffu &&
                unsorted[2].score == 200 && unsorted[3].score == 0xfffffffeu &&
                unsorted[4].name == "old" && unsorted[5].name == "new" && unsorted[6].score == 0xfffffffdu,
                "insertion sorted the original prefix or moved an existing tie");
        auto fullTies = std::vector<resources::Record>(7, resources::makeRecord(0, 1, "old"));
        require(!ui::RecordStore::insertRecord(fullTies, resources::makeRecord(0, 1, "new")) &&
                fullTies.size() == 7 && fullTies.back().name == "old", "bounded rank-eight handling changed");
        records.replaceRecords(resources::loadRawRecords((fixture / "record_entry_negative-cutoff-fixture.dat").string()));
        records.beginEndRun(ui::EndReason::GameOver, 0, 1, 0, 0);
        require(records.startNextPendingRecord() && records.hasPendingRecord(), "zero pending entry missing");
        records.setPendingNameForFixture("retry");
        records.setPath((out / "missing" / "records.dat").string());
        require(records.finalizePendingRecord() == ui::RecordStore::CommitResult::SaveFailed &&
                records.hasPendingRecord() && records.pending().score == 0 && records.pending().name == "retry",
                "save failure discarded zero-score pending ownership");
        records.setPath((out / "retry.dat").string());
        require(records.finalizePendingRecord() == ui::RecordStore::CommitResult::Saved && !records.hasPendingRecord(),
                "zero-score retry did not commit");
        require(records.finalizePendingRecord() == ui::RecordStore::CommitResult::NoPending,
                "cleared ownership committed a second time");
        records.replaceRecords({});
        for (uint32_t score : {700u, 600u, 500u, 400u, 300u, 200u, 100u}) {
            auto table = records.records();
            table.push_back(resources::makeRecord(score, 1, "old"));
            records.replaceRecords(std::move(table));
        }
        records.beginEndRun(ui::EndReason::GameOver, 0, 1, 800, 150);
        require(records.startNextPendingRecord() && records.pending().player == 1, "first qualifier missing");
        require(records.finalizePendingRecord() == ui::RecordStore::CommitResult::Saved &&
                !records.startNextPendingRecord(), "second score was not checked against the updated cutoff");
        std::cout << "original_end_run=ok flows=" << flows << " compared_saved_bytes=1472 signed_cases=" << signedCases
                  << " acknowledgement=1 zero_pending=1 both_slots=1 stable_ties=1 prefix_preserved=1"
                     " final_main=1 retry=1 p2_recheck=1 rank8_memory_claim=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
