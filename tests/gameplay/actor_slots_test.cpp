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

void playerVisuals() {
    ActorSlots slots;
    slots.resetForLevel({16,16,0,0});
    const auto word = [](auto& row, size_t offset, uint16_t value) {
        row[offset] = static_cast<uint8_t>(value); row[offset + 1] = static_cast<uint8_t>(value >> 8);
    };
    for (size_t index = 0; index < 2; ++index) {
        const auto retained = slots.state();
        auto expected = retained;
        auto check = [&] {
            require(slots.state().visuals == expected.visuals, "player visual write touched another field or row");
            require(slots.state().actors == retained.actors && slots.state().links == retained.links &&
                slots.state().count == retained.count && slots.state().visualCount == retained.visualCount &&
                slots.state().success == retained.success, "player visual write touched unrelated storage");
        };
        auto& row = expected.visuals[index];
        slots.setPlayerPosition(index,65535,32768);
        word(row,0,65535); word(row,2,32768); check();
        slots.setPlayerSpriteOffset(index,{7,9,0x35,0xa7});
        row[6]=0x35; row[7]=0xa7; check();
        slots.reducePlayerDimensions(index); row[4]=row[5]=1; check();
        slots.setPlayerSpriteOffset(index,{16,16,0x79,0x13});
        row[6]=0x79; row[7]=0x13; check();
        slots.setPlayerDescriptor(index,{12,15,0x81,0x23});
        row[4]=12; row[5]=15; row[6]=0x81; row[7]=0x23; check();
        slots.setPlayerY(index,65535); word(row,2,65535); check();
        slots.hidePlayer(index); word(row,0,10000); check();
    }
    const auto retained = slots.state();
    for (size_t index : {size_t{2}, size_t(-1)}) {
        rejects<std::out_of_range>([&] { slots.setPlayerPosition(index,1,2); });
        rejects<std::out_of_range>([&] { slots.setPlayerY(index,1); });
        rejects<std::out_of_range>([&] { slots.hidePlayer(index); });
        rejects<std::out_of_range>([&] { slots.setPlayerSpriteOffset(index,{1,2,3,4}); });
        rejects<std::out_of_range>([&] { slots.setPlayerDescriptor(index,{1,2,3,4}); });
        rejects<std::out_of_range>([&] { slots.reducePlayerDimensions(index); });
        require(slots.state().visuals == retained.visuals && slots.state().actors == retained.actors,
            "invalid player index changed storage before rejection");
    }
}

void playerHealth() {
    ActorSlots slots;
    auto state = slots.state();
    for (size_t slot = 0; slot < state.actors.size(); ++slot)
        for (size_t byte = 0; byte < state.actors[slot].size(); ++byte)
            state.actors[slot][byte] = static_cast<uint8_t>(slot * 31 + byte * 17);
    state.actors[0][1] = 1;
    slots.restoreForFixture(state, {});
    for (int health = 0; health < 256; ++health) {
        auto expected = state;
        expected.actors[0][36] = static_cast<uint8_t>(health);
        slots.setPlayer2Health(static_cast<uint8_t>(health));
        require(slots.state().actors == expected.actors && slots.state().visuals == expected.visuals &&
            slots.state().links == expected.links && slots.state().count == expected.count &&
            slots.state().visualCount == expected.visualCount && slots.state().success == expected.success,
            "player health write cleared another field or actor");
    }
    slots.setPlayer2Health(41);
    slots.resetForLevel({16,16,0,0});
    require(slots.state().actors[0][36] == 41, "level reset refilled reserved player health");
    require(slots.append(1,{10,12,5,1,0,0,184,100},{16,16,0,0}), "health compaction probe did not allocate");
    require(slots.retire(1) && slots.state().actors[0][36] == 41, "nonplayer retirement changed reserved player health");
}

void run() {
    playerVisuals();
    playerHealth();
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
