#pragma once

#include "gameplay/actor_storage.hpp"
#include "gameplay/gran_group.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace lezac::gameplay {

// Bind typed gameplay identities to physical records without changing the
// verified allocator's stable compaction or untouched inactive tail bytes.
class ActorSlots {
public:
    using State = ActorStorage::State;
    using Construction = ActorStorage::Construction;
    using Descriptor = ActorStorage::Descriptor;

    size_t count() const { return storage_.state().count; }
    const State& state() const { return storage_.state(); }
    const ActorStorage::Actor& playerRecord(size_t index) const {
        if (index >= 2) throw std::out_of_range("invalid player record index");
        return index == 0 ? state().player1 : state().actors[0];
    }
    void setPlayerHealth(size_t index, uint8_t value) { storage_.player(index)[36] = value; }
    void setPlayerIdle(size_t index, uint8_t value) { storage_.player(index)[2] = value; }
    void setPlayerDropTicks(size_t index, uint16_t value) { playerWord(storage_.player(index), 14, value); }
    void setPlayerCountdown(size_t index, uint16_t value) { playerWord(storage_.player(index), 16, value); }
    void setPlayerBehavior(size_t index, uint8_t value) { storage_.player(index)[21] = value; }
    void setPlayerAnimation(size_t index, const ActorAnimation& animation, bool backup = false) {
        auto& raw = storage_.player(index);
        const auto bytes = animation.packed();
        std::copy(bytes.begin(), bytes.end(), raw.begin() + (backup ? 29 : 22));
    }
    void writePlayerMotion(size_t index, const Player& player) {
        auto& raw = storage_.player(index);
        playerWord(raw, 10, player.fracX); playerWord(raw, 12, player.fracY);
        playerWord(raw, 6, static_cast<uint16_t>(player.vx8));
        playerWord(raw, 8, static_cast<uint16_t>(player.vy8));
    }
    void setSharedResult(uint16_t value) { storage_.setSharedResult(value); }
    void setPlayer2Health(uint8_t value) { setPlayerHealth(1, value); }
    void setPlayerReserve(size_t index, uint8_t value) { storage_.setPlayerReserve(index, value); }
    uint8_t& hudEnergyCache(size_t index) { return storage_.hudEnergyCache(index); }
    void setSavedViewportColumns(uint16_t value) { storage_.setSavedViewportColumns(value); }
    void setViewportDestination(size_t index, uint16_t value) { storage_.setViewportDestination(index, value); }
    void resetHudDestinations() { storage_.resetHudDestinations(); }
    void setSpriteBankTag(uint8_t value) { storage_.setSpriteBankTag(value); }
    const ActorStorage::Actor& actor(uint64_t order) const { return state().actors[require(order)]; }
    const ActorStorage::Visual& visual(uint64_t order) const { return state().visuals[actor(order)[1]]; }

    void setPlayerPosition(size_t index, uint16_t x, uint16_t y) {
        auto& row = playerVisual(index);
        playerWord(row, 0, x); playerWord(row, 2, y);
    }

    void setPlayerY(size_t index, uint16_t y) { playerWord(playerVisual(index), 2, y); }
    void hidePlayer(size_t index) { playerWord(playerVisual(index), 0, 10000); }

    void setPlayerSpriteOffset(size_t index, const Descriptor& descriptor) {
        auto& row = playerVisual(index);
        row[6] = descriptor[2]; row[7] = descriptor[3];
    }

    void setPlayerDescriptor(size_t index, const Descriptor& descriptor) {
        setPlayerSpriteOffset(index, descriptor);
        auto& row = playerVisual(index);
        row[4] = descriptor[0]; row[5] = descriptor[1];
    }

    void reducePlayerDimensions(size_t index) {
        auto& row = playerVisual(index);
        row[4] = row[5] = 1;
    }

    size_t find(uint64_t order) const {
        if (order == 0) return 0;
        for (size_t slot = 1; slot <= count(); ++slot) {
            if (orders_[slot] == order) return slot;
        }
        return 0;
    }

