#include "gameplay/game_session.hpp"
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

int GameSession::monsterDamageForBomb(BombType type) const {
        // UNEVIDENCED legacy diagnostic only (@unevidenced:bomb_direct_monster_damage).
        // Live explode() now seeds flame records and never calls this helper.
        return std::clamp(bombTypeIndex(type) + 1, 1, 4);
    }

void GameSession::damageMonstersInExplosion(const std::vector<std::array<int, 2>>& tiles, BombType type) {
        int damage = monsterDamageForBomb(type);
        for (ActiveMonster& monster : monsters_) {
            if (!monster.alive) continue;
            // Boss actors are exempt from the generic shot-damage path in
            // the original (1000:7427); the head instead drains from live
            // flames each frame in updateBossHead.
            if (monster.behavior == 5 || monster.behavior == 6) continue;
            if (monsterOverlapsExplosionTiles(monster, tiles)) {
                damageMonster(monster, damage);
            }
        }
    }

bool GameSession::monsterOverlapsExplosionTiles(const ActiveMonster& monster, const std::vector<std::array<int, 2>>& tiles) const {
        for (const auto& tile : tiles) {
            float x = static_cast<float>(tile[0] * kTileSize);
            float y = static_cast<float>(tile[1] * kTileSize);
            if (rectsOverlap(static_cast<float>(monster.x), static_cast<float>(monster.y),
                             14.0f, 16.0f, x, y, static_cast<float>(kTileSize),
                             static_cast<float>(kTileSize))) {
                return true;
            }
        }
        return false;
    }

bool GameSession::rectsOverlap(float ax, float ay, float aw, float ah, float bx, float by, float bw, float bh) const {
        return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
    }

void GameSession::damageMonster(ActiveMonster& monster, int damage, bool updatedThisTick) {
        if (monster.behavior == 2) return;
        // Boss actors are exempt from generic damage (original 1000:7427
        // applies shot damage to kinds 1..8 only).
        if (monster.behavior == 5 || monster.behavior == 6) return;
        // 1000:745B..74A6 changes the displayed sprite, not the animation
        // cursor. The byte rewind holds this impact until the next advance.
        monster.animFrame = static_cast<uint8_t>(monsterCorpseSprite(monster));
        monster.hotspotY = static_cast<uint8_t>(16 - sprites_.sprites.at(monster.animFrame).height);
        monster.animTick = static_cast<uint8_t>(monster.animDelay - 4);
        monster.hp = std::max(0, monster.hp - std::max(1, damage));
        if (monster.hp == 0) {
            enterMonsterDeath(monster, updatedThisTick);
        }
    }

bool GameSession::playerOverlapsAnyExplosionTile(const Player& player, const std::vector<std::array<int, 2>>& tiles) const {
        for (const auto& tile : tiles) {
            float x = static_cast<float>(tile[0] * kTileSize);
            float y = static_cast<float>(tile[1] * kTileSize);
            if (playerOverlaps(player, x, y, static_cast<float>(kTileSize),
                               static_cast<float>(kTileSize))) {
                return true;
            }
        }
        return false;
    }

void GameSession::damagePlayersInExplosion(const std::vector<std::array<int, 2>>& tiles) {
        if (!playerDead_ && playerOverlapsAnyExplosionTile(player_, tiles)) {
            queuePlayerDamage(1);
        }
        if (playerCount_ > 1 && !player2Dead_ &&
            playerOverlapsAnyExplosionTile(player2_, tiles)) {
            queuePlayerDamage(2);
        }
    }

int GameSession::monsterCorpseSprite(const ActiveMonster& monster) const {
        const size_t kind = monster.kind < kMonsterImpactSprites.size()
                                ? monster.kind
                                : 0;
        return kMonsterImpactSprites[kind][monster.vx8 > 0 ? 1 : 0];
    }

void GameSession::enterMonsterDeath(ActiveMonster& monster, bool updatedThisTick) {
        if (monster.behavior == 2) return;
        // Fatal conversion follows movement; the velocity and fractions survive.
        monster.corpseSprite = static_cast<uint8_t>(monsterCorpseSprite(monster));
        monster.behavior = 2;
        monster.kind = 0x0c;
        // Encode raw timer 25's odd-frame countdown as remaining updates.
        // External blast conversion precedes this tick's monster dispatch.
        monster.stateTimer = 50 - static_cast<int>((logicTick_ + 1) & 1u) + (updatedThisTick ? 0 : 1);
        monster.animMode = 0;
        monster.hotspotY = static_cast<uint8_t>(16 - sprites_.sprites.at(monster.corpseSprite).height);
        monster.deathRewardPending = true;
        releaseMonsterSlot(monster);
        requestMonsterDeathSound();
    }

