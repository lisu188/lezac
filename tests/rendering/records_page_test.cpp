#include "rendering/game_renderer.hpp"
#include "resources/io.hpp"
#include "ui/level_flow.hpp"
#include "ui/ui_controller.hpp"
#include <cstddef>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <type_traits>

using namespace lezac;

namespace {
struct PreviousRecordLayout {
    uint32_t score;
    uint8_t level;
    std::string name;
    std::string encodedName;
};
static_assert(std::is_standard_layout_v<resources::Record>);
static_assert(sizeof(resources::Record) == sizeof(PreviousRecordLayout));
static_assert(alignof(resources::Record) == alignof(PreviousRecordLayout));
static_assert(offsetof(resources::Record, score) == offsetof(PreviousRecordLayout, score));
static_assert(offsetof(resources::Record, level) == offsetof(PreviousRecordLayout, level));
static_assert(offsetof(resources::Record, name) == offsetof(PreviousRecordLayout, name));
static_assert(offsetof(resources::Record, encodedName) == offsetof(PreviousRecordLayout, encodedName));

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
template<class Fn> void rejects(Fn function) {
    bool rejected = false;
    try { function(); } catch (const std::runtime_error&) { rejected = true; }
    require(rejected, "malformed name length accepted");
}

void checkInput() {
    using namespace ui;
    std::vector<Key> keys{Key::Unknown, Key::Backspace, Key::Return, Key::Escape, Key::Space,
        Key::One, Key::Two, Key::KeypadEnter, Key::F5, Key::PageUp, Key::PageDown,
        Key::RightControl, Key::Keypad0, Key::Insert};
    for (int key = static_cast<int>(Key::A); key <= static_cast<int>(Key::Z); ++key)
        keys.push_back(static_cast<Key>(key));
    require(keys.size() == 40, "input fixture count changed");
    for (Key key : keys) {
        UiController controller;
        RecordStore records;
        bool running = true;
        int entries = 0, sounds = 0, draws = 0;
        UiActions actions;
        actions.recordsPageSound = [&] {
            require(controller.snapshot().page == MenuPage::Records && entries == 0,
                    "records sound callback order changed");
            ++sounds;
        };
        actions.prepareRecordsPage = [&] {
            ++entries;
            require(controller.snapshot().page == MenuPage::Records, "background prepared before entry");
            LevelFlow::makeLevelIntroPattern([&](int low, int) { ++draws; return low; });
        };
        actions.prepareNewGame = [](int) { throw std::runtime_error("records key started a game"); };
        actions.beginLevel = [](int) { throw std::runtime_error("records key loaded a level"); };
        actions.clearScores = [] { throw std::runtime_error("records key cleared scores"); };
        controller.beginMainMenu(0);
        controller.onKey(Key::R, running, 3, 2, records, actions, 100000);
        require(controller.snapshot().page == MenuPage::Records && entries == 1 && sounds == 1 && draws == 8,
                "records entry did not prepare exactly one background");
        controller.onKey(key, running, 3, 2, records, actions, 100001);
        require(running && controller.snapshot().menu && controller.snapshot().page == MenuPage::Main &&
                controller.snapshot().mainMenu.startedAt == 100001 && controller.snapshot().italian &&
                entries == 1 && sounds == 1 && draws == 8, "records acknowledgement dispatched a menu command");
    }
    UiController controller;
    RecordStore records;
    UiActions actions;
    int prepared = 0;
    actions.prepareRecordsPage = [&] { ++prepared; };
    actions.clearScores = [] {};
    controller.finalizePendingRecord(records, actions);
    controller.cancelPendingRecord(records, actions);
    require(prepared == 2 && controller.snapshot().page == MenuPage::Records,
            "record completion/cancellation missed background preparation");
}

void writePpm(const std::filesystem::path& path, const std::vector<uint32_t>& pixels) {
    std::ofstream output(path, std::ios::binary);
    output << "P6\n320 200\n255\n";
    for (uint32_t color : pixels) {
        const char rgb[]{static_cast<char>(color >> 16), static_cast<char>(color >> 8), static_cast<char>(color)};
        output.write(rgb, 3);
    }
    require(bool(output), "PPM write failed");
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 3, "expected fixture and output directories");
        checkInput();
        const std::filesystem::path fixture(argv[1]), out(argv[2]);
        require(!std::filesystem::exists(out), "output directory already exists");
        std::filesystem::create_directories(out);
        const auto assets = resources::AssetCatalog::load(resources::AssetFormat::Original);
        rendering::PresentationState presentation;
        presentation.setPalette(assets.backgroundPalette());
        rendering::Canvas canvas;
        rendering::TextRenderer text(canvas, presentation.palette(), assets.fontSprites());
        rendering::GameRenderer renderer(canvas, text, assets, presentation);
        const std::array<ui::LevelIntroPattern, 2> patterns{{
            {79, 50, {{{77, 12, 56}, {85, 16, 69}, {97, 20, 81}, {109, 24, 93},
                       {121, 28, 105}, {134, 32, 117}, {146, 36, 130}}}},
            {74, 24, {{{20, 52, 32}, {24, 60, 32}, {32, 69, 32}, {40, 81, 32},
                       {44, 89, 32}, {52, 101, 32}, {60, 109, 32}}}}}};
        const std::array<std::string, 2> kinds{{"shipped", "short"}};
        const std::array<uint8_t, 7> shortLengths{{8, 1, 0, 2, 3, 4, 7}};
        const std::array<std::string, 7> shortNames{{"abcdefgh", "a", "nessuno", "ab", "abc", "abcd", "abcdefg"}};
        const std::string pendingName;
        for (size_t index = 0; index < kinds.size(); ++index) {
            const std::string stem = "records_page_" + kinds[index];
            const auto raw = resources::readFile((fixture / (stem + ".dat")).string());
            auto records = resources::parseRawRecords(raw, stem);
            require(records.size() == 7, "record count mismatch");
            for (size_t i = 0; i < records.size(); ++i) {
                require(records[i].level == 0 && records[i].encodedName.size() == 8 &&
                    records[i].nameLength == (index == 0 ? 8 : shortLengths[i]) &&
                    records[i].name == (index == 0 ? "aga" : shortNames[i]), "Pascal name decode mismatch");
            }
            resources::saveRecords((out / (stem + ".dat")).string(), records);
            require(resources::readFile((out / (stem + ".dat")).string()) == raw, "raw tail/length changed");
            records[0].level = 255;
            resources::saveRecords((out / (stem + ".json")).string(), records);
            const auto jsonRecords = resources::loadRecords((out / (stem + ".json")).string());
            require(jsonRecords[0].level == 255, "port-only JSON level lost");
            resources::saveRecords((out / (stem + "-json.dat")).string(), jsonRecords);
            require(resources::readFile((out / (stem + "-json.dat")).string()) == raw, "JSON roundtrip changed wire data");
            const auto expected = resources::readFile((fixture / (stem + ".rgb")).string());
            require(expected.size() == 192000, "RGB oracle size mismatch");
            for (bool italian : {false, true}) {
                const rendering::MenuView menu{ui::MenuPage::Records, italian, records, 0, 0, 0,
                    pendingName, 1, {{0, 0}}, 63, static_cast<size_t>(-1), patterns[index]};
                renderer.drawMenu(menu);
                writePpm(out / (stem + (italian ? "-italian.ppm" : "-english.ppm")), canvas.pixels());
                size_t differences = 0;
                for (size_t pixel = 0; pixel < canvas.pixels().size(); ++pixel) {
                    const uint32_t reference = 0xff000000u | (uint32_t(expected[pixel * 3]) << 16) |
                        (uint32_t(expected[pixel * 3 + 1]) << 8) | expected[pixel * 3 + 2];
                    if (canvas.pixels()[pixel] != reference) ++differences;
                }
                if (differences) throw std::runtime_error(kinds[index] + " differing pixels=" + std::to_string(differences));
                const auto previous = canvas.pixels();
                renderer.drawMenu(menu);
                require(previous == canvas.pixels(), "redraw changed frozen records background");
            }
            auto malformed = raw;
            malformed[5] = 9;
            rejects([&] { resources::parseRawRecords(malformed, "invalid"); });
            records[0].nameLength = 9;
            rejects([&] { resources::saveRecords((out / (stem + ".dat")).string(), records); });
            require(resources::readFile((out / (stem + ".dat")).string()) == raw, "invalid save truncated existing file");
        }
        rejects([] { resources::parseJsonRecords(R"({"records":[{"name_length":-1}]})"); });
        rejects([] { resources::parseJsonRecords(R"({"records":[{"name_length":9}]})"); });
        const auto legacy = resources::parseJsonRecords(R"({"records":[{"level":9,"decoded_name":"a"}]})");
        require(legacy[0].level == 9 && legacy[0].nameLength == 8, "legacy JSON compatibility changed");
        std::cout << "records_page=ok original_frames=2 compared_pixels=256000 differing_pixels=0 masks=0"
                     " raw_roundtrips=2 input_cases=40 layout_preserved=1 timing_parity=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "records_page failed: " << error.what() << '\n';
        return 1;
    }
}
