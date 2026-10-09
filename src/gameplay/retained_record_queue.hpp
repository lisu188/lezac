#pragma once

#include <algorithm>
#include <cstddef>
#include <type_traits>
#include <vector>

namespace lezac::gameplay {

// Original queue compaction moves live records without clearing the retired tail.
template <typename Record>
class RetainedRecordQueue {
    static_assert(std::is_trivially_copyable_v<Record>);
    std::vector<Record> slots_;
    size_t live_ = 0;

public:
    using iterator = typename std::vector<Record>::iterator;
    using const_iterator = typename std::vector<Record>::const_iterator;

    size_t size() const { return live_; }
    bool empty() const { return live_ == 0; }
    iterator begin() { return slots_.begin(); }
    iterator end() { return begin() + static_cast<std::ptrdiff_t>(live_); }
    const_iterator begin() const { return slots_.begin(); }
    const_iterator end() const { return begin() + static_cast<std::ptrdiff_t>(live_); }
    Record& operator[](size_t index) { return slots_[index]; }
    const Record& operator[](size_t index) const { return slots_[index]; }
    Record& front() { return slots_[0]; }
    const Record& front() const { return slots_[0]; }
    Record& back() { return slots_[live_ - 1]; }
    const Record& back() const { return slots_[live_ - 1]; }

    void clear() { live_ = 0; }
    void pop_back() { --live_; }
    void push_back(const Record& record) {
        if (live_ == slots_.size()) slots_.push_back(record);
        else slots_[live_] = record;
        ++live_;
    }
    iterator erase(iterator position) {
        const auto index = position - begin();
        std::copy(position + 1, end(), position);
        --live_;
        return begin() + index;
    }

    Record& retainedSlot(size_t index) {
        if (index >= slots_.size()) slots_.resize(index + 1);
        return slots_[index];
    }
    const Record& retainedSlot(size_t index) const { return slots_.at(index); }
};

}  // namespace lezac::gameplay
