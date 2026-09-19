#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace lezac::resources {

struct Record {
    uint32_t score = 0;
    uint8_t level = 0;
    std::string name;
    std::string encodedName;
};

std::vector<Record> parseJsonRecords(const std::string& json);
std::string decodeRawRecordName(std::string encoded);
std::vector<Record> parseRawRecords(const std::vector<uint8_t>& data, const std::string& path);
std::vector<Record> loadRawRecords(const std::string& path);
std::vector<Record> loadRecords(const std::string& path);
std::string encodeRecordName(const std::string& name);
std::string encodedRecordName(const Record& record);
Record makeRecord(uint32_t score, uint8_t level, const std::string& enteredName);
bool isJsonRecordPath(const std::string& path);
void saveRecords(const std::string& path, const std::vector<Record>& records);

}
