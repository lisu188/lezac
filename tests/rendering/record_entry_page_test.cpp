#include "rendering/game_renderer.hpp"
#include "resources/io.hpp"
#include "ui/level_flow.hpp"
#include "ui/ui_controller.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>

using namespace lezac;

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

void writePpm(const std::filesystem::path& path, const std::vector<uint32_t>& pixels) {
    std::ofstream file(path, std::ios::binary);
    file << "P6\n320 200\n255\n";
    for (uint32_t color : pixels) {
        const char rgb[]{static_cast<char>(color >> 16), static_cast<char>(color >> 8), static_cast<char>(color)};
        file.write(rgb, 3);
    }
    require(bool(file), "PPM write failed");
}

void checkEditing(const std::filesystem::path& out) {
    using namespace ui;
    UiController controller;
    RecordStore records;
    records.setPath((out / "editing.dat").string());
    bool running = true;
    int prepared = 0, randomDraws = 0, prompts = 0, commits = 0;
    UiActions actions;
    actions.resetAfterEndRun = [] {};
    actions.clearScores = [] {};
    actions.prepareNameEntryPage = [&] {
        require(controller.snapshot().page == MenuPage::NameEntry && prompts == 0,
                "name background must precede prompt sound");
        ++prepared;
        LevelFlow::makeLevelIntroPattern([&](int low, int) { ++randomDraws; return low; });
    };
    actions.recordPromptSound = [&] { ++prompts; };
    actions.recordCommitSound = [&] { ++commits; };
    controller.beginEndRun(EndReason::GameOver, 0, 1, 100, 0, records, actions);
    require(prepared == 1 && randomDraws == 8 && prompts == 1, "name entry background draw count changed");
    for (Key key : {Key::Escape, Key::Unknown, Key::One, Key::Two, Key::F5, Key::RightControl,
                    Key::Keypad0, Key::Insert, Key::PageUp, Key::PageDown, Key::Backspace}) {
        controller.onKey(key, running, 0, 1, records, actions);
        require(running && controller.snapshot().page == MenuPage::NameEntry && records.pending().name.empty(),
                "nonletter input changed empty name entry");
    }
    for (Key key : {Key::A, Key::Space, Key::B, Key::Backspace, Key::C, Key::Escape})
        controller.onKey(key, running, 0, 1, records, actions);
    require(records.pending().name == "a c", "letter/space/backspace/Escape behavior changed");
    for (int i = 0; i < 10; ++i) controller.onKey(Key::Z, running, 0, 1, records, actions);
    require(records.pending().name == "a czzzzz", "name cap changed");
    for (int i = 0; i < 5; ++i) controller.onKey(Key::Backspace, running, 0, 1, records, actions);
    require(records.pending().name == "a c", "backspace failed to restore entered space");
    require(prepared == 1 && randomDraws == 8 && prompts == 1 && commits == 0,
            "editing regenerated the name background or requested commit");
    controller.onKey(Key::KeypadEnter, running, 0, 1, records, actions);
    const auto saved = resources::loadRawRecords((out / "editing.dat").string());
    require(commits == 1 && saved.size() == 1 && saved[0].encodedName == "a c:::::",
            "Return did not commit literal space and colon padding");
}

