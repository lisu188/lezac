#include "diagnostics/corpse_storage_fixture.hpp"
#include "core/fixed_point.hpp"
#include "core/random.hpp"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <vector>

using namespace lezac::gameplay;
namespace fixture = lezac::diagnostics::corpse_storage;

struct ProbeActor {
    enum class Kind { Corpse, Reward, Effect } kind = Kind::Effect;
    ActiveMonster corpse;
    BonusDrop reward;
    TransientActor effect;
};

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("expected corpse request and output paths");
        std::ifstream input(argv[1], std::ios::binary);
        std::ofstream output(argv[2], std::ios::binary);
        if (!input || !output) throw std::runtime_error("cannot open corpse protocol files");
        const fixture::Header header(input);
        ActorSlots slots;
        std::vector<ProbeActor> actors;
        actors.reserve(30);
        uint64_t nextOrder = 1;
        bool seeded = false;
        lezac::core::TurboRandom random;
        lezac::resources::SoundBank bank;
        lezac::sound::SoundEngine sound(bank);
        uint8_t roll = 0;
        std::array<uint8_t, 2> pending{}, hits{}, alive{};
        auto hotspot = [&](uint8_t sprite) { return static_cast<uint8_t>(16 - header.descriptor(sprite)[1]); };
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
                for (size_t slot = 1; slot <= seed.storage.count; ++slot) {
                    ProbeActor actor;
                    if (slots.actor(orders[slot])[0] == 0x0c) {
                        actor.kind = ProbeActor::Kind::Corpse;
                        actor.corpse = fixture::decode(slots, orders[slot]);
                    } else actor.effect = lezac::diagnostics::transient_storage::decode(slots, orders[slot]);
                    actors.push_back(actor);
                }
                random.setSeed(seed.rng); pending = seed.pending; hits = seed.hits; alive = seed.alive;
                roll = seed.roll;
                sound.restoreLatchForFixture(seed.latch);
                sound.restoreRequestForFixture(seed.requestCursor, seed.requestPriority);
                seeded = true;
            } else if (command == 'U') {
                if (!seeded) throw std::runtime_error("corpse update before seed");
                const uint16_t tick = fixture::word(input);
                for (size_t index = 0; index < actors.size();) {
                    auto& actor = actors[index];
                    if (actor.kind == ProbeActor::Kind::Corpse) {
                        auto& corpse = actor.corpse;
                        const bool advanced = advanceMonsterAnimation(corpse);
                        uint8_t timer = slots.actor(corpse.actorOrder)[2];
                        const bool expired = advanceCorpseMotion(corpse, timer, tick, motion);
                        slots.writeCorpse(corpse.actorOrder, corpse, timer, advanced,
                            advanced ? header.descriptor(corpse.animCursor + 1) : ActorSlots::Descriptor{});
                        if (expired) {
                            roll = static_cast<uint8_t>(random.range(0, 100));
                            sound.requestSoundCursor(static_cast<uint16_t>(0xea74 + random.range(0, 20)), 4);
                            const auto conversion = convertCorpseReward(corpse, roll, hotspot);
                            slots.convertCorpse(corpse.actorOrder, conversion,
                                header.descriptor(conversion.hasReward ? static_cast<uint8_t>(conversion.reward.type) + 62 : 69));
                            actor.kind = conversion.hasReward ? ProbeActor::Kind::Reward : ProbeActor::Kind::Effect;
                            actor.reward = conversion.reward;
                            actor.effect = conversion.fade;
                            const int x = corpse.x, y = static_cast<int16_t>(corpse.y + corpse.hotspotY);
                            for (int particle = 0; particle < 2; ++particle) {
                                const auto vx = static_cast<int16_t>(random.range(0, 600) - 300);
                                const auto vy = static_cast<int16_t>(random.range(0, 600) - 300);
                                if (slots.append(nextOrder, {0x0b, 15, 5, 13, 0, vy,
                                        static_cast<int16_t>(x), static_cast<int16_t>(y)}, header.descriptor(13))) {
                                    ProbeActor appended;
                                    auto& effect = appended.effect;
                                    effect.actorOrder = nextOrder++;
                                    effect.kind = 0x0b; effect.timer = 15; effect.spriteIndex = 12;
                                    effect.x = x; effect.y = y; effect.vx8 = vx; effect.vy8 = vy;
                                    effect.hotspotY = slots.actor(effect.actorOrder)[20];
                                    effect.animation = ActorAnimation::initialize(69, 79, 2, 2);
                                    effect.animationBackup = slots.animationBackup(effect.actorOrder);
                                    slots.writeTransient(effect.actorOrder, effect, false, {});
                                    actors.push_back(appended);
                                }
                            }
                        }
                    } else if (actor.kind == ProbeActor::Kind::Reward) {
                        auto& drop = actor.reward;
                        const auto step = advanceBonusDrop(drop, slots.animationBackup(drop.actorOrder), tick,
                            {{false, false}}, pending, motion, [&] { return random.range(1, 3); },
                            [&](uint8_t sprite) { return hotspot(sprite + 1); });
                        if (step.converted) {
                            slots.setSpriteDescriptor(drop.actorOrder, header.descriptor(step.conversion.spriteIndex + 1));
                            slots.writeTransient(drop.actorOrder, step.conversion, false, {});
                            actor.kind = ProbeActor::Kind::Effect;
                            actor.effect = step.conversion;
                        } else slots.writeReward(drop.actorOrder, drop, step.animationAdvanced,
                            step.animationAdvanced ? header.descriptor(drop.animation.current) : ActorSlots::Descriptor{});
                    } else {
                        auto& effect = actor.effect;
                        const bool advanced = advanceTransientActor(effect, tick);
                        slots.writeTransient(effect.actorOrder, effect, advanced,
                            advanced ? header.descriptor(effect.spriteIndex + 1) : ActorSlots::Descriptor{});
                        if (!effect.timer) {
                            slots.retire(effect.actorOrder);
                            actors.erase(actors.begin() + static_cast<std::ptrdiff_t>(index));
                            continue;
                        }
                    }
                    ++index;
                }
            } else throw std::runtime_error("unknown corpse command");
            fixture::writeState(output, slots.state(), random.seed(), pending, hits, alive, roll, sound);
        }
        fixture::finish(input, output);
        std::cout << "corpse_storage_probe=ok operations=" << header.operations << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