    uint64_t order(size_t slot) const {
        if (slot == 0 || slot > count()) throw std::out_of_range("inactive actor identity");
        return orders_[slot];
    }

    bool append(uint64_t order, const Construction& input, const Descriptor& descriptor) {
        if (order == 0 || find(order)) throw std::invalid_argument("invalid actor allocation identity");
        const size_t slot = storage_.append(input, descriptor);
        if (slot == 0) return false;
        orders_[slot] = order;
        return true;
    }

    template<class DescriptorLookup,class AnimationRange>
    void appendGranGroup(uint64_t firstOrder,const GranGroup& group,int16_t x,int16_t y,
                         const DescriptorLookup& descriptor,const AnimationRange& range) {
        const size_t oldCount=count();
        if (!firstOrder || firstOrder > std::numeric_limits<uint64_t>::max()-group.actorCount())
            throw std::invalid_argument("Invalid GRAN identity range");
        for (size_t i=0;i<group.actorCount();++i)
            if (find(firstOrder+i)) throw std::invalid_argument("Duplicate GRAN actor identity");
        auto loaded=state();
        group.append(loaded,x,y,descriptor,range);
        storage_.restore(loaded);
        for (size_t i=0;i<group.actorCount();++i) orders_[oldCount+i+1]=firstOrder+i;
    }

    void writeLinkMotion(size_t index,uint8_t phase,int16_t x,int16_t y) {
        auto& link=storage_.link(index);
        link[6]=phase;
        const auto word=[](auto& bytes,size_t at,uint16_t value) {
            bytes[at]=static_cast<uint8_t>(value);bytes[at+1]=static_cast<uint8_t>(value>>8);
        };
        word(link,11,static_cast<uint16_t>(x));word(link,13,static_cast<uint16_t>(y));
    }

    bool retire(uint64_t order) {
        const size_t slot = find(order);
        if (slot == 0) return false;
        const size_t oldCount = count();
        storage_.retire(slot);
        for (size_t index = slot; index < oldCount; ++index) orders_[index] = orders_[index + 1];
        orders_[oldCount] = 0;
        return true;
    }

    ActorAnimation animationBackup(uint64_t order) const {
        const size_t slot = require(order);
        const auto& raw = state().actors[slot];
        return {raw[29], raw[30], raw[31], raw[32], raw[33], raw[34], static_cast<int8_t>(raw[35])};
    }

    ActorAnimation activeAnimation(uint64_t order) const {
        const auto& raw = actor(order);
        return {raw[22], raw[23], raw[24], raw[25], raw[26], raw[27], static_cast<int8_t>(raw[28])};
    }

    void disableAnimation(uint64_t order) {
        storage_.actor(require(order))[27] = 0;
    }

    void setActiveAnimation(uint64_t order, const ActorAnimation& animation) {
        auto& raw = storage_.actor(require(order));
        const auto bytes = animation.packed();
        std::copy(bytes.begin(), bytes.end(), raw.begin() + 22);
    }

    void setAnimationBackup(uint64_t order, const ActorAnimation& animation) {
        auto& raw = storage_.actor(require(order));
        const auto bytes = animation.packed();
        std::copy(bytes.begin(), bytes.end(), raw.begin() + 29);
    }

    void setTimer(uint64_t order, uint8_t timer) { storage_.actor(require(order))[2] = timer; }

    void writeBombMotion(uint64_t order, const Bomb& bomb) {
        auto& raw = storage_.actor(require(order));
        auto& row = storage_.visual(raw[1]);
        const auto word = [](auto& bytes, size_t offset, uint16_t value) {
            bytes[offset] = static_cast<uint8_t>(value);
            bytes[offset + 1] = static_cast<uint8_t>(value >> 8);
        };
        word(row, 0, static_cast<uint16_t>(bomb.pixelX)); word(row, 2, static_cast<uint16_t>(bomb.pixelY));
        word(raw, 10, bomb.fracX); word(raw, 12, bomb.fracY);
        word(raw, 6, static_cast<uint16_t>(bomb.vx8)); word(raw, 8, static_cast<uint16_t>(bomb.vy8));
    }

