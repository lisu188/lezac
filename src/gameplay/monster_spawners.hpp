#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <stdexcept>

namespace lezac::gameplay {

class MonsterSpawnerStorage {
public:
    using Record = std::array<uint8_t, 30>;
    // DS:74A8 is the dummy row; shipped source references select rows 1..8.
    using State = std::array<Record, 9>;

    const State& state() const { return state_; }

    const Record& record(uint8_t source) const {
        if (source >= state_.size()) throw std::out_of_range("monster spawner source");
        return state_[source];
    }

    void loadRecord(uint8_t source, const Record& row) {
        if (source == 0 || source >= state_.size()) throw std::out_of_range("monster spawner source");
        state_[source] = row;
    }

    bool release(uint8_t source) {
        if (source == 0) return false;
        if (source >= state_.size()) throw std::out_of_range("monster spawner source");
        auto& available = state_[source][10];
        available = static_cast<uint8_t>(available + 1u);
        return true;
    }

    bool tick(uint8_t source) {
        if (source == 0 || source >= state_.size()) throw std::out_of_range("monster spawner source");
        auto& row = state_[source];
        row[27] = static_cast<uint8_t>(row[27] - 1u);
        if (row[27] || !row[10] || !row[9] || row[8] != 1) return false;
        row[27] = row[28];
        return true;
    }

    void consume(uint8_t source) {
        if (source == 0 || source >= state_.size()) throw std::out_of_range("monster spawner source");
        --state_[source][9];
        --state_[source][10];
    }

    void restoreForFixture(const State& state) { state_ = state; }

private:
    State state_{};
};

} // namespace lezac::gameplay
