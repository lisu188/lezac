#include "gameplay/game_session.hpp"
#include "gameplay/motion_math.hpp"
#include "core/progress.hpp"
#include <cmath>

namespace lezac::gameplay {
using namespace lezac::core;
using detail::clampI16;
using detail::integrateAxis8_8;

std::array<int, 2> GameSession::monsterFrameRange(uint8_t kind) const {
        switch (kind) {
            case 1: return {43, 44};
            case 2: return {39, 41};
            case 3: return {49, 51};
            case 4: return {53, 55};
            default: return {39, 41};
        }
    }

std::array<int, 2> GameSession::monsterDirectionalFrameRange(uint8_t kind, int16_t vx8) const {
        // vx > 0 selects the right-facing set (1000:72DA `cmp vx,0; jle`);
        // vx < 0 the left set (1000:7286 `jge`). vx == 0 selects NEITHER in
        // the reselection; the spawn default is the actor+0x03 (left) set --
        // both captured spawns show frame 44, the left pair's high member --
        // so the vx == 0 mapping here is the left set.
        if (kind == 1) return vx8 > 0 ? std::array<int, 2>{45, 46}
                                      : std::array<int, 2>{43, 44};
        return monsterFrameRange(kind);
    }

uint8_t GameSession::monsterHotspotY(uint8_t kind) { return kind == 1 ? 6 : 0; }

bool GameSession::actorTouchesPlayer(const Player& player, int ax, int ayCollide) const {
        const int dx = static_cast<int>(player.x) - ax;
        const int dy = static_cast<int>(player.y) - ayCollide;
        return dx > -10 && dx < 10 && dy > -10 && dy < 10;
    }

uint16_t GameSession::randomRangeValue(uint16_t base, uint16_t range) { return random_.range(base, range); }

int GameSession::randomInclusive(int low, int high) {
        return static_cast<int>(randomRangeValue(static_cast<uint16_t>(low),
                                                 static_cast<uint16_t>(high - low + 1)));
    }

int16_t GameSession::groundWalkerSpeed8(const ActiveMonster& monster) const {
        return clampI16(monster.ai0);
    }

int16_t GameSession::retargetSpeed8(const ActiveMonster& monster) const {
        return clampI16(monster.ai1);
    }

void GameSession::refreshMonsterAnimationProfile(ActiveMonster& monster) {
        auto frames = monsterDirectionalFrameRange(monster.kind, monster.vx8);
        if (monster.animStart != frames[0] || monster.animEnd != frames[1]) {
            monster.animStart = static_cast<uint8_t>(frames[0]);
            monster.animEnd = static_cast<uint8_t>(frames[1]);
            monster.animFrame = monster.animStart;
            monster.animCursor = monster.animStart;
        }
    }

void GameSession::reselectWalkerFacing(ActiveMonster& monster) {
        if (monster.vx8 == 0) return;
        // Facing reselection only exists for kinds with DISTINCT left/right
        // pairs. For direction-independent kinds -- e.g. the shipped kind-4
        // behavior-3 actors on levels 3 and 6, whose range is a static
        // {53,55} -- a terrain event must stay the no-op it was before this
        // helper existed, not rewind their animation. Note the guard is on
        // the KIND's table, not on whether this call changes the range: the
        // capture adjudicates that a kind-1 wall tick re-selecting the SAME
        // pair still resets the cursor (walker B, frame 907: dropping the
        // same-range reset diverges there), so same-range resets are real
        // evidenced behavior for directional kinds.
        if (monsterDirectionalFrameRange(monster.kind, -0x0100) ==
            monsterDirectionalFrameRange(monster.kind, 0x0100)) {
            return;
        }
        auto frames = monsterDirectionalFrameRange(monster.kind, monster.vx8);
        monster.animStart = static_cast<uint8_t>(frames[0]);
        monster.animEnd = static_cast<uint8_t>(frames[1]);
        monster.animCursor = monster.animStart;
    }

void GameSession::initializeMonsterMotion(ActiveMonster& monster) {
        if (monster.behavior == 4) {
            // Original 1000:70D7 gates behavior-4 steering on the shared
            // DS:78C2 frame counter. A newly spawned actor therefore stays
            // still until that global clock is divisible by actor +0x0E;
            // there is no private per-actor countdown and no spawn-time draw.
            monster.vx8 = 0;
            monster.vy8 = 0;
            monster.motionTimer = 0;
            refreshMonsterAnimationProfile(monster);
            return;
        }
        monster.vx8 = 0;
        monster.vy8 = 0;
        refreshMonsterAnimationProfile(monster);
    }

void GameSession::retargetMonster(ActiveMonster& monster) {
        int16_t speed = retargetSpeed8(monster);
        const Player& target = nearestPlayer(monster.x, monster.y);
        double dx = static_cast<int>(target.x) - monster.x;
        double dy = static_cast<int>(target.y) - monster.y;
        double threshold = monster.ai2;
        if (std::fabs(dx) + std::fabs(dy) < threshold) {
            double len = std::max(1.0, std::hypot(dx, dy));
            // The original vector helper at 1000:346B converts both scaled
            // reals with truncation toward zero. The diagonal runtime capture
            // is decisive: speed 494 and delta (40,20) produce (441,220), not
            // the rounded (442,221).
            monster.vx8 = clampI16(static_cast<int>(speed * dx / len));
            monster.vy8 = clampI16(static_cast<int>(speed * dy / len));
        } else {
            int range = std::max(1, static_cast<int>(monster.ai1) * 2);
            int vxFixed = static_cast<int>(randomRangeValue(0, static_cast<uint16_t>(range))) -
                          static_cast<int>(monster.ai1);
            int vyFixed = static_cast<int>(randomRangeValue(0, static_cast<uint16_t>(range))) -
                          static_cast<int>(monster.ai1);
            monster.vx8 = clampI16(vxFixed);
            monster.vy8 = clampI16(vyFixed);
        }
    }

const Player& GameSession::nearestPlayer(float x, float y) const {
        if (playerCount_ <= 1 || player2Dead_) return player_;
        if (playerDead_) return player2_;
        float distance1 =
            std::fabs(player_.x - x) + std::fabs(player_.y - y);
        float distance2 =
            std::fabs(player2_.x - x) + std::fabs(player2_.y - y);
        return distance2 < distance1 ? player2_ : player_;
    }

void GameSession::updateMonsterMotion(ActiveMonster& monster, float unused1) {
        if (monster.behavior == 6) {
            updateBossHead(monster);
            return;
        }
        if (monster.behavior == 5) {
            applyBossSegmentLinks(monster);
            return;
        }
        if (monster.behavior == 4) {
            const uint16_t period = monster.ai0;
            const uint16_t originalTick = static_cast<uint16_t>(logicTick_);
            if (period != 0 && originalTick % period == 0) {
                retargetMonster(monster);
            }
            // Diagnostic only: ticks until the next shared gate, not AI state.
            monster.motionTimer = period == 0
                                      ? 0
                                      : static_cast<int>(
                                            period - (originalTick % period));
            return;
        }

        // Ground walkers (behaviors 1-3) face the direction set at spawn
        // (initializeMonsterMotion) and reverse only at walls and floor edges;
        // the original never steers them toward the player, so preserve the
        // current facing rather than seeking (defaulting to the spawn heading).
        // Rank 10: the original seeds and renormalises the ground walker's
        // horizontal speed only while the bottom-contact flag is set; an
        // airborne walker keeps whatever vx it had (0 at spawn).
        if (monster.edges.bottom) {
            const int16_t speed = groundWalkerSpeed8(monster);
            if (monster.vx8 == 0) {
                // Seed (1000:71F9): no facing-reselect request -- only the
                // renormalisation branch sets the flag (1000:71F3).
                monster.vx8 = speed;
            } else if (std::abs(monster.vx8) != speed) {
                monster.vx8 = monster.vx8 > 0 ? speed : static_cast<int16_t>(-speed);
                monster.facingDirty = true;
            }
            float probeX = monster.x + (monster.vx8 < 0 ? -2.0f : 15.0f);
            if (!solidPixel(probeX, monster.y + 17.0f)) {
                monster.vx8 = -monster.vx8;
                // The original sets the reselect flag whenever either
                // below-edge cell stops being bottom-solid (1000:723D).
                monster.facingDirty = true;
            }
        }
    }

void GameSession::updateMonsterSpawners() {
        // Recovered original spawner loop, 1000:7A6B..7C2C. The decisive byte
        // order per record:
        //   1000:7A9B  dec  es:[di+0x1b]      ; countdown FIRST, before every
        //                                     ; gate -- the byte free-runs and
        //                                     ; wraps 0->255 even when budget
        //                                     ; or slots are spent
        //   1000:7AA2  cmp  es:[di+0x1b],0    ; spawn path only when it
        //              je   ...               ; REACHES 0 this tick
        //   1000:7AAF  cmp  es:[di+0x0a],0    ; live-slot gate
        //   1000:7ABC  cmp  es:[di+0x09],0    ; budget gate
        //   1000:7AC9  cmp  es:[di+0x08],1    ; enabled gate
        //   1000:7AD6  mov  al,es:[di+0x1c]   ; reload from the reset byte...
        //   1000:7ADD  mov  es:[di+0x1b],al   ; ...BEFORE the spawn helper
        //   1000:7B28  call (spawn helper)
        //   1000:7B2B  cmp  ds:0x2072,1       ; helper failure keeps the
        //                                     ; reload but spends nothing
        //   1000:7B38/7B3F dec budget / slots ; only on success, then the RNG
        //                                     ; draws ai0, ai1, ai2, hp
        // A blocked spawn (gates fail at countdown 0) does NOT reload, so the
        // byte wraps and retries 256 ticks later (capture: 5/5 free-running
        // wraps with live=2). Fit: 1458/1458 byte transitions, first spawn at
        // frame 257 (0xE5 = 229 ticks after frame 28), period exactly 90.
        for (size_t i = 0; i < spawnerStates_.size() && i < level_.monsterSpawners.size(); ++i) {
            SpawnerState& state = spawnerStates_[i];
            const MonsterSpawner& spawner = level_.monsterSpawners[i];
            state.cooldown = static_cast<uint8_t>(state.cooldown - 1);
            if (state.cooldown != 0) continue;
            if (state.availableSlots <= 0) continue;
            if (state.remaining <= 0) continue;
            if (!spawner.enabled) continue;
            state.cooldown = spawner.cooldownReset;
            if (sharedActorCount() >= 30) continue;
            ActiveMonster monster;
            monster.x = spawner.x;
            // The spawner y is VISUAL space; monster.y carries the
            // collision-space y = visual - hotspot (rank 6).
            monster.hotspotY = monsterHotspotY(spawner.monsterKind);
            monster.y = static_cast<int>(spawner.y) - monster.hotspotY;
            monster.kind = spawner.monsterKind;
            monster.spawnerIndex = i;
            monster.hasSpawner = true;
            monster.behavior = spawner.spawnArg;
            monster.ai0 = randomRangeValue(spawner.param0Base, spawner.param0Range);
            monster.ai1 = randomRangeValue(spawner.param1Base, spawner.param1Range);
            monster.ai2 = randomRangeValue(spawner.param2Base, spawner.param2Range);
            monster.hp = 1 + static_cast<uint8_t>(randomRangeValue(spawner.randomBase, spawner.randomRange));
            auto frames = monsterDirectionalFrameRange(monster.kind, monster.vx8);
            monster.animStart = static_cast<uint8_t>(frames[0]);
            monster.animEnd = static_cast<uint8_t>(frames[1]);
            monster.animFrame = monster.animStart;
            monster.animCursor = monster.animStart;
            // Raw delay byte: the shared advance fires when the counter
            // EXCEEDS it (1000:608F cmp/ja), so delay 3 means period 4.
            monster.animDelay = spawner.animationDelay;
            // The anim init helper (1000:06AB) leaves the counter AT the
            // delay, so the first entity update advances immediately: the
            // spawn-tick visible frame is animStart + 1, the pair's high
            // member (capture: 2/2 spawns show 44).
            monster.animTick = monster.animDelay;
            initializeMonsterMotion(monster);
            monster.actorOrder = claimActorOrder();
            monsters_.push_back(monster);
            --state.remaining;
            --state.availableSlots;
        }
    }

void GameSession::updateMonsters(float dt, uint64_t onlyOrder) {
        for (ActiveMonster& monster : monsters_) {
            if (onlyOrder && monster.actorOrder != onlyOrder) continue;
            if (!monster.alive) continue;
            if (monster.behavior == 2) {
                if (monster.bossDebris) {
                    updateTimedActorMotion(monster.x, monster.y, monster.vx8, monster.vy8,
                                           monster.fracX, monster.fracY, scanActorEdges(monster.x, monster.y));
                    if (logicTick_ & 1u) monster.stateTimer = static_cast<uint8_t>(monster.stateTimer - 1);
                    if (monster.stateTimer == 0 || monster.stateTimer == 0xff) {
                        Bomb bomb;
                        bomb.type = BombType::Medium;
                        bomb.pixelX = monster.x;
                        bomb.pixelY = monster.y + monster.hotspotY;
                        bomb.x = monster.x >> 3;
                        bomb.y = bomb.pixelY >> 3;
                        bomb.fracX = monster.fracX; bomb.fracY = monster.fracY;
                        bomb.actorOrder = monster.actorOrder;
                        bomb.bossVisualOrder = monster.bossVisualOrder;
                        monster.alive = false;
                        explode(bomb);
                    }
                    continue;
                }
                if (monster.kind == 0x0c) {
                    updateTimedActorMotion(monster.x, monster.y, monster.vx8, monster.vy8,
                                           monster.fracX, monster.fracY, scanActorEdges(monster.x, monster.y));
                }
                if (--monster.stateTimer <= 0) {
                    // Corpse expiry reuses its slot for the reward or fade.
                    // Do not count both representations during allocation.
                    monster.alive = false;
                    if (monster.deathRewardPending) {
                        finishMonsterDeathReward(monster);
                        monster.deathRewardPending = false;
                    }
                    releaseMonsterSlot(monster);
                }
                continue;
            }
            const int damageColumn = (monster.x + 4) >> 3;
            const int damageRow = monster.y >> 3;
            // Recovered original animation advance -- the per-entity PROLOGUE
            // (1000:6088 `inc es:[di+3]`; 1000:608F `cmp al,es:[di+4]; ja`):
            // the counter must EXCEED the delay byte, so delay 3 advances
            // every 4 ticks (capture: 589/589 sprite changes at
            // (frame - spawn) mod 4 == 0; mod 3 spread 198/196/195). The
            // advance steps the CURSOR and only then rewrites the visible
            // frame (the visual-table word write at 1000:613B..6156); between
            // boundaries the visible frame is untouched, which is what makes
            // the facing reselection latch.
            if (monster.animMode != 0) monster.animTick = static_cast<uint8_t>(monster.animTick + 1);
            if (monster.animMode != 0 && monster.animTick > monster.animDelay) {
                monster.animTick = 0;
                if (monster.animCursor < monster.animStart ||
                    monster.animCursor > monster.animEnd) {
                    // Repair for hand-seeded actors (diagnostics, GRAN.MST
                    // bosses) that predate the cursor field; the live spawner
                    // path always keeps the cursor in range.
                    monster.animCursor = (monster.animFrame >= monster.animStart &&
                                          monster.animFrame <= monster.animEnd)
                                             ? monster.animFrame
                                             : monster.animStart;
                }
                int next = static_cast<int>(monster.animCursor) + monster.animStep;
                if (next > monster.animEnd || next < monster.animStart) {
                    if (monster.animMode == 2) {
                        monster.animStep = -monster.animStep;
                        next = static_cast<int>(monster.animCursor) + monster.animStep;
                    } else {
                        // Wrap re-enters at the range base (1000:60DA..60E4
                        // `mov al,es:[di+1]; mov es:[di],al`).
                        next = monster.animStep >= 0 ? monster.animStart : monster.animEnd;
                    }
                }
                monster.animCursor = static_cast<uint8_t>(
                    std::clamp(next, static_cast<int>(monster.animStart),
                               static_cast<int>(monster.animEnd)));
                monster.animFrame = monster.animCursor;
            }

            // Rank 5: the player-contact test runs BEFORE the tile scan and
            // the motion update (contact at 1000:63C6..63F0, scan from
            // 1000:655B), i.e. from the PRE-motion position. monster.y is the
            // collision-space y (rank 6), which carries the actor +0x14 bias
            // the original applies at 1000:629D before both the contact test
            // and the scan.
            if (!playerDead_ && actorTouchesPlayer(player_, monster.x, monster.y)) {
                queuePlayerDamage(1);
            }
            if (playerCount_ > 1 && !player2Dead_ &&
                actorTouchesPlayer(player2_, monster.x, monster.y)) {
                queuePlayerDamage(2);
            }
            // The level-3 behavior-4 lockstep extends the recovered edge-scan
            // path to free flyers. They use the same pre-integration scan and
            // common top/side response, but have their own bottom reflection
            // before steering and never receive gravity.
            const bool recoveredResolution =
                !isBossMotionBehavior(monster.behavior);
            if (recoveredResolution) {
                monster.edges = scanActorEdges(monster.x, monster.y);
                // Facing-reselect request, seeded from wall contact exactly
                // where the original's behaviour-3 dispatch does it
                // (1000:7159..716B: [bp-0x20] = left || right).
                monster.facingDirty = monster.behavior == 3 &&
                                      (monster.edges.left || monster.edges.right);
            } else {
                monster.edges = {};
                monster.facingDirty = false;
            }

            // Gravity and landing run BEFORE the motion update, which is
            // where the original puts them (image 0x716e..0x7200: the
            // bottom-gated gravity/snap block precedes the vx seed and the
            // behaviour-3 ledge probe). The order matters: the ledge probe
            // reads a tile row from monster.y, so on the landing tick it must
            // see the SNAPPED y. Running the snap afterwards let a walker
            // landing at y % 8 != 0 probe one row too low and falsely reverse
            // on a platform that continues.
            if (recoveredResolution && monster.behavior != 4) {
                const ActiveMonster::EdgeFlags& e = monster.edges;
                if (!e.bottom || monster.vy8 < 0) {
                    monster.vy8 = static_cast<int16_t>(std::min<int>(0x07ff, monster.vy8 + 0x40));
                } else if (monster.vy8 > 0) {
                    monster.vy8 = 0;
                    monster.y &= ~7;
                    // Landing tick requests a facing reselect (1000:71A0).
                    monster.facingDirty = true;
                }
            }

            // Behavior 4's dedicated pre-steering floor response
            // (1000:7062..70B9) uses the narrower side-solid class 1..0x4C
            // for the two bottom cells. A strong bottom plus top contact
            // zeroes vy; otherwise a positive vy reflects by -vy/2. The
            // global-clock steering gate follows and may replace that result.
            if (monster.behavior == 4) {
                const bool strongBottom =
                    scanActorStrongBottom(monster.x, monster.y);
                if (strongBottom && monster.edges.top) {
                    monster.vy8 = 0;
                }
                if (strongBottom && monster.vy8 > 0) {
                    monster.vy8 = static_cast<int16_t>(-(monster.vy8 / 2));
                }
            }

            updateMonsterMotion(monster, dt);

            // Boss segments (behavior 5) are positioned purely by their
            // motion links in the original and pass through terrain. The boss
            // head (behavior 6) is excluded too: 1000:5CB0 does its own
            // four-edge scan and reflects there, keeping the 8.8 fraction.
            if (recoveredResolution) {
                // The facing consume (1000:727D, reselect branches
                // 1000:7286/72DA) sits BEFORE the wall reflection in the
                // instruction stream, so a wall tick consumes the flag with
                // the PRE-reflection vx and re-selects the OLD facing set --
                // an unconditional cursor reset to that set's base -- while
                // the NEW set is selected on the following tick, when the
                // renormalisation (1000:71F3) raises the flag again with the
                // reversed vx. The capture adjudicates the order: walker A's
                // wall tick 374 has the renorm tick 375 land before the next
                // advance tick 376, so its flip shows at row 377 (the next
                // boundary), but walker B's wall tick 481 is immediately
                // followed by the advance tick 482, whose prologue still
                // steps the OLD right pair (46 at row 483, 3/3 wall turns);
                // the left pair only appears at row 487. Reselecting after
                // the reflection flips one boundary early in B's phase.
                if (monster.behavior == 3 && monster.facingDirty) {
                    reselectWalkerFacing(monster);
                    monster.facingDirty = false;
                }
                const ActiveMonster::EdgeFlags e = monster.edges;
                if (e.top && monster.vy8 < 0) monster.vy8 = 1;
                if (e.left && e.right) {
                    monster.vx8 = 0;
                } else if ((e.left && monster.vx8 < 0) || (e.right && monster.vx8 > 0)) {
                    monster.vx8 = static_cast<int16_t>(-monster.vx8 / 2);
                    monster.x += monster.vx8 < 0 ? -1 : 1;
                }
                integrateAxis8_8(monster.y, monster.fracY, monster.vy8);
                integrateAxis8_8(monster.x, monster.fracX, monster.vx8);
            } else {
                integrateAxis8_8(monster.x, monster.fracX, monster.vx8);
                integrateAxis8_8(monster.y, monster.fracY, monster.vy8);
            }

            monster.x = std::clamp(monster.x, 0, std::max(16, level_.width * 8 - 16));
            monster.y = std::clamp(monster.y, 0, std::max(16, level_.height * 8 - 16));
            if (monster.kind >= 1 && monster.kind <= 8) {
                int damage = 0;
                // 1000:7427 calls 56B6 using the pre-motion 2x2 footprint.
                for (int dy = 0; dy < 2; ++dy) for (int dx = 0; dx < 2; ++dx) {
                    const int glyph = tileAt(damageColumn + dx, damageRow + dy);
                    if (glyph == 0x75) damage += 2;
                    else if (glyph >= 1 && glyph <= 0x4c) ++damage;
                }
                if (damage) damageMonster(monster, damage, true);
            }
        }
        monsters_.erase(std::remove_if(monsters_.begin(), monsters_.end(),
                                       [](const ActiveMonster& monster) { return !monster.alive; }),
                        monsters_.end());
    }

void GameSession::releaseMonsterSlot(ActiveMonster& monster) {
        if (!monster.hasSpawner || monster.deathCredited) return;
        if (monster.spawnerIndex < spawnerStates_.size()) {
            ++spawnerStates_[monster.spawnerIndex].availableSlots;
            monster.deathCredited = true;
            monster.hasSpawner = false;
        }
    }
}
