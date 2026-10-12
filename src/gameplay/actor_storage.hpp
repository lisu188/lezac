#pragma once

#include "gameplay/actor_models.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <stdexcept>

namespace lezac::gameplay {

class ActorStorage {
public:
    using Actor = std::array<uint8_t, 38>;
    using Visual = std::array<uint8_t, 8>;
    using Link = std::array<uint8_t, 16>;
    using Descriptor = std::array<uint8_t, 4>;
    static constexpr size_t capacity = 30;

    struct State {
        std::array<Actor, capacity + 1> actors{}; // Slot0 is player2.
        // Row32 is inactive guard memory; its last four bytes alias descriptor0.
        std::array<Visual, capacity + 3> visuals{};
        std::array<Link, 8> links{};
        uint8_t count = 0;
        uint8_t visualCount = 2;
        uint16_t success = 0;
    };

    struct Construction {
        uint8_t kind;
        uint8_t timer;
        uint8_t behavior;
        uint16_t sprite;
        int16_t vx;
        int16_t vy;
        int16_t x;
        int16_t y;
    };

    const State& state() const { return state_; }

    // DS:2072 is shared by allocation and the generic tile-damage query.
    void setSharedResult(uint16_t value) { state_.success = value; }

    void restore(const State& state) {
        if (state.count > capacity || state.visualCount != state.count + 2 || state.links[0][15] > 7) {
            throw std::invalid_argument("invalid actor storage counts");
        }
        for (size_t slot = 0; slot <= state.count; ++slot) {
            if (state.actors[slot][1] >= state.visualCount) {
                throw std::invalid_argument("invalid actor visual reference");
            }
        }
        state_ = state;
    }

    Actor& actor(size_t slot) {
        if (slot > state_.count) throw std::out_of_range("inactive actor slot");
        return state_.actors[slot];
    }

    Visual& visual(size_t index) {
        if (index >= state_.visualCount) throw std::out_of_range("inactive visual row");
        return state_.visuals[index];
    }

    size_t append(const Construction& input, const Descriptor& descriptor) {
        if (state_.count == capacity) {
            state_.success = 0;
            return 0;
        }
        const size_t slot = ++state_.count;
        Actor& raw = state_.actors[slot];
        raw[0] = input.kind;
        raw[1] = state_.visualCount;
        raw[2] = input.timer;
        word(raw, 6, static_cast<uint16_t>(clampConstructedActorVelocity8(input.vx)));
        word(raw, 8, static_cast<uint16_t>(clampConstructedActorVelocity8(input.vy)));
        word(raw, 10, 0);
        word(raw, 12, 0);
        raw[20] = input.sprite == 31 ? 0 : static_cast<uint8_t>(16 - descriptor[1]);
        raw[21] = input.behavior;
        Visual& row = state_.visuals[state_.visualCount++];
        word(row, 0, static_cast<uint16_t>(input.x));
        word(row, 2, static_cast<uint16_t>(input.y));
        for (size_t i = 0; i < descriptor.size(); ++i) row[i + 4] = descriptor[i];
        state_.success = 1;
        return slot;
    }

    bool retire(size_t slot) {
        if (slot == 0) throw std::out_of_range("player2 is not a nonplayer allocation");
        if (slot > state_.count) return false;
        const uint8_t removedVisual = state_.actors[slot][1];
        for (size_t row = removedVisual; row + 1 < state_.visualCount; ++row) {
            state_.visuals[row] = state_.visuals[row + 1];
        }
        --state_.visualCount;
        for (size_t row = slot; row < state_.count; ++row) state_.actors[row] = state_.actors[row + 1];
        --state_.count;
        for (size_t row = 0; row <= state_.count; ++row) {
            uint8_t& index = state_.actors[row][1];
            if (index > removedVisual) --index;
        }
        for (size_t row = 1; row <= state_.links[0][15]; ++row) {
            for (size_t offset = 0; offset < 2; ++offset) {
                uint8_t& index = state_.links[row][offset];
                if (index > removedVisual) --index;
            }
        }
        return true;
    }

    void resetForLevel(const Descriptor& playerDescriptor) {
        // Only the storage portion of 2BA4..2BDC / 2D5A..2E0B, not all level globals.
        state_.count = 0;
        state_.links[0][15] = 0;
        state_.visualCount = 2;
        for (size_t row = 0; row < 2; ++row) {
            for (size_t i = 0; i < playerDescriptor.size(); ++i) {
                state_.visuals[row][i + 4] = playerDescriptor[i];
            }
        }
        Actor& player2 = state_.actors[0];
        player2[0] = 0;
        player2[1] = 1;
        for (size_t i = 6; i < 16; ++i) player2[i] = 0;
        player2[20] = 0;
        player2[21] = 1;
        const auto animation = ActorAnimation::initialize(21, 28, 1, 1).packed();
        for (size_t i = 0; i < animation.size(); ++i) player2[22 + i] = animation[i];
    }

private:
    template <size_t Size>
    static void word(std::array<uint8_t, Size>& raw, size_t offset, uint16_t value) {
        raw[offset] = static_cast<uint8_t>(value);
        raw[offset + 1] = static_cast<uint8_t>(value >> 8);
    }

    State state_;
};

} // namespace lezac::gameplay
