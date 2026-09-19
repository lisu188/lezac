#include "gameplay/actor_system.hpp"
#include "core/fixed_point.hpp"
#include "core/progress.hpp"
#include <cmath>

namespace lezac::gameplay {
using namespace lezac::core;
namespace {
int16_t clampI16(int value) { return static_cast<int16_t>(std::clamp(value, -32768, 32767)); }
void integrateAxis8_8(int& pos, uint8_t& frac, int16_t velocity) {
    core::Fixed8_8Axis axis{pos, frac};
    core::integrateFixed8_8(axis, velocity);
    pos = axis.position; frac = axis.fraction;
}
}

std::vector<SharedActorEntry> ActorSystem::sharedActorEntries() const {
        std::vector<SharedActorEntry> result;
        for (size_t i = 0; i < state_.transientActors_.size(); ++i) result.push_back({state_.transientActors_[i].actorOrder, SharedActorKind::Effect, i});
        for (size_t i = 0; i < state_.launchPadMarkers_.size(); ++i) result.push_back({state_.launchPadMarkers_[i].actorOrder, SharedActorKind::Marker, i});
        for (size_t i = 0; i < state_.bombs_.size(); ++i) result.push_back({state_.bombs_[i].actorOrder, SharedActorKind::Bomb, i});
        for (size_t i = 0; i < state_.monsters_.size(); ++i) if (state_.monsters_[i].alive) result.push_back({state_.monsters_[i].actorOrder, SharedActorKind::Monster, i});
        for (size_t i = 0; i < state_.bonusDrops_.size(); ++i) if (!state_.bonusDrops_[i].collected) result.push_back({state_.bonusDrops_[i].actorOrder, SharedActorKind::Reward, i});
        std::stable_sort(result.begin(), result.end(), [](const SharedActorEntry& a, const SharedActorEntry& b) { return a.order < b.order; });
        return result;
    }

uint64_t ActorSystem::sharedActorVisualKey(const SharedActorEntry& entry) const {
        if (entry.kind == SharedActorKind::Monster && state_.monsters_[entry.index].bossVisualOrder)
            return state_.monsters_[entry.index].bossVisualOrder;
        if (entry.kind == SharedActorKind::Effect && state_.transientActors_[entry.index].bossVisualOrder)
            return state_.transientActors_[entry.index].bossVisualOrder;
        return entry.order;
    }

void ActorSystem::adoptUnorderedActors() {
        // Directly seeded diagnostics predate shared ordering. Real producers
        // claim an order at construction; explicit original replays seed it.
        const auto entries = sharedActorEntries();
        for (const auto& entry : entries) state_.nextActorOrder_ = std::max(state_.nextActorOrder_, entry.order + 1);
        for (const auto& entry : entries) {
            if (entry.order) continue;
            const uint64_t order = state_.nextActorOrder_++;
            switch (entry.kind) {
                case SharedActorKind::Effect: state_.transientActors_[entry.index].actorOrder = order; break;
                case SharedActorKind::Marker: state_.launchPadMarkers_[entry.index].actorOrder = order; break;
                case SharedActorKind::Bomb: state_.bombs_[entry.index].actorOrder = order; break;
                case SharedActorKind::Monster: state_.monsters_[entry.index].actorOrder = order; break;
                case SharedActorKind::Reward: state_.bonusDrops_[entry.index].actorOrder = order; break;
            }
        }
    }

uint64_t ActorSystem::claimActorOrder() {
        adoptUnorderedActors();
        return state_.nextActorOrder_++;
    }

size_t ActorSystem::sharedActorCount() const {
        const auto liveMonsters = std::count_if(state_.monsters_.begin(), state_.monsters_.end(),
            [](const ActiveMonster& monster) { return monster.alive; });
        return static_cast<size_t>(liveMonsters) + state_.bombs_.size() + state_.bonusDrops_.size() +
               state_.launchPadMarkers_.size() + state_.transientActors_.size();
    }

size_t ActorSystem::pickupActorCount() const {
        return static_cast<size_t>(std::count_if(state_.transientActors_.begin(), state_.transientActors_.end(),
            [](const TransientActor& actor) { return actor.kind == 0x0a; }));
    }
}
