#include "gameplay/actor_slots.hpp"

#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

using lezac::gameplay::ActorAnimation;
using lezac::gameplay::ActorSlots;
using lezac::gameplay::Player;

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
void word(auto& raw, size_t at, uint16_t value) {
    raw[at] = static_cast<uint8_t>(value);
    raw[at + 1] = static_cast<uint8_t>(value >> 8);
}
bool equal(const ActorSlots::State& a, const ActorSlots::State& b) {
    return a.player1 == b.player1 && a.actors == b.actors && a.visuals == b.visuals &&
        a.links == b.links && a.count == b.count && a.visualCount == b.visualCount && a.success == b.success;
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 1 || argc == 2, "invalid player record stream arguments");
        ActorSlots slots;
        auto base = slots.state();
        const auto fill = [](auto& rows) {
            for (size_t row = 0; row < rows.size(); ++row)
                for (size_t at = 0; at < rows[row].size(); ++at)
                    rows[row][at] = static_cast<uint8_t>(0x73 + row * 31 + at * 17);
        };
        fill(base.actors); fill(base.visuals); fill(base.links);
        base.links[0][15] = 0; base.success = 0x55aa;
        std::vector<uint8_t> stream{'P','R','E','C','v','1',0,0};
        size_t cases = 0;
        const auto run = [&](uint8_t op, uint8_t index, uint8_t value) {
            auto initial = base;
            auto record = [&](auto& state, size_t player) -> auto& {
                return player == 0 ? state.player1 : state.actors[0];
            };
            for (size_t player = 0; player < 2; ++player) {
                auto& raw = record(initial, player);
                for (size_t at = 0; at < raw.size(); ++at)
                    raw[at] = static_cast<uint8_t>(0x35 + at * 17 + value * 7 + player * 31);
                raw[1] = static_cast<uint8_t>(player);
            }
            if (op == 3) {
                record(initial, index)[21] = 2;
                word(record(initial, index), 16, static_cast<uint16_t>(value * 257));
            }
            slots.restoreForFixture(initial, {});
            auto expected = initial;
            auto& raw = record(expected, index);
            const auto animation = [&](size_t player, const ActorAnimation& a) {
                const auto bytes = a.packed();
                std::copy(bytes.begin(), bytes.end(), record(expected, player).begin() + 22);
            };
            switch (op) {
            case 0: {
                constexpr ActorSlots::Descriptor descriptor{2, 16, 0x34, 0x12};
                slots.resetForLevel(descriptor);
                for (size_t player = 0; player < 2; ++player) {
                    auto& reset = record(expected, player);
                    reset[0] = reset[20] = 0;
                    reset[1] = reset[21] = static_cast<uint8_t>(player);
                    std::fill(reset.begin() + 6, reset.begin() + 16, uint8_t{0});
                    animation(player, ActorAnimation::initialize(player == 0 ? 2 : 21, player == 0 ? 9 : 28, 1, 1));
                    std::copy(descriptor.begin(), descriptor.end(), expected.visuals[player].begin() + 4);
                }
                break;
            }
            case 1: {
                Player player;
                player.vx8 = static_cast<int16_t>(value * 257);
                player.vy8 = static_cast<int16_t>(-value * 129);
                player.fracX = value; player.fracY = static_cast<uint8_t>(255 - value);
                slots.writePlayerMotion(index, player);
                word(raw, 10, value); word(raw, 12, static_cast<uint16_t>(255 - value));
                word(raw, 6, static_cast<uint16_t>(player.vx8)); word(raw, 8, static_cast<uint16_t>(player.vy8));
                break;
            }
            case 2:
                slots.setPlayerAnimation(index, ActorAnimation::initialize(74, 79, 3, 1));
                slots.setPlayerBehavior(index, 2); slots.setPlayerCountdown(index, 60);
                slots.setPlayerHealth(index, 100);
                animation(index, ActorAnimation::initialize(74, 79, 3, 1));
                raw[21] = 2; word(raw, 16, 60); raw[36] = 100;
                break;
            case 3:
                slots.setPlayerCountdown(index, static_cast<uint16_t>(value * 257 - 1));
                word(raw, 16, static_cast<uint16_t>(value * 257 - 1));
                break;
            case 4:
                slots.setPlayerBehavior(index, index); slots.setPlayerHealth(index, 100);
                raw[21] = index; raw[36] = 100;
                break;
            default: throw std::runtime_error("invalid player record operation");
            }
            require(equal(slots.state(), expected), "player record writer changed unrelated storage");
            stream.insert(stream.end(), {op, index, value});
            for (const auto* state : std::array<const ActorSlots::State*, 2>{&initial, &slots.state()}) {
                stream.insert(stream.end(), state->player1.begin(), state->player1.end());
                stream.insert(stream.end(), state->actors[0].begin(), state->actors[0].end());
            }
            ++cases;
        };
        for (int value = 0; value < 256; ++value) run(0, 0, static_cast<uint8_t>(value));
        for (uint8_t op = 1; op <= 4; ++op) for (uint8_t index = 0; index < 2; ++index)
            for (int value = 0; value < 256; ++value) run(op, index, static_cast<uint8_t>(value));
        size_t bounds = 0;
        const auto before = slots.state();
        for (int op = 0; op < 9; ++op) {
            try {
                switch (op) {
                case 0: (void)slots.playerRecord(2); break;
                case 1: slots.setPlayerHealth(2, 19); break;
                case 2: slots.setPlayerIdle(2, 19); break;
                case 3: slots.setPlayerDropTicks(2, 19); break;
                case 4: slots.setPlayerCountdown(2, 19); break;
                case 5: slots.setPlayerBehavior(2, 19); break;
                case 6: slots.setPlayerAnimation(2, {}); break;
                case 7: slots.setPlayerAnimation(2, {}, true); break;
                case 8: slots.writePlayerMotion(2, {}); break;
                }
                throw std::runtime_error("invalid player index accepted");
            } catch (const std::out_of_range&) { ++bounds; }
            require(equal(slots.state(), before), "invalid player index changed storage");
        }
        require(cases == 2304 && bounds == 9 && stream.size() == 357128, "player record coverage differs");
        if (argc == 2) {
            std::ofstream output(argv[1], std::ios::binary);
            output.exceptions(std::ios::failbit | std::ios::badbit);
            output.write(reinterpret_cast<const char*>(stream.data()), static_cast<std::streamsize>(stream.size()));
        }
        std::cout << "player_record_storage=ok cases=2304 bounds=9 full_state_preserved=1 whole_game_claim=0\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