    void enterBombFade(uint64_t order, const TransientActor& fade, const Descriptor& descriptor) {
        auto& raw = storage_.actor(require(order));
        // 1000:7604..766A changes dispatch/visual state before particle creation.
        raw[0] = 0; raw[2] = fade.timer; raw[21] = 5;
        std::fill(raw.begin() + 6, raw.begin() + 10, uint8_t{0});
        setSpriteDescriptor(order, descriptor);
        setActiveAnimation(order, fade.animation);
    }

    void setSpriteDescriptor(uint64_t order, const Descriptor& descriptor) {
        auto& raw = storage_.actor(require(order));
        auto& row = storage_.visual(raw[1]);
        std::copy(descriptor.begin(), descriptor.end(), row.begin() + 4);
        raw[20] = static_cast<uint8_t>(16 - descriptor[1]);
    }

    void initializeSpawnedMonster(uint64_t order, const ActiveMonster& monster, uint8_t source) {
        auto& raw = storage_.actor(require(order));
        raw[3] = monster.animationSetLeft;
        raw[4] = monster.animationSetRight;
        const std::array<uint16_t, 3> parameters{monster.ai0, monster.ai1, monster.ai2};
        for (size_t index = 0; index < parameters.size(); ++index) {
            raw[14 + index * 2] = static_cast<uint8_t>(parameters[index]);
            raw[15 + index * 2] = static_cast<uint8_t>(parameters[index] >> 8);
        }
        setActiveAnimation(order, monsterAnimation(monster));
        // 1000:7B43..7C36 leaves opaque byte5 and animation backup29..35 intact.
        raw[36] = static_cast<uint8_t>(monster.hp - 1);
        raw[37] = source;
    }

    void writeMonsterAnimation(uint64_t order, const ActiveMonster& monster, bool advanced,
                               const Descriptor& descriptor) {
        setActiveAnimation(order, monsterAnimation(monster));
        if (advanced) {
            auto& row = storage_.visual(actor(order)[1]);
            row[6] = descriptor[2]; row[7] = descriptor[3];
        }
    }

    void writeMonsterMotion(uint64_t order, const ActiveMonster& monster) {
        auto& raw = storage_.actor(require(order));
        auto& row = storage_.visual(raw[1]);
        const auto word = [](auto& bytes, size_t offset, uint16_t value) {
            bytes[offset] = static_cast<uint8_t>(value);
            bytes[offset + 1] = static_cast<uint8_t>(value >> 8);
        };
        word(raw, 6, static_cast<uint16_t>(monster.vx8));
        word(raw, 8, static_cast<uint16_t>(monster.vy8));
        word(raw, 10, monster.fracX); word(raw, 12, monster.fracY);
        word(row, 0, static_cast<uint16_t>(monster.x));
        word(row, 2, static_cast<uint16_t>(monster.y + monster.hotspotY));
    }

    void applyMonsterImpact(uint64_t order, const Descriptor& descriptor) {
        setSpriteDescriptor(order, descriptor);
        auto& raw = storage_.actor(require(order));
        raw[25] = static_cast<uint8_t>(raw[26] - 4);
    }

    void writeBossDamage(uint64_t order,uint8_t health,uint8_t lives,const Descriptor& descriptor) {
        auto& raw=storage_.actor(require(order));
        raw[36]=health;raw[2]=lives;
        setSpriteDescriptor(order,descriptor);
    }

    void enterBossDebris(uint64_t order,uint8_t timer) {
        auto& raw=storage_.actor(require(order));
        raw[0]=14;raw[2]=timer;raw[21]=2;raw[27]=0;
    }

    void enterMonsterCorpse(uint64_t order) {
        auto& raw = storage_.actor(require(order));
        // 1000:74BB..7517 preserves stored HP, source, backup and opaque bytes.
        raw[0] = 12;
        raw[2] = 25;
        raw[21] = 2;
        raw[27] = 0;
    }