void GameSession::spawnBonusDrop(float x, float y, BonusType type) {
        BonusDrop drop;
        drop.x = x;
        drop.y = y;
        drop.type = type;
        drop.hotspotY = static_cast<uint8_t>(16 - sprites_.sprites.at(bonusSpriteIndex(type)).height);
        drop.actorOrder = claimActorOrder();
        bonusDrops_.push_back(drop);
    }

void GameSession::finishMonsterDeathReward(ActiveMonster& monster) {
        // Exact original kind-0x0c expiry path, disassembled at file
        // 0x7ddd..0x7ec0 (Ghidra 1000:766d..7750) and confirmed by the live
        // level-1 trace. The transition first rolls Random(100); values below
        // 40 produce no reward, while the ascending DGROUP thresholds select
        // one of the seven bonus kinds for rolls 40..99.
        const int rewardRoll = randomRangeValue(0, 100);
        const uint16_t rewardSound =
            static_cast<uint16_t>(0xea74 + randomRangeValue(0, 20));
        requestSoundCursor(rewardSound, 4);
        static constexpr std::array<int, 7> kRewardUpperBounds{{
            65, 71, 78, 83, 89, 93, 100,
        }};
        if (rewardRoll >= 40) {
            size_t rewardIndex = 0;
            while (rewardIndex + 1 < kRewardUpperBounds.size() &&
                   rewardRoll > kRewardUpperBounds[rewardIndex]) {
                ++rewardIndex;
            }
            spawnBonusDrop(
                static_cast<float>(monster.x),
                static_cast<float>(monster.y + monster.hotspotY),
                static_cast<BonusType>(rewardIndex));
            BonusDrop& reward = bonusDrops_.back();
            reward.actorOrder = monster.actorOrder;
            reward.vx8 = monster.vx8;
            reward.vy8 = static_cast<int16_t>(monster.vy8 - 200);
            reward.fracX = monster.fracX;
            reward.fracY = monster.fracY;
        } else {
            // 1000:760D converts the existing corpse in place, even at full
            // capacity. Its fractions survive; this frame does not tick it twice.
            TransientActor fade;
            fade.x = monster.x;
            fade.y = monster.y + monster.hotspotY;
            fade.kind = 0;
            fade.timer = 18;
            fade.fracX = monster.fracX;
            fade.fracY = monster.fracY;
            fade.spriteIndex = 68;
            fade.animation = ActorAnimation::initialize(69, 79, 2, 1);
            fade.actorOrder = monster.actorOrder;
            transientActors_.push_back(fade);
        }

        spawnExpiryParticles(monster.x, monster.y + monster.hotspotY);
    }

void GameSession::spawnExpiryParticles(int x, int y, int count) {
        // 1000:772A..777D draws both velocities even on allocation failure.
        // The dynamic actor-loop bound at 7ECB visits appended actors this frame.
        for (int effect = 0; effect < count; ++effect) {
            const int vx8 = static_cast<int>(randomRangeValue(0, 600)) - 300;
            const int vy8 = static_cast<int>(randomRangeValue(0, 600)) - 300;
            if (auto* actor = spawnTransientActor(x, y,
                    static_cast<int16_t>(vy8), 13, 0x0b, 15,
                    ActorAnimation::initialize(69, 79, 2, 2))) {
                actor->vx8 = static_cast<int16_t>(vx8);
                if (!orderedActorPass_) updateTransientActor(*actor);
            }
        }
    }

