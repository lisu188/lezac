#include "resources/records.hpp"

#include "resources/io.hpp"
#include "resources/json.hpp"
#include "resources/binary.hpp"

#include <algorithm>
#include <stdexcept>
#include <utility>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iomanip>

namespace lezac::resources {

std::vector<Record> parseJsonRecords(const std::string& json) {
    std::vector<Record> records;
    auto recordObjects = extractObjectArray(json, "records");
    for (const auto& recJson : recordObjects) {
        Record r;
        r.score = static_cast<uint32_t>(extractInt(recJson, "score"));
        r.level = static_cast<uint8_t>(extractInt(recJson, "level"));
        r.name = extractString(recJson, "decoded_name", "nessuno");
        r.encodedName = extractString(recJson, "encoded_name", "");
        records.push_back(r);
    }
    return records;
}

std::string decodeRawRecordName(std::string encoded) {
    std::replace(encoded.begin(), encoded.end(), ':', ' ');
    while (!encoded.empty() && encoded.back() == ' ') {
        encoded.pop_back();
    }
    return encoded.empty() ? std::string("nessuno") : encoded;
}

std::vector<Record> parseRawRecords(const std::vector<uint8_t>& data,
                                    const std::string& path) {
    constexpr size_t kRecordSize = 13;
    if (data.empty()) {
        throw std::runtime_error(path + " is empty");
    }
    uint8_t count = data[0];
    if (data.size() != 1 + static_cast<size_t>(count) * kRecordSize) {
        throw std::runtime_error(path + " raw record table size mismatch");
    }
    std::vector<Record> records;
    records.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        size_t off = 1 + i * kRecordSize;
        Record record;
        record.score = le32(data, off);
        record.level = data[off + 4];
        std::string encoded(data.begin() + static_cast<std::ptrdiff_t>(off + 5),
                            data.begin() + static_cast<std::ptrdiff_t>(off + 13));
        record.name = decodeRawRecordName(encoded);
        record.encodedName = encoded;
        records.push_back(std::move(record));
    }
    return records;
}

std::vector<Record> loadRawRecords(const std::string& path) {
    return parseRawRecords(readFile(path), path);
}

std::vector<Record> loadRecords(const std::string& path) {
    auto data = readFile(path);
    auto first = std::find_if(data.begin(), data.end(), [](uint8_t byte) {
        return !std::isspace(static_cast<unsigned char>(byte));
    });
    if (first != data.end() && *first == '{') {
        return parseJsonRecords(std::string(data.begin(), data.end()));
    }
    return parseRawRecords(data, path);
}

std::string encodeRecordName(const std::string& name) {
    std::string out = name;
    out.resize(8, ':');
    for (char& ch : out) {
        if (ch == ' ') ch = ':';
    }
    return out;
}

std::string encodedRecordName(const Record& record) {
    if (record.encodedName.size() == 8) {
        return record.encodedName;
    }
    return encodeRecordName(record.name);
}

Record makeRecord(uint32_t score, uint8_t level, const std::string& enteredName) {
    Record record;
    record.score = score;
    record.level = level;
    record.encodedName = encodeRecordName(enteredName);
    record.name = decodeRawRecordName(record.encodedName);
    return record;
}

bool isJsonRecordPath(const std::string& path) {
    std::string ext = std::filesystem::path(path).extension().string();
    std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return ext == ".json";
}

void saveRecords(const std::string& path, const std::vector<Record>& records) {
    if (!isJsonRecordPath(path)) {
        std::ofstream out(path, std::ios::binary);
        if (!out) {
            throw std::runtime_error("cannot create " + path);
        }
        size_t count = std::min<size_t>(records.size(), 255);
        out.put(static_cast<char>(count));
        for (size_t i = 0; i < count; ++i) {
            uint32_t score = records[i].score;
            out.put(static_cast<char>(score & 0xffu));
            out.put(static_cast<char>((score >> 8) & 0xffu));
            out.put(static_cast<char>((score >> 16) & 0xffu));
            out.put(static_cast<char>((score >> 24) & 0xffu));
            out.put(static_cast<char>(records[i].level));
            std::string name = encodedRecordName(records[i]);
            out.write(name.data(), static_cast<std::streamsize>(name.size()));
        }
        return;
    }

    std::ofstream out(path);
    if (!out) {
        throw std::runtime_error("cannot create " + path);
    }
    size_t count = std::min<size_t>(records.size(), 255);
    out << "{\n";
    out << "  \"file\": \"RECS.DAT\",\n";
    out << "  \"type\": \"high_scores\",\n";
    out << "  \"record_count\": " << count << ",\n";
    out << "  \"records\": [\n";
    for (size_t i = 0; i < count; ++i) {
        std::string name = encodedRecordName(records[i]);
        out << "    {\n";
        out << "      \"index\": " << i << ",\n";
        out << "      \"score\": " << records[i].score << ",\n";
        out << "      \"level\": " << static_cast<int>(records[i].level) << ",\n";
        out << "      \"encoded_name\": " << std::quoted(name) << ",\n";
        out << "      \"decoded_name\": " << std::quoted(records[i].name) << "\n";
        out << "    }" << (i + 1 == count ? "\n" : ",\n");
    }
    out << "  ]\n";
    out << "}\n";
}

}