    bool applyMonsterDamage(uint64_t order, int8_t delta) {
        auto& raw = storage_.actor(require(order));
        const int health = static_cast<int>(raw[36]) + delta;
        if (health < 0) {
            enterMonsterCorpse(order);
            return true;
        }
        raw[36] = static_cast<uint8_t>(health);
        return false;
    }

    void writeCorpse(uint64_t order, const ActiveMonster& corpse, uint8_t timer,
                     bool animationAdvanced, const Descriptor& descriptor) {
        auto& raw = storage_.actor(require(order));
        auto& row = storage_.visual(raw[1]);
        auto word = [](auto& bytes, size_t offset, uint16_t value) {
            bytes[offset] = static_cast<uint8_t>(value);
            bytes[offset + 1] = static_cast<uint8_t>(value >> 8);
        };
        raw[0] = corpse.kind;
        raw[2] = timer;
        word(raw, 6, static_cast<uint16_t>(corpse.vx8));
        word(raw, 8, static_cast<uint16_t>(corpse.vy8));
        word(raw, 10, corpse.fracX);
        word(raw, 12, corpse.fracY);
        raw[20] = static_cast<uint8_t>(corpse.hotspotY);
        raw[21] = corpse.behavior;
        setActiveAnimation(order, monsterAnimation(corpse));
        word(row, 0, static_cast<uint16_t>(corpse.x));
        word(row, 2, static_cast<uint16_t>(corpse.y + corpse.hotspotY));
        if (animationAdvanced) { row[6] = descriptor[2]; row[7] = descriptor[3]; }
    }

    void convertCorpse(uint64_t order, const CorpseRewardConversion& conversion, const Descriptor& descriptor) {
        auto& raw = storage_.actor(require(order));
        setSpriteDescriptor(order, descriptor);
        // 1000:766d..76f4 preserves coordinates, fractions, backup and opaque bytes.
        if (conversion.hasReward) {
            raw[0] = static_cast<uint8_t>(conversion.reward.type) + 0x13;
            raw[2] = conversion.reward.timer;
            const uint16_t vy = static_cast<uint16_t>(conversion.reward.vy8);
            raw[8] = static_cast<uint8_t>(vy);
            raw[9] = static_cast<uint8_t>(vy >> 8);
            raw[27] = 0;
        } else {
            raw[0] = conversion.fade.kind;
            raw[2] = conversion.fade.timer;
            std::fill(raw.begin() + 6, raw.begin() + 10, uint8_t{0});
            raw[21] = 5;
            setActiveAnimation(order, conversion.fade.animation);
        }
    }

    void writeReward(uint64_t order, const BonusDrop& drop, bool animationAdvanced,
                     const Descriptor& descriptor) {
        auto& raw = storage_.actor(require(order));
        auto& row = storage_.visual(raw[1]);
        auto word = [](auto& bytes, size_t offset, uint16_t value) {
            bytes[offset] = static_cast<uint8_t>(value);
            bytes[offset + 1] = static_cast<uint8_t>(value >> 8);
        };
        raw[0] = static_cast<uint8_t>(static_cast<uint8_t>(drop.type) + 0x13);
        raw[2] = drop.timer;
        word(raw, 6, static_cast<uint16_t>(drop.vx8));
        word(raw, 8, static_cast<uint16_t>(drop.vy8));
        word(raw, 10, drop.fracX);
        word(raw, 12, drop.fracY);
        raw[20] = drop.hotspotY;
        raw[21] = 2;
        setActiveAnimation(order, drop.animation);
        word(row, 0, static_cast<uint16_t>(static_cast<int16_t>(drop.x)));
        word(row, 2, static_cast<uint16_t>(static_cast<int16_t>(drop.y)));
        if (animationAdvanced) { row[6] = descriptor[2]; row[7] = descriptor[3]; }
    }

