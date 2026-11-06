#pragma once

#include "diagnostics/level1_trace.hpp"
#include "gameplay/actor_slots.hpp"

namespace lezac::diagnostics {

template<size_t Rows, size_t Columns>
inline std::string actorStorageHex(const std::array<std::array<uint8_t, Columns>, Rows>& records) {
    std::vector<uint8_t> bytes;
    bytes.reserve(Rows * Columns);
    for (const auto& record : records) bytes.insert(bytes.end(), record.begin(), record.end());
    return level1::quote(level1::hexBytes(bytes));
}

// Observe the owned backing as-is, including reserved records and inactive tails.
inline std::string actorStorageCheckpoint(const gameplay::ActorSlots& slots, uint64_t sequence,
                                         uint32_t tick, const char* phase) {
    const auto& state = slots.state();
    std::vector<std::string> orders;
    for (size_t slot = 1; slot <= slots.count(); ++slot) orders.push_back(std::to_string(slots.order(slot)));
    return level1::object({{"kind", level1::quote("checkpoint")}, {"seq", std::to_string(sequence)},
        {"tick", std::to_string(tick)}, {"phase", level1::quote(phase)},
        {"count", std::to_string(state.count)}, {"visual_count", std::to_string(state.visualCount)},
        {"success", std::to_string(state.success)}, {"orders", level1::array(orders)},
        {"player1_hex", level1::quote(level1::hexBytes(std::vector<uint8_t>(state.player1.begin(), state.player1.end())))},
        {"actors_hex", actorStorageHex(state.actors)}, {"visuals_hex", actorStorageHex(state.visuals)},
        {"links_hex", actorStorageHex(state.links)}});
}

} // namespace lezac::diagnostics
