#pragma once

#include "diagnostics/transient_storage_fixture.hpp"

namespace lezac::diagnostics::marker_storage {

using transient_storage::byte;
using transient_storage::word;
using transient_storage::readSeed;
using transient_storage::writeState;
using transient_storage::finish;

struct Header {
    uint32_t operations;
    std::array<gameplay::ActorSlots::Descriptor, 92> descriptors{};

    explicit Header(std::istream& input) {
        std::string magic(8, '\0');
        input.read(magic.data(), 8);
        if (magic != "LZMW0001") throw std::runtime_error("invalid marker request magic");
        const uint32_t low = word(input);
        operations = low | (static_cast<uint32_t>(word(input)) << 16);
        if (operations == 0 || operations > 100000) throw std::runtime_error("invalid operation count");
        transient_storage::readRows(input, descriptors);
    }

    gameplay::ActorSlots::Descriptor descriptor(uint16_t sprite) const {
        if (sprite >= descriptors.size()) throw std::runtime_error("marker sprite outside descriptor bank");
        return descriptors[sprite];
    }
};

inline void writeHeader(std::ostream& output, uint32_t operations) {
    output.write("LZMO0001", 8);
    transient_storage::write(output, operations, 4);
}

inline gameplay::LaunchPadMarker decode(const gameplay::ActorSlots& slots, uint64_t order) {
    const auto actor = transient_storage::decode(slots, order);
    if (actor.kind != gameplay::kLaunchPadMarkerKind) throw std::runtime_error("non-marker fixture actor");
    gameplay::LaunchPadMarker marker;
    marker.actorOrder = order;
    marker.x = actor.x; marker.y = actor.y;
    marker.velocityX8 = actor.vx8; marker.velocityY8 = actor.vy8;
    marker.fracX = actor.fracX; marker.fracY = actor.fracY;
    marker.kind = actor.kind; marker.timer = actor.timer;
    marker.animation = actor.animation; marker.frame = actor.animation.current;
    return marker;
}

struct Position {
    int16_t x, y;
    explicit Position(std::istream& input)
        : x(static_cast<int16_t>(word(input))), y(static_cast<int16_t>(word(input))) {}
};

} // namespace lezac::diagnostics::marker_storage
