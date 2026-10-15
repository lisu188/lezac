#include "resources/io.hpp"
#include "resources/records.hpp"

#include <array>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
std::filesystem::path createRunDirectory(const std::filesystem::path& root) {
    std::filesystem::create_directories(root);
    for (std::uint64_t attempt = 0;; ++attempt) {
        const auto candidate = root / ("run-" + std::to_string(attempt));
        if (std::filesystem::create_directory(candidate)) return candidate;
    }
}

void checkExistingFieldLayout() {
    struct LegacyRecord {
        uint32_t score = 0;
        uint8_t level = 0;
        std::string name;
        std::string encodedName;
    };
    const LegacyRecord legacy;
    const lezac::resources::Record current;
    const auto offsets = [](const auto& record) {
        const auto* base = reinterpret_cast<const char*>(&record);
        return std::array<std::ptrdiff_t, 4>{{
            reinterpret_cast<const char*>(&record.score) - base,
            reinterpret_cast<const char*>(&record.level) - base,
            reinterpret_cast<const char*>(&record.name) - base,
            reinterpret_cast<const char*>(&record.encodedName) - base}};
    };
    if (sizeof(legacy) != sizeof(current) || alignof(LegacyRecord) != alignof(decltype(current)) ||
        offsets(legacy) != offsets(current))
        throw std::runtime_error("record field layout changed on this toolchain");
}
}

int main(int argc, char** argv) {
    using namespace lezac::resources;
    try {
        if (argc != 3) throw std::runtime_error("expected original fixture and output directory");
        const auto expected = readFile(argv[1]);
        if (expected.size() != 92 || expected.front() != 7 || expected[5] != 8)
            throw std::runtime_error("original record-save fixture shape changed");
        checkExistingFieldLayout();
        const auto output = createRunDirectory(argv[2]);
        for (const uint8_t level : std::array<uint8_t, 5>{{1, 0, 7, 8, 255}}) {
            std::vector<Record> records{makeRecord(100, level, "a")};
            for (size_t i = 0; i < 6; ++i) records.push_back(makeRecord(0, 8, "zero"));
            const std::string stem = "record-level-" + std::to_string(level);
            const auto binary = (output / (stem + ".dat")).string();
            saveRecords(binary, records);
            const auto actual = readFile(binary);
            if (actual != expected) {
                size_t differences = actual.size() > expected.size() ? actual.size() - expected.size() :
                                     expected.size() - actual.size();
                for (size_t i = 0; i < actual.size() && i < expected.size(); ++i)
                    differences += actual[i] != expected[i];
                throw std::runtime_error("original record-save bytes differ: level=" +
                                         std::to_string(level) + " differences=" + std::to_string(differences));
            }
            const auto json = (output / (stem + ".json")).string();
            saveRecords(json, records);
            const auto reloaded = loadRecords(json);
            if (reloaded.size() != 7 || reloaded.front().level != level ||
                reloaded.front().score != 100 || reloaded.front().encodedName != "a:::::::" ||
                reloaded.front().nameLength != 8)
                throw std::runtime_error("JSON level metadata or record contents changed");
        }
        std::cout << "record_save_original=ok cases=5 compared_bytes=460 differences=0"
                     " original_level=1 original_name_length=8 json_level_metadata_preserved=1"
                     " whole_game_parity=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
