#include "diagnostics/transient_storage_fixture.hpp"

#include <fstream>
#include <iostream>
#include <vector>

using namespace lezac::gameplay;
namespace fixture = lezac::diagnostics::transient_storage;

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("expected transient request and output paths");
        std::ifstream input(argv[1], std::ios::binary);
        std::ofstream output(argv[2], std::ios::binary);
        if (!input || !output) throw std::runtime_error("cannot open transient protocol files");
        const fixture::Header header(input);
        ActorSlots slots;
        std::vector<TransientActor> actors;
        uint64_t nextOrder = 1;
        fixture::writeHeader(output, header.operations);
        for (uint32_t operation = 0; operation < header.operations; ++operation) {
            const auto command = fixture::byte(input);
            if (command == 'S') {
                const auto state = fixture::readSeed(input);
                std::array<uint64_t, ActorStorage::capacity + 1> orders{};
                actors.clear();
                for (size_t slot = 1; slot <= state.count; ++slot) orders[slot] = nextOrder++;
                slots.restoreForFixture(state, orders);
                for (size_t slot = 1; slot <= state.count; ++slot) actors.push_back(fixture::decode(slots, orders[slot]));
            } else if (command == 'U') {
                const uint16_t tick = fixture::word(input);
                for (size_t index = 0; index < actors.size();) {
                    auto& actor = actors[index];
                    const bool advanced = advanceTransientActor(actor, tick);
                    slots.writeTransient(actor.actorOrder, actor, advanced,
                        advanced ? header.descriptor(static_cast<uint16_t>(actor.spriteIndex) + 1) : ActorSlots::Descriptor{});
                    if (actor.timer == 0) {
                        slots.retire(actor.actorOrder);
                        actors.erase(actors.begin() + static_cast<std::ptrdiff_t>(index));
                    } else ++index;
                }
            } else if (command == 'C') {
                const fixture::Constructor constructor(input);
                const auto row = slots.count() == ActorStorage::capacity ? ActorSlots::Descriptor{}
                                                                        : header.descriptor(constructor.input.sprite);
                if (slots.append(nextOrder, constructor.input, row)) {
                    auto actor = fixture::decode(slots, nextOrder++);
                    actor.spriteIndex = static_cast<uint8_t>(constructor.input.sprite - 1);
                    actor.animation = constructor.animation;
                    slots.writeTransient(actor.actorOrder, actor, false, {});
                    actors.push_back(actor);
                }
            } else throw std::runtime_error("unknown transient command");
            fixture::writeState(output, slots.state());
        }
        fixture::finish(input, output);
        std::cout << "transient_storage_probe=ok operations=" << header.operations << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
