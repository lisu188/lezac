#pragma once

#include "gameplay/actor_slots.hpp"

#include <istream>
#include <ostream>
#include <string>

namespace lezac::diagnostics::transient_storage {

inline uint8_t byte(std::istream& input) {
    const int value = input.get();
    if (value == std::char_traits<char>::eof()) throw std::runtime_error("truncated transient request");
    return static_cast<uint8_t>(value);
}

inline uint16_t word(std::istream& input) {
    const uint16_t low = byte(input);
    return static_cast<uint16_t>(low | (static_cast<uint16_t>(byte(input)) << 8));
}

inline void write(std::ostream& output, uint32_t value, size_t size) {
    for (size_t index = 0; index < size; ++index) output.put(static_cast<char>(value >> (index * 8)));
}

template <typename Rows> void readRows(std::istream& input, Rows& rows) {
    for (auto& row : rows) for (auto& value : row) value = byte(input);
}

template <typename Rows> void writeRows(std::ostream& output, const Rows& rows) {
    for (const auto& row : rows) for (const auto value : row) output.put(static_cast<char>(value));
}

struct Header {
    uint32_t operations;
    std::array<gameplay::ActorSlots::Descriptor, 92> descriptors{};

    explicit Header(std::istream& input) {
        std::string magic(8, '\0');
        input.read(magic.data(), 8);
        if (magic != "LZTW0001") throw std::runtime_error("invalid transient request magic");
        const uint32_t low = word(input);
        operations = low | (static_cast<uint32_t>(word(input)) << 16);
        if (operations == 0 || operations > 100000) throw std::runtime_error("invalid operation count");
        readRows(input, descriptors);
    }

    gameplay::ActorSlots::Descriptor descriptor(uint16_t sprite) const {
        if (sprite >= descriptors.size()) throw std::runtime_error("transient sprite outside descriptor bank");
        return descriptors[sprite];
    }
};

inline gameplay::ActorSlots::State readSeed(std::istream& input) {
    gameplay::ActorSlots::State state;
    readRows(input, state.actors); readRows(input, state.visuals); readRows(input, state.links);
    state.count = byte(input); state.visualCount = byte(input);
    if (byte(input) != state.links[0][15]) throw std::runtime_error("inconsistent link count");
    state.success = word(input);
    if (state.count > gameplay::ActorStorage::capacity) throw std::runtime_error("invalid actor count");
    return state;
}

inline void writeHeader(std::ostream& output, uint32_t operations) {
    output.write("LZTO0001", 8);
    write(output, operations, 4);
}

inline void writeState(std::ostream& output, const gameplay::ActorSlots::State& state) {
    writeRows(output, state.actors); writeRows(output, state.visuals); writeRows(output, state.links);
    write(output, state.count, 1); write(output, state.visualCount, 1);
    write(output, state.links[0][15], 1); write(output, state.success, 2);
}

inline gameplay::TransientActor decode(const gameplay::ActorSlots& slots, uint64_t order) {
    const auto& raw = slots.actor(order);
    const auto& row = slots.visual(order);
    if (raw[21] != 5) throw std::runtime_error("non-transient fixture actor");
    gameplay::TransientActor actor;
    actor.actorOrder = order;
    actor.kind = raw[0]; actor.timer = raw[2]; actor.hotspotY = raw[20];
    actor.x = static_cast<int16_t>(row[0] | (static_cast<uint16_t>(row[1]) << 8));
    actor.y = static_cast<int16_t>(row[2] | (static_cast<uint16_t>(row[3]) << 8));
    actor.vx8 = static_cast<int16_t>(raw[6] | (static_cast<uint16_t>(raw[7]) << 8));
    actor.vy8 = static_cast<int16_t>(raw[8] | (static_cast<uint16_t>(raw[9]) << 8));
    actor.fracX = raw[10]; actor.fracY = raw[12];
    actor.animation = {raw[22], raw[23], raw[24], raw[25], raw[26], raw[27], static_cast<int8_t>(raw[28])};
    actor.animationBackup = slots.animationBackup(order);
    return actor;
}

struct Constructor {
    gameplay::ActorSlots::Construction input{};
    gameplay::ActorAnimation animation;

    explicit Constructor(std::istream& stream) {
        std::array<uint16_t, 8> values{};
        for (auto& value : values) value = word(stream);
        std::array<uint8_t, 7> bytes{};
        for (auto& value : bytes) value = byte(stream);
        if (values[0] != 5 || values[5] != 0) throw std::runtime_error("unsupported fixture constructor");
        input = {static_cast<uint8_t>(values[2]), static_cast<uint8_t>(values[1]), 5, values[3],
            0, static_cast<int16_t>(values[4]), static_cast<int16_t>(values[7]), static_cast<int16_t>(values[6])};
        animation = {bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], static_cast<int8_t>(bytes[6])};
    }
};

inline void finish(std::istream& input, std::ostream& output) {
    if (input.peek() != std::char_traits<char>::eof()) throw std::runtime_error("trailing transient request bytes");
    output.flush();
    if (!output) throw std::runtime_error("cannot write transient output");
}

} // namespace lezac::diagnostics::transient_storage
