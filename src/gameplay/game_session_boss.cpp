#include "gameplay/game_session.hpp"
#include "gameplay/motion_math.hpp"
#include "core/progress.hpp"
#include <cmath>

namespace lezac::gameplay {
using namespace lezac::core;
using detail::clampI16;
using detail::integrateAxis8_8;

void GameSession::spawnLevel7Boss() {
        std::vector<uint8_t> granBytes;
        for (const GranRecord& record : gran_.records) {
            granBytes.insert(granBytes.end(), record.bytes.begin(), record.bytes.end());
        }
        if (granBytes.size() != 399 || granBytes[0] != 7) return;
        size_t pos = 1;
        const size_t recordCount = granBytes[0];
        const size_t recordsBase = pos;
        pos += recordCount * 0x26;
        const size_t spritesBase = pos;
        pos += recordCount;
        const size_t pairsBase = pos;
        pos += recordCount * 4;
        const size_t extraCount = granBytes[pos++];
        const size_t extrasBase = pos;
        if (pos + extraCount * 16 != granBytes.size()) return;

        for (size_t i = 0; i < bossSinTable_.size(); ++i) {
            // The original fills a 128-entry Real48 table with Sin(i*6.28/128).
            bossSinTable_[i] = std::sin(static_cast<float>(i) * 6.28f / 128.0f);
        }

        bossLinks_.clear();
        for (size_t i = 0; i < extraCount; ++i) {
            const uint8_t* extra = granBytes.data() + extrasBase + i * 16;
            BossMotionLink link;
            link.targetVisual = static_cast<uint8_t>(extra[0] + kBossVisualBase);
            link.selfVisual = static_cast<uint8_t>(extra[1] + kBossVisualBase);
            link.gain = extra[2];
            link.mode = extra[3];
            link.radiusX = extra[4];
            link.radiusY = extra[5];
            link.phase = extra[6];
            link.offX = static_cast<int16_t>(extra[7] | (extra[8] << 8));
            link.offY = static_cast<int16_t>(extra[9] | (extra[10] << 8));
            // The loader copies the complete link before the first actor pass.
            link.outX = static_cast<int16_t>(extra[11] | (extra[12] << 8));
            link.outY = static_cast<int16_t>(extra[13] | (extra[14] << 8));
            link.biasY = static_cast<int8_t>(extra[15]);
            bossLinks_.push_back(link);
        }

        const uint64_t firstBossVisualOrder = nextActorOrder_;
        const auto bossGroup = static_cast<uint16_t>(sharedActorCount() + 1);
        for (size_t i = 0; i < recordCount; ++i) {
            const uint8_t* record = granBytes.data() + recordsBase + i * 0x26;
            ActiveMonster actor;
            actor.kind = record[0x00];
            actor.behavior = record[0x15];
            actor.bossVisual = static_cast<uint8_t>(record[0x01] + kBossVisualBase);
            // The GRAN reader rewrites the head +0x12 and segment +0x25
            // owner fields to the group's first one-based actor slot.
            actor.bossGroup = bossGroup;
            const size_t entryOrder = static_cast<size_t>(actor.bossVisual) - kBossVisualBase;
            if (entryOrder >= recordCount) continue;
            const int dx = static_cast<int16_t>(granBytes[pairsBase + entryOrder * 4] |
                                                (granBytes[pairsBase + entryOrder * 4 + 1] << 8));
            const int dy = static_cast<int16_t>(granBytes[pairsBase + entryOrder * 4 + 2] |
                                                (granBytes[pairsBase + entryOrder * 4 + 3] << 8));
            actor.x = 100 + dx;
            actor.y = 100 + dy;
            const uint8_t entrySprite = granBytes[spritesBase + entryOrder];
            const uint8_t animSet = record[0x03];
            if (animSet != 0 && animSet < kBossAnimSets.size() &&
                kBossAnimSets[animSet][0] != 0) {
                actor.animStart = kBossAnimSets[animSet][0] - 1;
                actor.animEnd = kBossAnimSets[animSet][1] - 1;
                actor.animMode = 1;
                actor.animCursor = actor.animStart;
                actor.animTick = record[0x1a];
            } else {
                // A zero animation-set selector leaves the copied bytes intact.
                actor.animCursor = static_cast<uint8_t>(record[0x16] - 1);
                actor.animStart = static_cast<uint8_t>(record[0x17] - 1);
                actor.animEnd = static_cast<uint8_t>(record[0x18] - 1);
                actor.animTick = record[0x19];
                actor.animMode = record[0x1b];
                actor.animStep = static_cast<int8_t>(record[0x1c]);
            }
            // GRAN.MST and the animation table carry one-based descriptors.
            actor.animFrame = entrySprite - 1;
            // Raw delay byte: the shared advance (1000:608F) fires when the
            // counter exceeds it, so 0 keeps the old every-tick cadence and
            // any nonzero byte means period byte+1.
            actor.animDelay = record[0x1a];
            if (actor.kind == 0x1e) {
                actor.bossHpByte = record[0x24];
                actor.bossLives = record[0x02];
                actor.bossBoxW = record[0x0e];
                actor.bossBoxH = record[0x0f];
                actor.hp = actor.bossHpByte;
            } else {
                // Segments carry serial link bytes at +0x0e/+0x10; at level
                // entry the DS:0x79F9 rebase base is zero, so the shipped
                // serials index bossLinks_ 1-based directly.
                actor.linkA = record[0x0e];
                actor.linkB = record[0x0f];
                actor.linkC = record[0x10];
                actor.hp = 255;
            }
            actor.actorOrder = claimActorOrder();
            actor.bossVisualOrder = firstBossVisualOrder + entryOrder;
            monsters_.push_back(actor);
        }
        bossPresent_ = true;
    }

ActiveMonster* GameSession::findBossActorByVisual(uint8_t visual) {
        for (ActiveMonster& monster : monsters_) {
            if (monster.alive && !monster.bossDebris &&
                (monster.behavior == 5 || monster.behavior == 6) &&
                monster.bossVisual == visual) {
                return &monster;
            }
        }
        return nullptr;
    }

void GameSession::updateBossLinks() {
        if (bossLinks_.empty()) return;
        for (BossMotionLink& link : bossLinks_) {
            ActiveMonster* target = findBossActorByVisual(link.targetVisual);
            if (link.mode != 0xff) {
                ActiveMonster* self = findBossActorByVisual(link.selfVisual);
                if (!target || !self) continue;
                link.outX = static_cast<int16_t>(
                    (target->x - self->x + link.offX) * link.gain);
                // 1000:43E8 reads DS:C220 visual Y, including the head's
                // signed hotspot after a nonfatal hit changes its descriptor.
                link.outY = static_cast<int16_t>(
                    (target->y + target->hotspotY - self->y - self->hotspotY + link.offY) * link.gain + link.biasY);
            } else {
                if (!target) continue;
                // Mode 0xff is a VERTICAL-only oscillation about the anchor,
                // not a two-axis orbit. A live level-7 capture pins the rule
                // over all 128 phases and all four orbit links, 774/774 ticks
                // exact on both axes:
                //   outX = anchor.x + offX                     (no x term)
                //   outY = anchor.y + offY + trunc(sin[phase] * radiusY)
                // radiusY is link byte +0x05; byte +0x04 is not an x radius,
                // so the cosine term the port used to add was a spurious 1 px
                // horizontal wobble. The scale is the shipped table's literal
                // 6.28 (not 2*pi), and the product truncates toward zero --
                // rounding to nearest is off by one on 21 of the 128 phases.
                link.phase = static_cast<uint8_t>((link.phase + link.gain) & 0x7f);
                const float sinValue = bossSinTable_[link.phase];
                link.outX = static_cast<int16_t>(target->x + link.offX);
                link.outY = static_cast<int16_t>(
                    target->y + target->hotspotY + link.offY +
                    static_cast<int>(sinValue * link.radiusY));
            }
        }
    }

void GameSession::applyBossSegmentLinks(ActiveMonster& monster) {
        const std::array<uint8_t, 3> serials{monster.linkA, monster.linkB, monster.linkC};
        for (uint8_t serial : serials) {
            if (serial == 0) break;
            int sign = 1;
            uint8_t index = serial;
            if (index > 0x80) {
                index = static_cast<uint8_t>(index - 0x80);
                sign = -1;
            }
            if (index == 0 || index > bossLinks_.size()) continue;
            const BossMotionLink& link = bossLinks_[index - 1];
            if (link.mode != 0xff) {
                monster.vx8 = clampI16(monster.vx8 + sign * link.outX);
                monster.vy8 = clampI16(monster.vy8 + sign * link.outY);
                const int limit = link.mode;
                if (std::abs(monster.vx8) > limit) {
                    monster.vx8 = static_cast<int16_t>(
                        monster.vx8 - (monster.vx8 > 0 ? limit : -limit));
                }
                if (std::abs(monster.vy8) > limit) {
                    monster.vy8 = static_cast<int16_t>(
                        monster.vy8 - (monster.vy8 > 0 ? limit : -limit));
                }
            } else {
                monster.x = link.outX;
                monster.y = link.outY;
                monster.vx8 = 0;
                monster.vy8 = 0;
                monster.fracX = 0;
                monster.fracY = 0;
            }
        }
    }

bool GameSession::isBossMotionBehavior(int behavior) {
        return behavior == 5 || behavior == 6;
    }

void GameSession::updateBossHead(ActiveMonster& monster) {
        // 1000:5E59 divides the shared 16-bit DS:78C2 clock, including wrap.
        monster.bossTick = static_cast<uint16_t>(logicTick_);
        // The original scans all four edges up front and the later gravity,
        // jump and reflection steps all read those flags, so scan first.
        const BossHeadEdges edges = scanBossHeadEdges(monster);
        // The actor-update caller computes both players' deltas and chooses the
        // Manhattan-nearest one before entering behavior 6. The callee reads
        // that selected X delta indirectly through caller local [BP-4].
        if (monster.bossTick % 29 == 0) {
            const int roarRoll = static_cast<int>(randomRangeValue(0, 100));
            if (roarRoll > 0x46 && (monster.bossTick & 1) == 0) {
                requestSoundCursor(kBossHeadRoarSoundCursor, kBossHeadRoarSoundPriority);
            }
            const int speed = 0x96 + static_cast<int>(randomRangeValue(0, 0x320));
            const Player& target =
                nearestPlayer(static_cast<float>(monster.x),
                              static_cast<float>(monster.y));
            monster.vx8 =
                clampI16(target.x > static_cast<float>(monster.x)
                             ? speed
                             : -speed);
            if (edges.bottom) {
                monster.vy8 = clampI16(-(0x12c + static_cast<int>(randomRangeValue(0, 0x5dc))));
            }
        }
        damageBossHeadFromFlames(monster);
        // Gravity (file 0x673b..0x6742): `add WORD ss:[di-0xe],0x40` is guarded
        // by `cmp BYTE ss:[di-0x21],0 / jne`, so it is applied ONLY when the
        // bottom flag is clear, and there is no upper clamp anywhere in
        // 1000:5CB0..604F. A live level-7 capture reaches vy 0x0a40, well past
        // the 0x07ff the port used to clamp to.
        if (!edges.bottom) {
            monster.vy8 = clampI16(monster.vy8 + 0x40);
        }
        // Reflection (file 0x6743..0x67bf): a top edge with negative velocity,
        // or a bottom edge with positive velocity, replaces the velocity with
        // -(v/2) using `idiv` truncation toward zero; the left/right pair does
        // the same for the horizontal velocity. The original does NOT reset the
        // 8.8 sub-pixel fraction here, and does not push the head out of the
        // tile -- the scan runs one tile outside the box, so the reversal
        // happens before the head enters solid geometry.
        if ((edges.top && monster.vy8 < 0) || (edges.bottom && monster.vy8 > 0)) {
            monster.vy8 = static_cast<int16_t>(-(monster.vy8 / 2));
        }
        if ((edges.left && monster.vx8 < 0) || (edges.right && monster.vx8 > 0)) {
            monster.vx8 = static_cast<int16_t>(-(monster.vx8 / 2));
        }
    }

void GameSession::damageBossHeadFromFlames(ActiveMonster& monster) {
        int damage = 0, lastCell = 0;
        const int headTileX = monster.x / kTileSize;
        const int headTileY = monster.y / kTileSize;
        for (int dy = 0; dy < monster.bossBoxH; ++dy) {
            for (int dx = 0; dx < monster.bossBoxW; dx += 2) {
                if (tileAt(headTileX + dx, headTileY + dy) != 0x75) continue;
                ++damage;
                lastCell = (headTileY + dy) * level_.width + headTileX + dx;
            }
        }
        if (damage == 0) return;
        const auto ray = std::find_if(flameRecords_.rbegin(), flameRecords_.rend(),
            [lastCell](const FlameRecord& item) { return item.cell == lastCell; });
        if (ray != flameRecords_.rend() && ray->mass > 1) damage *= 2;
        if (damage > monster.bossHpByte) {
            --monster.bossLives;
        }
        monster.bossHpByte = static_cast<uint8_t>(monster.bossHpByte - damage);
        // 1000:5A75 replaces the visible descriptor and signed hotspot only.
        // The caller still holds collision-space Y until its final writeback.
        monster.animFrame = 0x2f - 1;
        monster.hotspotY = static_cast<int8_t>(16 - altSprites_.sprites.at(monster.animFrame).height);
        if (monster.bossLives == 0xff) bossDeathChain(monster);
    }

void GameSession::bossDeathChain(ActiveMonster& head) {
        for (ActiveMonster& monster : monsters_) {
            if (!monster.alive) continue;
            if (monster.kind == 0x1f && monster.bossGroup == head.bossGroup) {
                monster.kind = 0x0e;
                monster.behavior = 2;
                monster.bossDebris = true;
                monster.animMode = 0;
                monster.stateTimer = 0x28 + static_cast<int>(randomRangeValue(0, 10));
            }
        }
        head.kind = 0x0e;
        head.behavior = 2;
        head.bossDebris = true;
        head.animMode = 0;
        head.stateTimer = 0x3c;
        applyTileTrigger(1000);
        requestTileTriggerSound();
        bossDefeated_ = true;
        requestMonsterDeathSound();
    }
}
