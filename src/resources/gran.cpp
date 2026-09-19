#include "resources/gran.hpp"

#include "resources/io.hpp"
#include "resources/json.hpp"

#include <algorithm>
#include <stdexcept>
#include <utility>

namespace lezac::resources {

GranBank loadGran(const std::string& path) {
    auto json = readTextFile(path);
    GranBank bank;
    bank.recordSize = static_cast<size_t>(extractInt(json, "record_size", static_cast<int>(kGranRecordSize)));
    if (bank.recordSize != kGranRecordSize) {
        throw std::runtime_error(path + " record_size does not match GRAN.MST fixed record size");
    }
    auto recordObjects = extractObjectArray(json, "records");
    if (recordObjects.size() != 7) {
        throw std::runtime_error(path + " records array does not contain seven records");
    }
    for (const auto& recJson : recordObjects) {
        GranRecord record;
        record.bytes = parseHexByteList(extractString(recJson, "bytes_hex"));
        if (record.bytes.size() != bank.recordSize) {
            throw std::runtime_error(path + " record length does not match record_size");
        }
        bank.records.push_back(std::move(record));
    }
    return bank;
}

GranBank loadRawGran(const std::string& path) {
    auto data = readFile(path);
    if (data.size() != 7 * kGranRecordSize) {
        throw std::runtime_error(path + " raw size does not match seven GRAN records");
    }
    GranBank bank;
    bank.recordSize = kGranRecordSize;
    for (size_t off = 0; off < data.size(); off += kGranRecordSize) {
        GranRecord record;
        record.bytes.insert(record.bytes.end(),
                            data.begin() + static_cast<std::ptrdiff_t>(off),
                            data.begin() +
                                static_cast<std::ptrdiff_t>(off + kGranRecordSize));
        bank.records.push_back(std::move(record));
    }
    return bank;
}

}
