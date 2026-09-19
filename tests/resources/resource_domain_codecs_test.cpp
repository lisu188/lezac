#include "resources/gran.hpp"
#include "resources/levels.hpp"
#include "resources/records.hpp"
#include "resources/sound.hpp"

#include <cstdio>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace lezac::resources;

namespace {
struct TestFile {
    std::string path;
    ~TestFile() { std::remove(path.c_str()); }
    void bytes(const std::vector<uint8_t>& data) const {
        std::ofstream out(path, std::ios::binary);
        out.write(reinterpret_cast<const char*>(data.data()), static_cast<std::streamsize>(data.size()));
    }
    void text(const std::string& data) const { std::ofstream(path) << data; }
};
void require(bool condition) {
    if (!condition) throw std::runtime_error("domain resource codec mismatch");
}
template <typename Fn> void rejects(Fn fn) {
    bool rejected = false;
    try { fn(); } catch (const std::runtime_error&) { rejected = true; }
    require(rejected);
}
}

int main() {
    TestFile binary{"resource_domain_codecs_test.bin"};
    TestFile json{"resource_domain_codecs_test.json"};
    const Record record = makeRecord(0x12345678, 7, "A B");
    require(record.name == "A B" && record.encodedName == "A:B:::::");
    saveRecords(binary.path, {record});
    auto rawRecords = loadRawRecords(binary.path);
    require(rawRecords.size() == 1 && rawRecords[0].score == 0x12345678 &&
            rawRecords[0].level == 7 && rawRecords[0].encodedName == record.encodedName);
    saveRecords(json.path, rawRecords);
    const auto jsonRecords = loadRecords(json.path);
    require(jsonRecords.size() == 1 && jsonRecords[0].name == record.name &&
            jsonRecords[0].encodedName == record.encodedName);
    rejects([&] { parseRawRecords({}, "empty"); });
    rejects([&] { parseRawRecords({1, 0}, "truncated"); });

    std::vector<uint8_t> sound(2 + 130 * kSoundStepSize);
    sound[0] = 130;
    binary.bytes(sound);
    const auto bank = loadRawSon(binary.path);
    require(bank.stepCount == 130 && bank.records.size() == 6 && bank.recordSize == 130);
    binary.bytes({0});
    rejects([&] { loadRawSon(binary.path); });
    binary.bytes({1, 0, 1});
    rejects([&] { loadRawSon(binary.path); });
    binary.bytes({1, 0, 0, 0, 0, 0, 0, 0});
    rejects([&] { loadRawSon(binary.path); });
    json.text(R"({"record_size":6,"record_count":1,"records":[{"bytes_hex":"01 02 03 04 05 06"}]})");
    require(loadSon(json.path).payload == std::vector<uint8_t>({1, 2, 3, 4, 5, 6}));
    json.text(R"({"record_size":6,"record_count":2,"records":[]})");
    rejects([&] { loadSon(json.path); });
    json.text(R"({"record_size":5,"records":[{"bytes_hex":"01 02 03 04 05"}]})");
    rejects([&] { loadSon(json.path); });

    binary.bytes(std::vector<uint8_t>(7 * kGranRecordSize, 0x2a));
    const auto gran = loadRawGran(binary.path);
    require(gran.records.size() == 7 && gran.records[6].bytes.size() == kGranRecordSize &&
            gran.records[6].bytes[56] == 0x2a);
    binary.bytes(std::vector<uint8_t>(7 * kGranRecordSize - 1));
    rejects([&] { loadRawGran(binary.path); });
    json.text(R"({"record_size":56,"records":[]})");
    rejects([&] { loadGran(json.path); });
    json.text(R"({"record_size":57,"records":[]})");
    rejects([&] { loadGran(json.path); });

    std::vector<uint8_t> level{1,0,1,0,1,1,0,0, 3,0,0,1,0, 3,0,0,0,0, 0,0,0,0, 0,0,0};
    binary.bytes(level);
    const auto rawLevels = loadRawLevels(binary.path);
    require(rawLevels.size() == 1 && rawLevels[0].tiles == std::vector<uint8_t>({1}) &&
            rawLevels[0].wordLayer == std::vector<uint16_t>({0}) &&
            rawLevels[0].startingObjectiveTiles == 1);
    level.pop_back();
    binary.bytes(level);
    rejects([&] { loadRawLevels(binary.path); });
    binary.bytes({0,0,1,0});
    rejects([&] { loadRawLevels(binary.path); });
    json.text(R"({"levels":[{"width":1,"height":1,"objectiveTile":1,"tiles_rows_hex":["01"],"word_rows_hex":["0000"]}]})");
    require(loadLevels(json.path).front().startingObjectiveTiles == 1);
    json.text(R"({"levels":[{"width":1,"height":1,"tiles_rows_hex":[],"word_rows_hex":["0000"]}]})");
    rejects([&] { loadLevels(json.path); });
    json.text(R"({"levels":[{"width":1,"height":1,"fieldB":1,"tiles_rows_hex":["01"],"word_rows_hex":["0000"]}]})");
    rejects([&] { loadLevels(json.path); });
    std::cout << "resource_domain_codecs=ok records=2 sound=2 gran=1 levels=2 malformed=14\n";
}
