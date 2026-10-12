#include "gameplay/actor_slots.hpp"

#include <algorithm>
#include <array>
#include <iostream>
#include <stdexcept>
#include <vector>

using lezac::gameplay::ActorAnimation;
using lezac::gameplay::ActorSlots;
using lezac::gameplay::ActorStorage;

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

template<class Exception, class Action>
void rejects(Action action) {
    try { action(); }
    catch (const Exception&) { return; }
    throw std::runtime_error("actor slot invalid input was accepted");
}

ActorAnimation animation(const std::array<uint8_t, 7>& bytes) {
    return {bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], static_cast<int8_t>(bytes[6])};
}

void run() {
    ActorSlots slots;
    auto seed = slots.state();
    std::array<std::array<uint8_t, 7>, ActorStorage::capacity + 1> retained{};
    for (size_t slot = 1; slot < retained.size(); ++slot) {
        for (size_t byte = 0; byte < 7; ++byte) retained[slot][byte] = static_cast<uint8_t>(slot * 17 + byte * 31);
        std::copy(retained[slot].begin(), retained[slot].end(), seed.actors[slot].begin() + 29);
    }
    slots.restoreForFixture(seed, {});
    const ActorSlots::Descriptor descriptor{{8, 16, 42, 0}};
    const ActorSlots::Construction input{10, 12, 5, 69, 0, -128, 184, 100};
    std::vector<uint64_t> live;
    uint64_t next = 1;
    size_t appended = 0, retired = 0, resets = 0, backupWrites = 0;
    auto check = [&] {
        require(slots.count() == live.size(), "actor slot count mismatch");
        require(slots.find(0) == 0, "zero identity resolved");
        for (size_t index = 0; index < live.size(); ++index) {
            require(slots.order(index + 1) == live[index] && slots.find(live[index]) == index + 1,
                "stable actor identity compaction mismatch");
            require(slots.animationBackup(live[index]).packed() == retained[index + 1],
                "physical backup inheritance mismatch");
        }
        for (size_t slot = 1; slot < retained.size(); ++slot) {
            require(std::equal(retained[slot].begin(), retained[slot].end(), slots.state().actors[slot].begin() + 29),
                "inactive backup bytes changed");
        }
    };
    for (size_t operation = 0; operation < 1800; ++operation) {
        if (operation && operation % 97 == 0) {
            slots.resetForLevel(descriptor);
            live.clear();
            ++resets;
        } else if (!live.empty() && operation % 7 == 0) {
            const size_t index = (operation * 13) % live.size();
            require(slots.retire(live[index]), "live actor retirement failed");
            for (size_t slot = index + 1; slot < live.size(); ++slot) retained[slot] = retained[slot + 1];
            live.erase(live.begin() + static_cast<std::ptrdiff_t>(index));
            ++retired;
        } else if (!live.empty() && operation % 11 == 0) {
            const size_t index = (operation * 19) % live.size();
            std::array<uint8_t, 7> value{};
            for (size_t byte = 0; byte < value.size(); ++byte) value[byte] = static_cast<uint8_t>(operation + byte * 23);
            slots.setAnimationBackup(live[index], animation(value));
            retained[index + 1] = value;
            ++backupWrites;
        } else {
            const auto before = slots.state();
            const bool allocated = slots.append(next, input, descriptor);
            require(allocated == (live.size() < ActorStorage::capacity), "actor slot capacity mismatch");
            if (allocated) { live.push_back(next++); ++appended; }
            else require(slots.state().actors == before.actors && slots.state().visuals == before.visuals,
                "failed allocation changed physical payload");
        }
        check();
    }
    rejects<std::invalid_argument>([&] { slots.append(0, input, descriptor); });
    require(!live.empty(), "empty final slot contract fixture");
    rejects<std::invalid_argument>([&] { slots.append(live.front(), input, descriptor); });
    rejects<std::out_of_range>([&] { slots.order(0); });
    rejects<std::out_of_range>([&] { slots.order(slots.count() + 1); });
    rejects<std::out_of_range>([&] { slots.animationBackup(next + 100); });
    rejects<std::out_of_range>([&] { slots.setAnimationBackup(0, {}); });
    require(!slots.retire(0) && !slots.retire(next + 100), "unknown identity retired");
    const auto beforeInvalid = slots.state();
    std::array<uint64_t, ActorStorage::capacity + 1> orders{};
    for (size_t index = 0; index < live.size(); ++index) orders[index + 1] = live[index];
    auto malformed = beforeInvalid;
    malformed.count = 255;
    rejects<std::invalid_argument>([&] { slots.restoreForFixture(malformed, orders); });
    auto invalidOrders = orders;
    invalidOrders[1] = 0;
    rejects<std::invalid_argument>([&] { slots.restoreForFixture(beforeInvalid, invalidOrders); });
    invalidOrders = orders;
    invalidOrders[0] = 123;
    rejects<std::invalid_argument>([&] { slots.restoreForFixture(beforeInvalid, invalidOrders); });
    invalidOrders = orders;
    invalidOrders[2] = invalidOrders[1];
    rejects<std::invalid_argument>([&] { slots.restoreForFixture(beforeInvalid, invalidOrders); });
    ActorSlots empty;
    std::array<uint64_t, ActorStorage::capacity + 1> inactiveOrders{};
    inactiveOrders[1] = 123;
    rejects<std::invalid_argument>([&] { empty.restoreForFixture(empty.state(), inactiveOrders); });
    malformed = beforeInvalid;
    malformed.visualCount = 0;
    rejects<std::invalid_argument>([&] { slots.restoreForFixture(malformed, orders); });
    require(slots.state().actors == beforeInvalid.actors && slots.state().visualCount == beforeInvalid.visualCount,
        "invalid restoration changed physical state");
    check();
    std::cout << "actor_slots=ok operations=1800 appended=" << appended << " retired=" << retired
              << " resets=" << resets << " backup_writes=" << backupWrites
              << " capacity=30 invalid_count_255=rejected compiled_binding=1 production_app=0 whole_game_claim=0\n";
}
} // namespace

int main() {
    try { run(); return 0; }
    catch (const std::exception& error) { std::cerr << "fatal: " << error.what() << '\n'; return 1; }
}