    void writeTransient(uint64_t order, const TransientActor& actor, bool animationAdvanced,
                        const Descriptor& descriptor) {
        auto& raw = storage_.actor(require(order));
        auto& row = storage_.visual(raw[1]);
        auto word = [](auto& bytes, size_t offset, uint16_t value) {
            bytes[offset] = static_cast<uint8_t>(value);
            bytes[offset + 1] = static_cast<uint8_t>(value >> 8);
        };
        raw[0] = actor.kind;
        raw[2] = actor.timer;
        word(raw, 6, static_cast<uint16_t>(actor.vx8));
        word(raw, 8, static_cast<uint16_t>(actor.vy8));
        word(raw, 10, actor.fracX);
        word(raw, 12, actor.fracY);
        raw[20] = actor.hotspotY;
        raw[21] = 5;
        const auto animation = actor.animation.packed();
        std::copy(animation.begin(), animation.end(), raw.begin() + 22);
        word(row, 0, static_cast<uint16_t>(actor.x));
        word(row, 2, static_cast<uint16_t>(actor.y));
        // 1000:6156 changes the pixel-offset word, retaining width/height.
        if (animationAdvanced) { row[6] = descriptor[2]; row[7] = descriptor[3]; }
    }

    void writeMarker(uint64_t order, const LaunchPadMarker& marker, bool animationAdvanced,
                     const Descriptor& descriptor) {
        auto& raw = storage_.actor(require(order));
        auto& row = storage_.visual(raw[1]);
        auto word = [](auto& bytes, size_t offset, uint16_t value) {
            bytes[offset] = static_cast<uint8_t>(value);
            bytes[offset + 1] = static_cast<uint8_t>(value >> 8);
        };
        raw[0] = marker.kind;
        raw[2] = marker.timer;
        word(raw, 6, static_cast<uint16_t>(marker.velocityX8));
        word(raw, 8, static_cast<uint16_t>(marker.velocityY8));
        word(raw, 10, marker.fracX);
        word(raw, 12, marker.fracY);
        raw[21] = marker.mode;
        setActiveAnimation(order, marker.animation);
        word(row, 0, static_cast<uint16_t>(marker.x));
        word(row, 2, static_cast<uint16_t>(marker.y));
        if (animationAdvanced) { row[6] = descriptor[2]; row[7] = descriptor[3]; }
    }

    void resetForLevel(const Descriptor& playerDescriptor) {
        storage_.resetForLevel(playerDescriptor);
        orders_.fill(0);
    }

    // Fixture restoration is deliberately explicit; normal play never rebuilds
    // physical storage from the typed actor vectors.
    void restoreForFixture(const State& state, const std::array<uint64_t, ActorStorage::capacity + 1>& orders) {
        if (state.count > ActorStorage::capacity) throw std::invalid_argument("invalid fixture actor count");
        for (size_t slot = 1; slot <= state.count; ++slot) {
            if (orders[slot] == 0) throw std::invalid_argument("missing fixture actor identity");
            for (size_t previous = 1; previous < slot; ++previous) {
                if (orders[previous] == orders[slot]) throw std::invalid_argument("duplicate fixture actor identity");
            }
        }
        for (size_t slot = state.count + 1; slot < orders.size(); ++slot) {
            if (orders[slot] != 0) throw std::invalid_argument("inactive fixture actor identity");
        }
        if (orders[0] != 0) throw std::invalid_argument("player2 fixture identity");
        storage_.restore(state);
        orders_ = orders;
    }

private:
    template<size_t Size>
    static void playerWord(std::array<uint8_t, Size>& row, size_t offset, uint16_t value) {
        row[offset] = static_cast<uint8_t>(value);
        row[offset + 1] = static_cast<uint8_t>(value >> 8);
    }

    ActorStorage::Visual& playerVisual(size_t index) {
        if (index >= 2) throw std::out_of_range("invalid player visual index");
        return storage_.visual(index);
    }

    size_t require(uint64_t order) const {
        const size_t slot = find(order);
        if (slot == 0) throw std::out_of_range("unbound production actor");
        return slot;
    }

    ActorStorage storage_;
    std::array<uint64_t, ActorStorage::capacity + 1> orders_{};
};

} // namespace lezac::gameplay
