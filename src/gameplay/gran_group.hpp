#pragma once

#include "gameplay/actor_storage.hpp"
#include "resources/binary.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <stdexcept>
#include <vector>

namespace lezac::gameplay {

// The 08A5 loader copies actor records, then allocates visuals in file order.
// Actor visual indexes are a permutation, not allocation/actor order.
class GranGroup {
public:
    explicit GranGroup(const std::vector<uint8_t>& bytes) {
        size_t at = 0;
        actors_ = resources::getFixedRecords<38>(bytes,at);
        if (actors_.empty()) throw std::invalid_argument("Empty GRAN actor group");
        sprites_ = resources::getBytes(bytes,at,actors_.size());
        for (size_t i = 0; i < actors_.size(); ++i) {
            const auto x = resources::getU16(bytes,at), y = resources::getU16(bytes,at);
            offsets_.push_back({x,y});
        }
        links_ = resources::getFixedRecords<16>(bytes,at);
        if (at != bytes.size()) throw std::invalid_argument("Trailing GRAN group data");
        std::vector<bool> seen(actors_.size());
        for (const auto& actor : actors_) {
            if (actor[1] >= actors_.size() || seen[actor[1]])
                throw std::invalid_argument("GRAN visual permutation differs");
            seen[actor[1]] = true;
        }
    }
    size_t actorCount() const noexcept { return actors_.size(); }
    size_t linkCount() const noexcept { return links_.size(); }
    uint8_t sprite(size_t visual) const { return sprites_.at(visual); }

    template<class DescriptorLookup,class AnimationRange>
    void append(ActorStorage::State& state,int16_t x,int16_t y,
                const DescriptorLookup& descriptor,const AnimationRange& range) const {
        const size_t oldActors = state.count, visualBase = state.visualCount;
        const size_t oldLinks = state.links[0][15];
        if (visualBase != oldActors+2 || oldActors+actors_.size() > ActorStorage::capacity ||
                oldLinks+links_.size() > 7)
            throw std::invalid_argument("GRAN group exceeds physical storage");
        auto next = state;
        const auto word = [](auto& bytes,size_t at,uint16_t value) {
            bytes[at] = static_cast<uint8_t>(value); bytes[at+1] = static_cast<uint8_t>(value>>8);
        };
        for (size_t i = 0; i < actors_.size(); ++i) {
            auto actor = actors_[i];
            const auto first = static_cast<uint16_t>(oldActors+1);
            if (i == 0) word(actor,18,first);
            else {
                // 0A6F..0ABE rebases words conditionally, including carries.
                auto serials = resources::recLe16(actor,14);
                if ((serials & 255u) != 0) {
                    serials = static_cast<uint16_t>(serials+oldLinks);
                    word(actor,14,serials);
                    if ((serials >> 8) != 0) {
                        word(actor,14,static_cast<uint16_t>(serials+(oldLinks<<8)));
                        const auto third = resources::recLe16(actor,16);
                        if ((third & 255u) != 0) word(actor,16,static_cast<uint16_t>(third+oldLinks));
                    }
                }
                actor[37] = static_cast<uint8_t>(first);
                actor[2] = static_cast<uint8_t>(actor[2]+visualBase);
            }
            actor[1] = static_cast<uint8_t>(actor[1]+visualBase);
            if (actor[3] != 0) {
                const auto limits = range(actor[3]);
                const auto animation = ActorAnimation::initialize(limits[0],limits[1],actor[26],1).packed();
                std::copy(animation.begin(),animation.end(),actor.begin()+22);
            }
            next.actors[oldActors+i+1] = actor;
        }
        for (size_t i = 0; i < actors_.size(); ++i) {
            auto& visual = next.visuals[visualBase+i];
            word(visual,0,static_cast<uint16_t>(static_cast<uint16_t>(x)+offsets_[i][0]));
            word(visual,2,static_cast<uint16_t>(static_cast<uint16_t>(y)+offsets_[i][1]));
            const auto image = descriptor(sprites_[i]);
            std::copy(image.begin(),image.end(),visual.begin()+4);
        }
        for (size_t i = 0; i < links_.size(); ++i) {
            auto link = links_[i];
            link[0] = static_cast<uint8_t>(link[0]+visualBase);
            link[1] = static_cast<uint8_t>(link[1]+visualBase);
            next.links[oldLinks+i+1] = link;
        }
        next.count = static_cast<uint8_t>(oldActors+actors_.size());
        next.visualCount = static_cast<uint8_t>(visualBase+actors_.size());
        next.links[0][15] = static_cast<uint8_t>(oldLinks+links_.size());
        state = next;
    }

private:
    std::vector<ActorStorage::Actor> actors_;
    std::vector<uint8_t> sprites_;
    std::vector<std::array<uint16_t,2>> offsets_;
    std::vector<ActorStorage::Link> links_;
};

} // namespace lezac::gameplay