void GameSession::updateBonusDrops(size_t initialDrops, uint64_t onlyOrder) {
        initialDrops = std::min(initialDrops, bonusDrops_.size());
        for (size_t i = 0; i < initialDrops && i < bonusDrops_.size(); ++i) {
            BonusDrop& drop = bonusDrops_[i];
            if (onlyOrder && drop.actorOrder != onlyOrder) continue;
            if (drop.collected) continue;
            bool p1Overlaps = !playerDead_ &&
                              playerOverlaps(player_, drop.x, drop.y, 12.0f, 12.0f);
            bool p2Overlaps = playerCount_ > 1 && !player2Dead_ &&
                              playerOverlaps(player2_, drop.x, drop.y, 12.0f, 12.0f);
            if (p1Overlaps &&
                (!p2Overlaps ||
                 bonusDistanceSq(player_, drop) <= bonusDistanceSq(player2_, drop))) {
                collectBonusDrop(drop, player_, energy_, bombInventory_, 1);
            } else if (p2Overlaps) {
                collectBonusDrop(drop, player2_, energy2_, bombInventory2_, 2);
            }
            // Collection can append a cloud's rewards and invalidate drop.
            if (bonusDrops_[i].collected) continue;
            BonusDrop& moving = bonusDrops_[i];
            int x = static_cast<int>(moving.x);
            int y = static_cast<int>(moving.y) - moving.hotspotY;
            updateTimedActorMotion(x, y, moving.vx8, moving.vy8, moving.fracX, moving.fracY,
                                   scanActorEdges(x, y));
            moving.x = static_cast<float>(x);
            moving.y = static_cast<float>(y + moving.hotspotY);
            moving.timer = static_cast<uint8_t>(moving.timer - (logicTick_ & 1u));
            if (moving.timer == 0 || moving.timer == 0xff) {
                moving.collected = true;
                TransientActor fade;
                fade.kind = 0;
                fade.x = x;
                fade.y = static_cast<int>(moving.y);
                fade.fracX = moving.fracX;
                fade.fracY = moving.fracY;
                fade.timer = 18;
                // DS:006C selects one-based sprite 74 for expired rewards.
                fade.spriteIndex = 73;
                fade.animation = ActorAnimation::initialize(74, 79, 2, 1);
                fade.actorOrder = moving.actorOrder;
                transientActors_.push_back(fade);
            }
        }
        bonusDrops_.erase(std::remove_if(bonusDrops_.begin(), bonusDrops_.end(),
                                         [](const BonusDrop& drop) { return drop.collected; }),
                          bonusDrops_.end());
    }

float GameSession::bonusDistanceSq(const Player& player, const BonusDrop& drop) const {
        float dx = (player.x + 6.0f) - (drop.x + 6.0f);
        float dy = (player.y + 8.0f) - (drop.y + 6.0f);
        return dx * dx + dy * dy;
    }

void GameSession::collectBonusDrop(BonusDrop& drop, const Player& collector, int& energy, BombInventory& inventory, uint8_t playerIndex) {
        BonusType type = drop.type;
        drop.collected = true;
        applyBonus(type, collector, energy, inventory, playerIndex);
        requestSoundCursor(kBonusPickupSoundCursor, kBonusPickupSoundPriority);
    }

void GameSession::applyBonus(BonusType type, const Player& collector, int& energy, BombInventory& inventory, uint8_t playerIndex) {
        switch (type) {
            case BonusType::Present:
                addScore(playerIndex, 2000);
                break;
            case BonusType::FirstAid:
                addScore(playerIndex, 1000);
                energy = 100;
                break;
            case BonusType::HotDog:
                addScore(playerIndex, 1500);
                energy = std::min(100, energy + 33);
                break;
            case BonusType::JollyCloud:
                addScore(playerIndex, 2000);
                spawnBonusRain(collector);
                break;
            case BonusType::YellowBombBox:
                addScore(playerIndex, 3000);
                grantNormalBombSet(inventory);
                break;
            case BonusType::GreenBombBox:
                addScore(playerIndex, 1000);
                grantSuperBombSet(inventory);
                break;
            case BonusType::BigDiamond:
                addScore(playerIndex, 5000);
                break;
        }
    }

void GameSession::grantNormalBombSet(BombInventory& inventory) {
        inventory.counts[0] = 200;
        inventory.counts[1] = std::min(99, inventory.counts[1] + randomInclusive(1, 10));
        inventory.counts[2] = std::min(99, inventory.counts[2] + randomInclusive(1, 4));
        if (!hasBomb(inventory, inventory.selected)) selectNextAvailableBomb(inventory);
    }

void GameSession::grantSuperBombSet(BombInventory& inventory) {
        inventory.counts[0] = 200;
        inventory.counts[1] = std::min(99, inventory.counts[1] + randomInclusive(1, 13));
        inventory.counts[2] = std::min(99, inventory.counts[2] + randomInclusive(2, 6));
        inventory.counts[3] = std::min(99, inventory.counts[3] + randomInclusive(1, 2));
        if (!hasBomb(inventory, inventory.selected)) selectNextAvailableBomb(inventory);
    }

void GameSession::spawnBonusRain(const Player& collector) {
        for (int i = 0; i < 4; ++i) {
            spawnBonusDrop(std::clamp(collector.x - 24.0f + i * 16.0f, 0.0f,
                                     std::max(16.0f, level_.width * 8.0f - 16.0f)),
                           std::max(16.0f, collector.y - 48.0f - i * 4.0f),
                           i % 2 == 0 ? BonusType::Present : BonusType::BigDiamond);
        }
    }
}
