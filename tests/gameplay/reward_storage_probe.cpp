#include "diagnostics/reward_storage_fixture.hpp"
#include "core/fixed_point.hpp"
#include "core/random.hpp"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <vector>

using namespace lezac::gameplay;
namespace fixture = lezac::diagnostics::reward_storage;

struct ProbeActor {
    BonusDrop drop;
    TransientActor effect;
    bool converted = false;
};

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("expected reward request and output paths");
        std::ifstream input(argv[1], std::ios::binary);
        std::ofstream output(argv[2], std::ios::binary);
        if (!input || !output) throw std::runtime_error("cannot open reward protocol files");
        const fixture::Header header(input);
        ActorSlots slots;
        std::vector<ProbeActor> actors;
        uint64_t nextOrder = 1;
        bool seeded = false;
        lezac::core::TurboRandom random;
        std::array<uint8_t, 2> pending{}, hits{}, alive{};
        std::array<Player, 2> players{};
        auto touches = [](const Player& player, int x, int y) {
            auto axis = [](int own, int other) {
                const uint16_t delta = static_cast<uint16_t>(own - other);
                const uint16_t magnitude = delta & 0x8000 ? static_cast<uint16_t>(0u - delta) : delta;
                return magnitude == 0x8000 || magnitude < 10;
            };
            return axis(static_cast<int>(player.x), x) && axis(static_cast<int>(player.y), y);
        };
        auto motion = [&](int& x, int& y, int16_t& vx, int16_t& vy, uint8_t& fracX, uint8_t& fracY) {
            const int column = (x + 4) >> 3, row = y >> 3;
            auto solid = [&](int c, int r, bool bottom) {
                const uint8_t tile = c < 0 || c >= 60 || r < 0 || r >= 33 ? 1 : header.tiles[r * 60 + c];
                return tile >= 1 && tile <= (bottom ? 0x52 : 0x4c);
            };
            const bool top = solid(column, row - 1, false) || solid(column + 1, row - 1, false);
            const bool bottom = solid(column, row + 2, true) || solid(column + 1, row + 2, true);
            const bool left = solid(column - 1, row, false) || solid(column - 1, row + 1, false);
            const bool right = solid(column + 2, row, false) || solid(column + 2, row + 1, false);
            if (!bottom || vy < 0) vy = std::min<int16_t>(0x07ff, static_cast<int16_t>(vy + 64));
            else if (vy > 0) { vy = 0; y &= ~7; }
            if (bottom) {
                const int16_t magnitude = static_cast<int16_t>(vx < 0 ? -vx : vx);
                vx = static_cast<int16_t>(magnitude < 43 ? 0 : vx + (vx < 0 ? 42 : -42));
            }
            if (top && vy < 0) vy = 1;
            if (left && right) vx = 0;
            else if ((left && vx < 0) || (right && vx > 0)) {
                vx = static_cast<int16_t>(static_cast<int16_t>(-vx) / 2);
                x += vx < 0 ? -1 : 1;
            }
            lezac::core::Fixed8_8Axis vertical{y, fracY}, horizontal{x, fracX};
            lezac::core::integrateFixed8_8(vertical, vy);
            lezac::core::integrateFixed8_8(horizontal, vx);
            y = static_cast<int16_t>(vertical.position); fracY = vertical.fraction;
            x = static_cast<int16_t>(horizontal.position); fracX = horizontal.fraction;
        };
        fixture::writeHeader(output, header.operations);
        for (uint32_t operation = 0; operation < header.operations; ++operation) {
            const auto command = fixture::byte(input);
            if (command == 'S') {
                const fixture::Seed seed(input);
                std::array<uint64_t, ActorStorage::capacity + 1> orders{};
                actors.clear();
                for (size_t slot = 1; slot <= seed.storage.count; ++slot) orders[slot] = nextOrder++;
                slots.restoreForFixture(seed.storage, orders);
                for (size_t slot = 1; slot <= seed.storage.count; ++slot) actors.push_back({fixture::decode(slots, orders[slot]), {}, false});
                random.setSeed(seed.rng); pending = seed.pending; hits = seed.hits; alive = seed.alive;
                for (size_t player = 0; player < players.size(); ++player) {
                    players[player].x = fixture::signedWord(seed.storage.visuals[player], 0);
                    players[player].y = fixture::signedWord(seed.storage.visuals[player], 2);
                }
                seeded = true;
            } else if (command == 'U') {
                if (!seeded) throw std::runtime_error("reward update before seed");
                const uint16_t tick = fixture::word(input);
                for (size_t index = 0; index < actors.size();) {
                    auto& actor = actors[index];
                    if (actor.converted) {
                        auto& effect = actor.effect;
                        const bool advanced = advanceTransientActor(effect, tick);
                        slots.writeTransient(effect.actorOrder, effect, advanced,
                            advanced ? header.descriptor(static_cast<uint16_t>(effect.spriteIndex) + 1) : ActorSlots::Descriptor{});
                        if (!effect.timer) {
                            slots.retire(effect.actorOrder);
                            actors.erase(actors.begin() + static_cast<std::ptrdiff_t>(index));
                            continue;
                        }
                    } else {
                        auto& drop = actor.drop;
                        const int x = static_cast<int16_t>(drop.x);
                        const int y = static_cast<int16_t>(static_cast<int>(drop.y) - static_cast<int8_t>(drop.hotspotY));
                        const std::array<bool, 2> touching{{alive[0] == 1 && touches(players[0], x, y),
                                                         alive[1] == 1 && touches(players[1], x, y)}};
                        const auto step = advanceBonusDrop(drop, slots.animationBackup(drop.actorOrder), tick,
                            touching, pending, motion, [&] { return random.range(1, 3); },
                            [&](uint8_t sprite) { return static_cast<uint8_t>(16 - header.descriptor(static_cast<uint16_t>(sprite) + 1)[1]); });
                        if (step.converted) {
                            slots.setSpriteDescriptor(drop.actorOrder, header.descriptor(static_cast<uint16_t>(step.conversion.spriteIndex) + 1));
                            slots.writeTransient(drop.actorOrder, step.conversion, false, {});
                            actor.effect = step.conversion;
                            actor.converted = true;
                        } else {
                            slots.writeReward(drop.actorOrder, drop, step.animationAdvanced,
                                step.animationAdvanced ? header.descriptor(drop.animation.current) : ActorSlots::Descriptor{});
                        }
                    }
                    ++index;
                }
            } else throw std::runtime_error("unknown reward command");
            fixture::writeState(output, slots.state(), random.seed(), pending, hits, alive);
        }
        fixture::finish(input, output);
        std::cout << "reward_storage_probe=ok operations=" << header.operations << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
