#include "gameplay/actor_slots.hpp"

#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

using lezac::gameplay::ActorSlots;
namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
void word(ActorSlots::State& state, size_t offset, uint16_t value) {
    state.links[0][offset] = static_cast<uint8_t>(value);
    state.links[0][offset + 1] = static_cast<uint8_t>(value >> 8);
}
bool equal(const ActorSlots::State& a, const ActorSlots::State& b) {
    return a.actors == b.actors && a.visuals == b.visuals && a.links == b.links &&
        a.count == b.count && a.visualCount == b.visualCount && a.success == b.success;
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 1 || argc == 2, "invalid alias stream arguments");
        ActorSlots slots;
        auto seeded = slots.state();
        const auto fill = [](auto& rows) {
            for (size_t row = 0; row < rows.size(); ++row)
                for (size_t byte = 0; byte < rows[row].size(); ++byte)
                    rows[row][byte] = static_cast<uint8_t>(row * 31 + byte * 17 + 53);
        };
        fill(seeded.actors); fill(seeded.visuals); fill(seeded.links);
        seeded.actors[0][1] = 1; seeded.links[0][15] = 0; seeded.success = 0x55aa;
        slots.restoreForFixture(seeded, {});
        std::vector<uint8_t> output{'A','L','I','S','v','1',0,0};
        size_t cases = 0;
        const auto run = [&](uint8_t op, uint8_t player, uint16_t value, uint8_t cached) {
            auto initial = slots.state();
            for (size_t i = 0; i < 16; ++i)
                initial.links[0][i] = static_cast<uint8_t>(0x35 + i * 17 + cases * 7);
            initial.links[0][15] = 3;
            if (op == 2) initial.links[0][player - 1] = static_cast<uint8_t>(value);
            if (op == 4) initial.links[0][player + 1] = cached;
            if (op == 8) word(initial, 4, value);
            if (op >= 11) initial.links[0][14] = static_cast<uint8_t>(value);
            slots.restoreForFixture(initial, {});
            auto expected = initial;
            switch (op) {
            case 1:
                slots.setPlayerReserve(0, 2); slots.setPlayerReserve(1, 2);
                expected.links[0][0] = expected.links[0][1] = 2;
                break;
            case 2:
                slots.setPlayerReserve(player - 1, static_cast<uint8_t>(value - 1));
                expected.links[0][player - 1] = static_cast<uint8_t>(value - 1);
                break;
            case 3:
                slots.hudEnergyCache(player - 1) = 255;
                expected.links[0][player + 1] = 255;
                break;
            case 4:
                if (cached != value) {
                    slots.hudEnergyCache(player - 1) = static_cast<uint8_t>(value);
                    expected.links[0][player + 1] = static_cast<uint8_t>(value);
                }
                break;
            case 5: slots.setSavedViewportColumns(40); word(expected, 4, 40); break;
            case 6: case 7: slots.setSavedViewportColumns(value); word(expected, 4, value); break;
            case 8:
                for (size_t index = 0; index < 2; ++index) {
                    const auto destination = static_cast<uint16_t>(1444 - value * 4);
                    slots.setViewportDestination(index, destination);
                    word(expected, 6 + index * 2, destination);
                }
                break;
            case 9:
                slots.setViewportDestination(0, 1284); slots.setViewportDestination(1, 1444);
                word(expected, 6, 1284); word(expected, 8, 1444);
                break;
            case 10: slots.resetHudDestinations(); word(expected, 12, 180); word(expected, 10, 0); break;
            case 11: case 13: slots.setSpriteBankTag(1); expected.links[0][14] = 1; break;
            case 12: slots.setSpriteBankTag(2); expected.links[0][14] = 2; break;
            default: throw std::runtime_error("invalid alias operation");
            }
            require(equal(slots.state(), expected), "alias write changed another physical field");
            output.insert(output.end(), {op, player, static_cast<uint8_t>(value), static_cast<uint8_t>(value >> 8), cached});
            output.insert(output.end(), initial.links[0].begin(), initial.links[0].end());
            output.insert(output.end(), slots.state().links[0].begin(), slots.state().links[0].end());
            ++cases;
        };
        run(1, 0, 0, 0);
        for (uint8_t player : {uint8_t{1}, uint8_t{2}}) for (int value = 0; value < 256; ++value)
            run(2, player, static_cast<uint16_t>(value), 0);
        for (uint8_t player : {uint8_t{1}, uint8_t{2}}) run(3, player, 0, 0);
        for (uint8_t player : {uint8_t{1}, uint8_t{2}}) for (int cached = 0; cached < 256; ++cached)
            for (uint16_t value : {uint16_t{0},uint16_t{1},uint16_t{7},uint16_t{100},uint16_t{101},
                    uint16_t{200},uint16_t{255},uint16_t{256},uint16_t{257},uint16_t{65535}})
                run(4, player, value, static_cast<uint8_t>(cached));
        run(5, 0, 0, 0);
        for (uint8_t op : {uint8_t{6},uint8_t{7},uint8_t{8}})
            for (uint16_t value = 21; value <= 40; ++value) run(op, 0, value, 0);
        run(9, 0, 0, 0); run(10, 0, 0, 0);
        for (uint8_t op : {uint8_t{11},uint8_t{12},uint8_t{13}}) for (int value = 0; value < 256; ++value)
            run(op, 0, static_cast<uint16_t>(value), 0);
        require(cases == 6466 && output.size() == 8 + cases * 37, "alias coverage changed");
        for (size_t index : {size_t{2},size_t{255}}) {
            const auto before = slots.state();
            unsigned rejected = 0;
            try { slots.setPlayerReserve(index, 1); } catch (const std::out_of_range&) { ++rejected; }
            try { slots.hudEnergyCache(index) = 1; } catch (const std::out_of_range&) { ++rejected; }
            try { slots.setViewportDestination(index, 1); } catch (const std::out_of_range&) { ++rejected; }
            require(rejected == 3 && equal(before, slots.state()), "invalid alias index changed storage");
        }
        if (argc == 2) {
            std::ofstream file(argv[1], std::ios::binary);
            file.write(reinterpret_cast<const char*>(output.data()), static_cast<std::streamsize>(output.size()));
            require(bool(file), "cannot write alias output stream");
        }
        std::cout << "actor_alias_storage=ok cases=6466 bounds=6 full_state_preserved=1 whole_game_claim=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "actor_alias_storage=failed " << error.what() << '\n';
        return 1;
    }
}
