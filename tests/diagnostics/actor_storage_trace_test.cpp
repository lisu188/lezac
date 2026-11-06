#include "diagnostics/actor_storage_trace.hpp"

#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

template<class Records>
std::string expectedHex(const Records& records) {
    std::ostringstream out;
    out << '"' << std::hex << std::setfill('0');
    for (const auto& record : records)
        for (uint8_t byte : record) out << std::setw(2) << unsigned(byte);
    return out.str() + '"';
}

void run() {
    using lezac::gameplay::ActorSlots;
    using lezac::gameplay::ActorStorage;
    namespace trace = lezac::diagnostics::level1;
    ActorSlots slots;
    auto state = slots.state();
    auto fill = [](auto& records) {
        size_t index = 0;
        for (auto& record : records)
            for (auto& byte : record) byte = static_cast<uint8_t>(index++ * 17 + 139);
    };
    fill(state.actors);
    fill(state.visuals);
    fill(state.links);
    state.links[0][15] = 7;
    state.success = 65535;
    std::array<uint64_t, ActorStorage::capacity + 1> orders{};
    size_t cases = 0;
    for (uint8_t count : {uint8_t(0), uint8_t(1), uint8_t(30)}) {
        state.count = count;
        state.visualCount = static_cast<uint8_t>(count + 2);
        for (size_t slot = 0; slot <= count; ++slot) state.actors[slot][1] = static_cast<uint8_t>(slot + 1);
        for (size_t slot = 1; slot < orders.size(); ++slot)
            orders[slot] = slot <= count ? UINT64_MAX - slot : 0;
        slots.restoreForFixture(state, orders);
        std::vector<std::string> expectedOrders;
        for (size_t slot = 1; slot <= count; ++slot) expectedOrders.push_back(std::to_string(orders[slot]));
        const auto expected = trace::object({{"kind", trace::quote("checkpoint")},
            {"seq", "18446744073709551615"}, {"tick", "20000"}, {"phase", trace::quote("post_update")},
            {"count", std::to_string(count)}, {"visual_count", std::to_string(state.visualCount)},
            {"success", "65535"}, {"orders", trace::array(expectedOrders)},
            {"actors_hex", expectedHex(state.actors)}, {"visuals_hex", expectedHex(state.visuals)},
            {"links_hex", expectedHex(state.links)}});
        for (size_t repeat = 0; repeat < 2; ++repeat)
            require(lezac::diagnostics::actorStorageCheckpoint(slots, UINT64_MAX, 20000, "post_update") == expected,
                "owned storage trace omitted or changed backing bytes");
        require(slots.state().actors == state.actors && slots.state().visuals == state.visuals &&
            slots.state().links == state.links && slots.state().count == state.count &&
            slots.state().visualCount == state.visualCount && slots.state().success == state.success,
            "owned storage trace mutated backing");
        for (size_t slot = 1; slot <= count; ++slot)
            require(slots.order(slot) == orders[slot], "owned storage trace mutated identities");
        ++cases;
    }
    const auto corpseOrder = orders[1];
    const auto storedHp = slots.actor(corpseOrder)[36];
    slots.enterMonsterCorpse(corpseOrder);
    require(slots.actor(corpseOrder)[36] == storedHp, "corpse changed retained HP");
    const auto before = slots.state();
    const auto sample = lezac::diagnostics::actorStorageCheckpoint(slots, 9, 18620, "present");
    require(sample.find(expectedHex(before.actors)) != std::string::npos, "corpse backing not retained");
    require(slots.retire(corpseOrder), "compaction fixture did not retire actor");
    const auto compacted = slots.state();
    require(lezac::diagnostics::actorStorageCheckpoint(slots, 10, 18620, "post_update").find(
        expectedHex(compacted.actors)) != std::string::npos, "compacted inactive tail not retained");
    std::cout << "actor_storage_trace=ok boundary_counts=" << cases
              << " bytes_per_sample=1570 read_only=1 inactive_tail=1 corpse=1 compaction=1\n";
}
} // namespace

int main() {
    try { run(); return 0; }
    catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
