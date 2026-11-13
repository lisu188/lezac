#pragma once

#include "ui/models.hpp"
#include "ui/record_adjacent_memory.hpp"
#include "resources/records.hpp"
#include <string>
#include <vector>

namespace lezac::ui {
class RecordStore {
public:
    enum class CommitResult { NoPending, SaveFailed, Saved };
    const std::vector<resources::Record>& records() const { return records_; }
    const std::string& path() const { return recordPath_; }
    const PendingRecordState& pending() const { return pending_; }
    bool hasPendingRecord() const { return pendingActive_; }
    const RecordAdjacentMemory& adjacentMemory() const { return adjacentMemory_; }
    void seedAdjacentMemoryForFixture(const RecordAdjacentMemory::Bytes& bytes) {
        adjacentMemory_.seedForFixture(bytes);
    }
    void replaceRecords(std::vector<resources::Record> records);
    void setPath(std::string path);
    void setPendingNameForFixture(std::string name);
    bool scoreQualifies(uint32_t score) const;
    void beginEndRun(EndReason reason, int levelIndex, int playerCount,
                     uint32_t score, uint32_t score2);
    void clearPendingRecord();
    void clearQueue();
    bool startNextPendingRecord();
    void appendNameCharacter(char character);
    void eraseNameCharacter();
    CommitResult finalizePendingRecord();
    static bool insertRecord(std::vector<resources::Record>& records,
                             resources::Record record, size_t maxRecords = 7);
private:
    static bool insertRecordWithAdjacent(std::vector<resources::Record>& records,
        resources::Record record, size_t maxRecords, RecordAdjacentMemory* adjacent);
    std::vector<resources::Record> records_;
    RecordAdjacentMemory adjacentMemory_;
    std::string recordPath_ = "RECS.DAT";
    PendingRecordState pending_;
    bool pendingActive_ = false;
    std::vector<PendingRecordEntry> pendingRecordQueue_;
};
}
