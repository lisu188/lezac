#include "diagnostics/marker_storage_fixture.hpp"

#include <fstream>
#include <iostream>
#include <vector>

using namespace lezac::gameplay;
namespace fixture = lezac::diagnostics::marker_storage;

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("expected marker request and output paths");
        std::ifstream input(argv[1], std::ios::binary);
        std::ofstream output(argv[2], std::ios::binary);
        if (!input || !output) throw std::runtime_error("cannot open marker protocol files");
        const fixture::Header header(input);
        ActorSlots slots;
        std::vector<LaunchPadMarker> markers;
        uint64_t nextOrder = 1;
        fixture::writeHeader(output, header.operations);
        for (uint32_t operation = 0; operation < header.operations; ++operation) {
            const auto command = fixture::byte(input);
            if (command == 'S') {
                const auto state = fixture::readSeed(input);
                std::array<uint64_t, ActorStorage::capacity + 1> orders{};
                markers.clear();
                for (size_t slot = 1; slot <= state.count; ++slot) orders[slot] = nextOrder++;
                slots.restoreForFixture(state, orders);
                for (size_t slot = 1; slot <= state.count; ++slot) markers.push_back(fixture::decode(slots, orders[slot]));
            } else if (command == 'U') {
                const uint16_t tick = fixture::word(input);
                for (size_t index = 0; index < markers.size();) {
                    auto& marker = markers[index];
                    const bool advanced = advanceLaunchPadMarker(marker, slots.animationBackup(marker.actorOrder), tick);
                    slots.writeMarker(marker.actorOrder, marker, advanced,
                        advanced ? header.descriptor(marker.frame) : ActorSlots::Descriptor{});
                    if (marker.timer == 0) {
                        slots.retire(marker.actorOrder);
                        markers.erase(markers.begin() + static_cast<std::ptrdiff_t>(index));
                    } else ++index;
                }
            } else if (command == 'L' || command == 'P') {
                const fixture::Position position(input);
                LaunchPadMarker marker;
                marker.x = static_cast<int16_t>(position.x + (command == 'L' ? 4 : 0));
                marker.y = static_cast<int16_t>(position.y + (command == 'L' ? 13 : 0));
                if (command == 'P') {
                    marker.velocityY8 = 0;
                    marker.timer = kPortalMarkerTimer;
                    marker.frame = kPortalMarkerFirstFrame;
                    marker.animation = ActorAnimation::initialize(kPortalMarkerFirstFrame, kPortalMarkerLastFrame, kPortalMarkerDelay, 1);
                }
                const ActorSlots::Construction construction{marker.kind, marker.timer, marker.mode, marker.frame,
                    marker.velocityX8, marker.velocityY8, static_cast<int16_t>(marker.x), static_cast<int16_t>(marker.y)};
                const auto row = slots.count() == ActorStorage::capacity ? ActorSlots::Descriptor{} : header.descriptor(marker.frame);
                if (slots.append(nextOrder, construction, row)) {
                    marker.actorOrder = nextOrder++;
                    if (command == 'P') slots.setActiveAnimation(marker.actorOrder, marker.animation);
                    else {
                        slots.disableAnimation(marker.actorOrder);
                        marker.animation = slots.activeAnimation(marker.actorOrder);
                    }
                    markers.push_back(marker);
                }
            } else throw std::runtime_error("unknown marker command");
            fixture::writeState(output, slots.state());
        }
        fixture::finish(input, output);
        std::cout << "marker_storage_probe=ok operations=" << header.operations << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
