#pragma once

#include "gameplay/actor_storage.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <stdexcept>

namespace lezac::gameplay {

// Bind typed gameplay identities to physical records without changing the
// verified allocator's stable compaction or untouched inactive tail bytes.
class ActorSlots {
public:
    using State = ActorStorage::State;
    using Construction = ActorStorage::Construction;
    using Descriptor = ActorStorage::Descriptor;

    size_t count() const { return storage_.state().count; }
    const State& state() const { return storage_.state(); }

    size_t find(uint64_t order) const {
        if (order == 0) return 0;
        for (size_t slot = 1; slot <= count(); ++slot) {
            if (orders_[slot] == order) return slot;
        }
        return 0;
    }

    uint64_t order(size_t slot) const {
        if (slot == 0 || slot > count()) throw std::out_of_range("inactive actor identity");
        return orders_[slot];
    }

    bool append(uint64_t order, const Construction& input, const Descriptor& descriptor) {
        if (order == 0 || find(order)) throw std::invalid_argument("invalid actor allocation identity");
        const size_t slot = storage_.append(input, descriptor);
        if (slot == 0) return false;
        orders_[slot] = order;
        return true;
    }

    bool retire(uint64_t order) {
        const size_t slot = find(order);
        if (slot == 0) return false;
        const size_t oldCount = count();
        storage_.retire(slot);
        for (size_t index = slot; index < oldCount; ++index) orders_[index] = orders_[index + 1];
        orders_[oldCount] = 0;
        return true;
    }

    ActorAnimation animationBackup(uint64_t order) const {
        const size_t slot = require(order);
        const auto& raw = state().actors[slot];
        return {raw[29], raw[30], raw[31], raw[32], raw[33], raw[34], static_cast<int8_t>(raw[35])};
    }

    void setAnimationBackup(uint64_t order, const ActorAnimation& animation) {
        auto& raw = storage_.actor(require(order));
        const auto bytes = animation.packed();
        std::copy(bytes.begin(), bytes.end(), raw.begin() + 29);
    }

    void resetForLevel(const Descriptor& playerDescriptor) {
        storage_.resetForLevel(playerDescriptor);
        orders_.fill(0);
    }

    // Fixture restoration is deliberately explicit; normal play never rebuilds
    // physical storage from the typed actor vectors.
    void restoreForFixture(const State& state, const std::array<uint64_t, ActorStorage::capacity + 1>& orders) {
        if (state.count > ActorStorage::capacity) throw std::invalid_argument("invalid fixture actor count");
        for (size_t slot = 1; slot <= state.count; ++slot) {
            if (orders[slot] == 0) throw std::invalid_argument("missing fixture actor identity");
            for (size_t previous = 1; previous < slot; ++previous) {
                if (orders[previous] == orders[slot]) throw std::invalid_argument("duplicate fixture actor identity");
            }
        }
        for (size_t slot = state.count + 1; slot < orders.size(); ++slot) {
            if (orders[slot] != 0) throw std::invalid_argument("inactive fixture actor identity");
        }
        if (orders[0] != 0) throw std::invalid_argument("player2 fixture identity");
        storage_.restore(state);
        orders_ = orders;
    }

private:
    size_t require(uint64_t order) const {
        const size_t slot = find(order);
        if (slot == 0) throw std::out_of_range("unbound production actor");
        return slot;
    }

    ActorStorage storage_;
    std::array<uint64_t, ActorStorage::capacity + 1> orders_{};
};

} // namespace lezac::gameplay
