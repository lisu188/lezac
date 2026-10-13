#include "resources/io.hpp"
#include "resources/records.hpp"

#include <array>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    using namespace lezac::resources;
    try {
        if (argc != 3) throw std::runtime_error("expected original fixture and output directory");
        const auto expected = readFile(argv[1]);
        if (expected.size() != 92 || expected.front() != 7 || expected[5] != 8)
            throw std::runtime_error("original record-save fixture shape changed");
        const std::filesystem::path output(argv[2]);
        std::filesystem::create_directories(output);
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
                reloaded.front().score != 100 || reloaded.front().encodedName != "a:::::::")
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