void checkObservedSaveBytes(const std::filesystem::path& fixture, const std::filesystem::path& out) {
    auto records = resources::loadRawRecords((fixture / "record_entry_negative-cutoff-fixture.dat").string());
    // Codec-only reconstruction of the observed tables, not an end-run queue replay.
    records.pop_back();
    records.insert(records.begin(), resources::makeRecord(0, 1, "a c"));
    resources::saveRecords((out / "player1.dat").string(), records);
    require(resources::readFile((out / "player1.dat").string()) ==
            resources::readFile((fixture / "record_entry_after-player1-file.dat").string()),
            "player-one saved bytes differ from original");
    records.pop_back();
    records.insert(records.begin() + 1, resources::makeRecord(0, 1, "z"));
    resources::saveRecords((out / "player2.dat").string(), records);
    require(resources::readFile((out / "player2.dat").string()) ==
            resources::readFile((fixture / "record_entry_saved-original.dat").string()),
            "player-two saved bytes differ from original");
    for (const std::string entered : {std::string(" "), std::string("a "), std::string(" a  b ")}) {
        const auto record = resources::makeRecord(0, 255, entered);
        require(record.encodedName == entered + std::string(8 - entered.size(), ':'), "space byte was normalized");
        resources::saveRecords((out / "spaces.json").string(), {record});
        require(resources::loadRecords((out / "spaces.json").string())[0].encodedName == record.encodedName,
                "JSON round trip lost entered space bytes");
    }
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 3, "expected fixture and output directories");
        const std::filesystem::path fixture(argv[1]), out(argv[2]);
        require(!std::filesystem::exists(out), "output directory already exists");
        std::filesystem::create_directories(out);
        checkEditing(out);
        checkObservedSaveBytes(fixture, out);
        const auto assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
        rendering::PresentationState presentation;
        presentation.setPalette(assets.palette());
        rendering::Canvas canvas;
        rendering::TextRenderer text(canvas, presentation.palette(), assets.fontSprites());
        rendering::GameRenderer renderer(canvas, text, assets, presentation);
        const std::array<ui::LevelIntroPattern, 2> patterns{{
            {80, 32, {{{52, 48, 20}, {52, 48, 36}, {52, 48, 52}, {52, 52, 69},
                       {52, 52, 85}, {52, 56, 101}, {52, 56, 117}}}},
            {77, 23, {{{48, 69, 0}, {52, 73, 8}, {60, 81, 16}, {69, 89, 24},
                       {73, 93, 36}, {81, 101, 44}, {89, 109, 52}}}}}};
        struct State { const char* file; uint8_t player; const char* name; };
        const std::array<State, 8> states{{
            {"player1-empty", 1, ""}, {"player1-a", 1, "a"}, {"player1-a-space", 1, "a "},
            {"player1-a-space-b", 1, "a b"}, {"player1-after-backspace", 1, "a "},
            {"player1-a-space-c", 1, "a c"}, {"after-player1-commit", 2, ""}, {"player2-z", 2, "z"}}};
        size_t compared = 0;
        for (const State& state : states) {
            const std::string stem = std::string("record_entry_") + state.file;
            const auto records = resources::loadRawRecords((fixture / (state.player == 1 ?
                "record_entry_negative-cutoff-fixture.dat" : "record_entry_after-player1-file.dat")).string());
            const std::string name(state.name);
            const auto expected = resources::readFile((fixture / (stem + ".rgb")).string());
            require(expected.size() == 192000, "RGB oracle size mismatch");
            for (bool italian : {false, true}) {
                const rendering::MenuView menu{ui::MenuPage::NameEntry, italian, records, state.player,
                    0, 1, name, 1, {{0, 0}}, 63, static_cast<size_t>(-1), patterns[state.player - 1]};
                renderer.drawMenu(menu);
                writePpm(out / (stem + (italian ? "-italian.ppm" : "-english.ppm")), canvas.pixels());
                size_t differences = 0;
                for (size_t pixel = 0; pixel < canvas.pixels().size(); ++pixel) {
                    const uint32_t reference = 0xff000000u | (uint32_t(expected[pixel * 3]) << 16) |
                        (uint32_t(expected[pixel * 3 + 1]) << 8) | expected[pixel * 3 + 2];
                    if (canvas.pixels()[pixel] != reference) ++differences;
                }
                compared += canvas.pixels().size();
                if (differences) throw std::runtime_error(stem + " differing_pixels=" + std::to_string(differences));
                const auto previous = canvas.pixels();
                renderer.drawMenu(menu);
                require(previous == canvas.pixels(), "name redraw changed frozen background");
            }
        }
        std::cout << "record_entry_page=ok original_frames=8 compared_pixels=" << compared
                  << " differing_pixels=0 masks=0 literal_space=1 saved_bytes=184 escape_ignored=1"
                     " background_rng_calls=8 timing_parity=0 end_flow_parity=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "record_entry_page failed: " << error.what() << '\n';
        return 1;
    }
}
