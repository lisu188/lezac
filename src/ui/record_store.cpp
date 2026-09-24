#include "ui/record_store.hpp"

#include <algorithm>
#include <iostream>
#include <utility>

namespace lezac::ui {
using namespace resources;

void RecordStore::replaceRecords(std::vector<Record> records) { records_ = std::move(records); }
void RecordStore::setPath(std::string path) { recordPath_ = std::move(path); }
void RecordStore::setPendingNameForFixture(std::string name) { pending_.name = std::move(name); }

bool RecordStore::insertRecord(std::vector<Record>& records, Record record, size_t maxRecords) {
    std::vector<Record> before = records;
    records.push_back(std::move(record));
    std::stable_sort(records.begin(), records.end(),
                     [](const Record& a, const Record& b) { return a.score > b.score; });
    if (records.size() > maxRecords) records.resize(maxRecords);
    if (records.size() != before.size()) return true;
    for (size_t i = 0; i < records.size(); ++i) {
        if (records[i].score != before[i].score || records[i].level != before[i].level ||
            records[i].name != before[i].name ||
            encodedRecordName(records[i]) != encodedRecordName(before[i])) return true;
    }
    return false;
}

bool RecordStore::scoreQualifies(uint32_t score) const {
    return score != 0 && (records_.size() < 7 || score > records_.back().score);
}

void RecordStore::beginEndRun(EndReason reason, int levelIndex, int playerCount,
                             uint32_t score, uint32_t score2) {
    uint8_t finalLevel = static_cast<uint8_t>(std::clamp(levelIndex + 1, 1, 255));
    pendingRecordQueue_.clear();
    if (score != 0) pendingRecordQueue_.push_back({score, finalLevel, 1, reason});
    if (playerCount > 1 && score2 != 0) pendingRecordQueue_.push_back({score2, finalLevel, 2, reason});
}

void RecordStore::clearPendingRecord() { pending_ = {}; }
void RecordStore::clearQueue() { pendingRecordQueue_.clear(); }

bool RecordStore::startNextPendingRecord() {
    while (!pendingRecordQueue_.empty()) {
        PendingRecordEntry entry = pendingRecordQueue_.front();
        pendingRecordQueue_.erase(pendingRecordQueue_.begin());
        if (!scoreQualifies(entry.score)) continue;
        static_cast<PendingRecordEntry&>(pending_) = entry;
        pending_.name.clear();
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
    if (pending_.score == 0) return CommitResult::NoPending;
    Record record = makeRecord(pending_.score, pending_.level, pending_.name);
    std::vector<Record> updatedRecords = records_;
    bool changed = insertRecord(updatedRecords, record);
    try {
        if (changed) saveRecords(recordPath_, updatedRecords);
    } catch (const std::exception& e) {
        std::cerr << "warning: could not save records: " << e.what() << '\n';
        return CommitResult::SaveFailed;
    }
    records_ = std::move(updatedRecords);
    clearPendingRecord();
    return CommitResult::Saved;
}
}
