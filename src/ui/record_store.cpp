#include "ui/record_store.hpp"

#include <algorithm>
#include <iostream>
#include <utility>

namespace lezac::ui {
using namespace resources;
namespace {
bool scoreLess(uint32_t left, uint32_t right) {
    // DOS compares the signed high word, then the unsigned low word.
    return (left ^ 0x80000000u) < (right ^ 0x80000000u);
}
}

void RecordStore::replaceRecords(std::vector<Record> records) { records_ = std::move(records); }
void RecordStore::setPath(std::string path) { recordPath_ = std::move(path); }
void RecordStore::setPendingNameForFixture(std::string name) { pending_.name = std::move(name); }

bool RecordStore::insertRecord(std::vector<Record>& records, Record record, size_t maxRecords) {
    std::vector<Record> before = records;
    size_t position = std::min(records.size(), maxRecords);
    while (position > 0 && scoreLess(records[position - 1].score, record.score)) --position;
    // Original rank eight writes outside the table; do not corrupt host memory.
    if (position == maxRecords) return false;
    records.insert(records.begin() + static_cast<std::ptrdiff_t>(position), std::move(record));
    if (records.size() > maxRecords) records.resize(maxRecords);
    if (records.size() != before.size()) return true;
    for (size_t i = 0; i < records.size(); ++i) {
        if (records[i].score != before[i].score || records[i].level != before[i].level ||
            records[i].name != before[i].name || records[i].nameLength != before[i].nameLength ||
            encodedRecordName(records[i]) != encodedRecordName(before[i])) return true;
    }
    return false;
}

bool RecordStore::scoreQualifies(uint32_t score) const {
    return records_.size() < 7 || !scoreLess(score, records_[6].score);
}

void RecordStore::beginEndRun(EndReason reason, int levelIndex, int,
                             uint32_t score, uint32_t score2) {
    uint8_t finalLevel = static_cast<uint8_t>(std::clamp(levelIndex + 1, 1, 255));
    pendingRecordQueue_.clear();
    clearPendingRecord();
    pendingRecordQueue_.push_back({score, finalLevel, 1, reason});
    pendingRecordQueue_.push_back({score2, finalLevel, 2, reason});
}

void RecordStore::clearPendingRecord() { pending_ = {}; pendingActive_ = false; }
void RecordStore::clearQueue() { pendingRecordQueue_.clear(); }

bool RecordStore::startNextPendingRecord() {
    while (!pendingRecordQueue_.empty()) {
        PendingRecordEntry entry = pendingRecordQueue_.front();
        pendingRecordQueue_.erase(pendingRecordQueue_.begin());
        if (!scoreQualifies(entry.score)) continue;
        static_cast<PendingRecordEntry&>(pending_) = entry;
        pending_.name.clear();
        pendingActive_ = true;
        return true;
    }
    clearPendingRecord();
    return false;
}

void RecordStore::appendNameCharacter(char character) {
    if (character != '\0' && pending_.name.size() < 8) pending_.name.push_back(character);
}
void RecordStore::eraseNameCharacter() { if (!pending_.name.empty()) pending_.name.pop_back(); }

RecordStore::CommitResult RecordStore::finalizePendingRecord() {
    if (!pendingActive_) return CommitResult::NoPending;
    Record record = makeRecord(pending_.score, pending_.level, pending_.name);
    std::vector<Record> updatedRecords = records_;
    insertRecord(updatedRecords, record);
    try {
        saveRecords(recordPath_, updatedRecords);
    } catch (const std::exception& e) {
        std::cerr << "warning: could not save records: " << e.what() << '\n';
        return CommitResult::SaveFailed;
    }
    records_ = std::move(updatedRecords);
    clearPendingRecord();
    return CommitResult::Saved;
}
}
