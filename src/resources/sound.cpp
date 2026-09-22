#include "resources/sound.hpp"

#include "resources/io.hpp"
#include "resources/json.hpp"
#include "resources/binary.hpp"

#include <algorithm>
#include <stdexcept>
#include <utility>

namespace lezac::resources {

SoundBank loadSon(const std::string& path) {
    auto json = readTextFile(path);
    SoundBank bank;
    bank.recordSize = static_cast<uint16_t>(extractInt(json, "record_size"));
    int declaredCount = extractInt(json, "record_count", -1);
    auto recordObjects = extractObjectArray(json, "records");
    if (declaredCount >= 0 && declaredCount != static_cast<int>(recordObjects.size())) {
        throw std::runtime_error(path + " record_count does not match records array");
    }
    for (const auto& recJson : recordObjects) {
        SoundEffectRecord record;
        record.bytes = parseHexByteList(extractString(recJson, "bytes_hex"));
        if (record.bytes.size() != bank.recordSize) {
            throw std::runtime_error(path + " record length does not match record_size");
        }
        bank.payload.insert(bank.payload.end(), record.bytes.begin(), record.bytes.end());
        bank.records.push_back(std::move(record));
    }
    if (bank.payload.empty() || bank.payload.size() % kSoundStepSize != 0) {
        throw std::runtime_error(path + " payload is not a whole number of six-byte steps");
    }
    bank.stepCount = bank.payload.size() / kSoundStepSize;
    return bank;
}

SoundBank loadRawSon(const std::string& path) {
    auto data = readFile(path);
    if (data.size() < 2) {
        throw std::runtime_error(path + " is too small for a sound header");
    }
    SoundBank bank;
    bank.stepCount = le16(data, 0);
    size_t payloadSize = bank.stepCount * kSoundStepSize;
    if (data.size() != 2 + payloadSize) {
        throw std::runtime_error(path + " raw payload size mismatch");
    }
    bank.payload.insert(bank.payload.end(), data.begin() + 2, data.end());
    bank.recordSize = 130;
    if (bank.payload.size() % bank.recordSize != 0) {
        throw std::runtime_error(path + " raw payload cannot be split into JSON chunks");
    }
    for (size_t off = 0; off < bank.payload.size(); off += bank.recordSize) {
        SoundEffectRecord record;
        record.bytes.insert(record.bytes.end(),
                            bank.payload.begin() + static_cast<std::ptrdiff_t>(off),
                            bank.payload.begin() +
                                static_cast<std::ptrdiff_t>(off + bank.recordSize));
        bank.records.push_back(std::move(record));
    }
    return bank;
}

}
