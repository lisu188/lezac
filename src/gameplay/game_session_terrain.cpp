#include "gameplay/game_session.hpp"
#include "gameplay/motion_math.hpp"
#include "core/progress.hpp"
#include <cmath>

namespace lezac::gameplay {
using namespace lezac::core;
using detail::clampI16;
using detail::integrateAxis8_8;

void GameSession::seedFlameRecords(int cell, int type) {
        // Exact finite constructor outputs. Turbo Pascal's real48 sine/cosine
        // and truncation produce asymmetric bytes, including 79 rather than 80.
        static const std::array<std::vector<std::array<int, 2>>, 4> velocities{{
            {{79,0},{56,-56},{0,-79},{-56,-56},{-79,0},{-56,56},{0,79},{56,56}},
            {{109,0},{95,-54},{55,-95},{0,-109},{-54,-95},{-95,-55},
             {-109,0},{-95,54},{-55,95},{0,109},{54,95},{95,55}},
            {{109,0},{101,-41},{79,-76},{44,-100},{3,-109},{-37,-103},
             {-73,-81},{-98,-48},{-109,-7},{-104,33},{-84,70},{-51,97},
             {-11,109},{30,105},{67,86},{95,55},{108,15}},
            {{0,-125},{-32,-121},{-62,-109},{-88,-89},{-109,-63},{-121,-32},{-125,0},
             {125,0},{121,-32},{109,-62},{89,-89},{63,-109},{32,-121},
             {-125,0},{-121,32},{-109,62},{-89,88},{-63,108},{-32,121},{0,125},
             {21,124},{52,114},{80,96},{103,72},{118,43},{125,11}},
        }};
        if (type < 1 || type > 4) return;
        const auto& rays = velocities[static_cast<size_t>(type - 1)];
        for (size_t i = 0; i < rays.size() && flameRecords_.size() < 198; ++i) {
            int origin = cell;
            if (type == 4) {
                if (i >= 20) origin += level_.width + 1;
                else if (i >= 13) origin += level_.width;
                else if (i >= 7) ++origin;
            }
            FlameRecord record;
            record.cell = static_cast<uint16_t>(origin);
            record.vx = static_cast<int8_t>(rays[i][0]);
            record.vy = static_cast<int8_t>(rays[i][1]);
            record.timer = static_cast<uint8_t>(explosionEffectTicks(type));
            record.variant = explosionVariantByte(type);
            record.mass = static_cast<uint8_t>(type == 4 ? 221 : type == 3 ? 9 : 1);
            flameRecords_.push_back(record);
        }
    }

void GameSession::updateFlameRecords() {
        auto object = [&](int cell) -> uint8_t {
            return cell >= 0 && static_cast<size_t>(cell) < level_.tiles.size() ? level_.tiles[cell] : 1;
        };
        auto stamp = [&](int cell, uint8_t value) {
            if (cell >= 0 && static_cast<size_t>(cell) < level_.tiles.size()) level_.tiles[cell] = value;
        };
        // Descending live slots. New chain-reaction records wait until next pass.
        for (size_t slot = flameRecords_.size(); slot > 0; --slot) {
            const size_t index = slot - 1;
            FlameRecord ray = flameRecords_[index];
            int delta = 0;
            auto integrate = [&](int8_t velocity, int8_t& fraction, int step) {
                int sum = fraction + velocity;
                if (sum > 127 || sum < -128) {
                    sum += sum > 127 ? -128 : 128;
                    delta += velocity < 0 ? -step : step;
                }
                fraction = static_cast<int8_t>(sum);
            };
            integrate(ray.vx, ray.subX, 1);
            integrate(ray.vy, ray.subY, level_.width);
            if (delta != 0) {
                const int target = static_cast<uint16_t>(ray.cell + delta);
                const uint8_t code = object(target);
                uint16_t word = wordAt(target % level_.width, target / level_.width);
                if (code == 0x66) {
                    // 1000:468E: consume the chain tile even when the pool is full.
                    stamp(target, word > 0x7fff ? 0xff : 0);
                    if (word <= 0x7fff && static_cast<size_t>(target) < level_.wordLayer.size()) {
                        level_.wordLayer[target] = 0;
                        word = 0;
                    }
                    seedFlameRecords(target, 1);
                    requestSoundOffset(explosionSoundOffset(1), explosionSoundSelector(1));
                }
                if (code == 0 || code == 0x75) {
                    if (object(ray.cell) == 0x75) stamp(ray.cell, 0);
                    stamp(target, ray.glyph);
                    ray.cell = static_cast<uint16_t>(target);
                } else if (word != 0) {
                    if ((word & kDamagedWordBit) == 0) {
                        queueTileDamage(target % level_.width, target / level_.width, 0, 0, true);
                    }
                    const auto match = resolveDamagePhase(static_cast<uint16_t>(word | kDamagedWordBit), false);
                    if (match.slotIndex != 0) {
                        const size_t other = static_cast<size_t>(match.slotIndex - 1);
                        const int weight = match.debris ? 1 : collapseQueue_[other].affectedBytes;
                        auto blend = [&](int own, int incoming) {
                            const int16_t numerator = static_cast<int16_t>(own * ray.mass + incoming * weight);
                            return static_cast<int8_t>(numerator / (ray.mass + weight));
                        };
                        if (match.debris) {
                            auto& debris = debrisQueue_[other];
                            debris.velocityX = blend(ray.vx, debris.velocityX);
                            debris.velocityY = blend(ray.vy, debris.velocityY);
                            if ((word & kDamagedWordBit) != 0 && ray.variant > 0) stamp(target, 0xff);
                        } else {
                            auto& collapse = collapseQueue_[other];
                            collapse.forwardPhase = static_cast<uint8_t>(blend(ray.vx, static_cast<int8_t>(collapse.forwardPhase)));
                            collapse.reversePhase = static_cast<uint8_t>(blend(ray.vy, static_cast<int8_t>(collapse.reversePhase)));
                        }
                    }
                }
            }
            if (ray.variant > 0) --ray.variant;
            --ray.timer;
            if (ray.timer == 0) {
                if (object(ray.cell) == 0x75) stamp(ray.cell, 0);
                flameRecords_.erase(flameRecords_.begin() + static_cast<std::ptrdiff_t>(index));
            } else flameRecords_[index] = ray;
        }
    }

bool GameSession::requestBombObjectScoreSound(bool sawHighObjectTile) {
        return requestSoundCursor(sawHighObjectTile ? kBombObjectHighSoundCursor
                                                    : kBombObjectDefaultSoundCursor,
                                  kBombObjectSoundPriority);
    }

bool GameSession::requestBombPlaceSound() {
        return requestSoundOffset(kBombPlaceSoundCursor, kBombPlaceSoundPriority);
    }

bool GameSession::requestMonsterDeathSound() {
        return requestSoundCursor(kMonsterDeathSoundCursor, kMonsterDeathSoundPriority);
    }

bool GameSession::requestWeaponSwitchSound() {
        return requestSoundCursor(kWeaponSwitchSoundCursor, kWeaponSwitchSoundPriority);
    }

bool GameSession::requestLaunchPadSound() {
        return requestSoundCursor(kLaunchPadSoundCursor, kLaunchPadSoundPriority);
    }

bool GameSession::requestPortalTeleportSound() {
        return requestSoundCursor(kPortalTeleportSoundCursor, kPortalTeleportSoundPriority);
    }

bool GameSession::requestTileTriggerSound() {
        return requestSoundCursor(kTileTriggerSoundCursor, kTileTriggerSoundPriority);
    }

bool GameSession::requestPlayerDamageSound() {
        return requestSoundCursor(kPlayerDamageSoundCursor, kPlayerDamageSoundPriority);
    }

bool GameSession::requestPlayerDeathSound() {
        return requestSoundCursor(kPlayerDeathSoundCursor, kPlayerDeathSoundPriority);
    }

void GameSession::blendDebrisImpactLane(int target, uint16_t word, int& velocity, bool reverse) {
        if ((word & kDamagedWordBit) == 0) {
            const size_t debrisBefore = debrisQueue_.size();
            const size_t collapseBefore = collapseQueue_.size();
            // Collision seeding leaves the object plane intact (original
            // new_collapse probe); older explosion playback marks it early.
            queueTileDamage(target % level_.width, target / level_.width, 0, 0, true);
            // 3C2D / 3DC1 return without writing the caller on seeder failure.
            if (debrisBefore == debrisQueue_.size() &&
                collapseBefore == collapseQueue_.size()) return;
        }
        const DamagePhaseLookup match = resolveDamagePhase(
            static_cast<uint16_t>(word | kDamagedWordBit), reverse);
        // The original expects a matching live record. Stale flagged map
        // cells in the reconstruction must not become an invalid table write.
        if (match.slotIndex == 0) return;
        const size_t index = static_cast<size_t>(match.slotIndex - 1);
        const int weight = match.debris ? 1 : collapseQueue_[index].affectedBytes;
        const int other = static_cast<int8_t>(match.phase);
        velocity = (velocity + other * weight) / (1 + weight);
        if (match.debris) {
            if (reverse) debrisQueue_[index].velocityY = static_cast<int8_t>(velocity);
            else debrisQueue_[index].velocityX = static_cast<int8_t>(velocity);
        } else {
            if (reverse) collapseQueue_[index].reversePhase = static_cast<uint8_t>(velocity);
            else collapseQueue_[index].forwardPhase = static_cast<uint8_t>(velocity);
        }
    }

void GameSession::explode(const Bomb& bomb) {
        spawnExplosionEffect(bomb);
        TransientActor fade;
        fade.x = bomb.pixelX;
        fade.y = bomb.pixelY;
        fade.kind = 0;
        fade.timer = 18;
        fade.fracX = bomb.fracX;
        fade.fracY = bomb.fracY;
        fade.spriteIndex = 68;
        fade.animation = ActorAnimation::initialize(69, 79, 2, 1);
        fade.actorOrder = bomb.actorOrder;
        fade.bossVisualOrder = bomb.bossVisualOrder;
        transientActors_.push_back(fade);
        spawnExpiryParticles(bomb.pixelX, bomb.pixelY, bombTypeIndex(bomb.type) + 2);
    }

void GameSession::updateDebrisRecords() {
        // Loop-2 emptiness gate (4934 cmp DS:207E,0xC8 / jb exit).
        if (debrisQueue_.empty()) return;
        const int width = level_.width;
        if (width <= 0 || level_.tiles.empty()) return;
        const int cellCount = static_cast<int>(level_.tiles.size());
        // The original never indexes outside the map (levels ship with solid
        // borders); the port clamps instead: out-of-range object bytes read as
        // solid (blocking moves and supporting fragments), out-of-range words
        // read 0, and out-of-range writes are dropped.
        auto objectByteAt = [&](int index) -> uint8_t {
            return index >= 0 && index < cellCount
                       ? level_.tiles[static_cast<size_t>(index)]
                       : uint8_t{0x01};
        };
        auto setObjectByte = [&](int index, uint8_t value) {
            if (index >= 0 && index < cellCount) {
                level_.tiles[static_cast<size_t>(index)] = value;
            }
        };
        auto wordCellAt = [&](int index) -> uint16_t {
            return index >= 0 &&
                           static_cast<size_t>(index) < level_.wordLayer.size()
                       ? level_.wordLayer[static_cast<size_t>(index)]
                       : uint16_t{0};
        };
        auto setWordCell = [&](int index, uint16_t value) {
            if (index >= 0 && static_cast<size_t>(index) < level_.wordLayer.size()) {
                level_.wordLayer[static_cast<size_t>(index)] = value;
            }
        };

        // Ascending slot order with the bound re-read live every iteration
        // (4947 re-reads DS:207E): a record seeded mid-pass by a cascade IS
        // updated later in this same tick (CONFIRMED by the L2 capture,
        // frame 404). Removal (458D) shifts the survivors down and rewinds
        // the caller's counter, which a vector erase without ++i reproduces.
        for (size_t i = 0; i < debrisQueue_.size();) {
            // Slot number as the original counts it: [bp-2] starts at 0xC8.
            const int slot = static_cast<int>(kDebrisRecordIndexBase) + 1 +
                             static_cast<int>(i);
            // Lane load 4950..49A1 (DS:78D2/78D3/78D4/78D5).
            int pos = debrisQueue_[i].tileIndex;
            int vx = debrisQueue_[i].velocityX;
            int vy = debrisQueue_[i].velocityY;
            int subX = debrisQueue_[i].subX;
            int subY = debrisQueue_[i].subY;
            uint8_t code = debrisQueue_[i].lookup;
            const uint16_t fw = debrisQueue_[i].flaggedWord;

            // Fragile-word auto-shatter 49A4..49C8: raw words 0x7FBD..0x7FFF
            // shatter even without a landing when still carrying a non-shatter
            // glyph.
            if (fw > kDebrisFragileWordFloor && code <= 0x66) {
                code = kDebrisShatterFrame;
                debrisQueue_[i].lookup = code;
                requestSoundCursor(kDebrisAutoShatterSoundCursor,
                                   kDebrisAutoShatterSoundPriority);
            }

            // Shatter frame stepper 49CB..4A18: one frame per tick; reaching
            // 0x79 picks the terminal glyph (0x6B+Random(5) for fragile words,
            // else 0xFF which dissolves through the consume path below); the
            // object plane is restamped every tick while code >= 0x76.
            if (code >= kDebrisShatterFrame) {
                code = static_cast<uint8_t>(code + 1);
                if (code == kDebrisShatterLastStep) {
                    code = fw > kDebrisFragileWordFloor
                               ? static_cast<uint8_t>(kDebrisTerminalBase +
                                                      randomRangeValue(0, 5))
                               : kDebrisDissolveByte;
                }
                debrisQueue_[i].lookup = code;
                setObjectByte(pos, code);
            }

            // 0xFF consume 4A1B..4A75: the fragment dissolves (both planes
            // cleared) and the cell above is re-seeded through the seeder
            // (guard 4A5B is word > 0 only; the seeder rejects the rest).
            if (objectByteAt(pos) == kDebrisDissolveByte) {
                setObjectByte(pos, 0);   // 4A31
                setWordCell(pos, 0);     // 4A49
                debrisQueue_.erase(debrisQueue_.begin() +
                                   static_cast<std::ptrdiff_t>(i));  // 4A39 -> 458D
                const int above = pos - width;
                if (above >= 0 && wordCellAt(above) > 0) {           // 4A5B
                    queueTileDamage(above % width, above / width);   // 4A72 -> 370E
                }
                continue;
            }

            // Integrator 3EDA (called at 4A81): per axis, a signed 8-bit
            // sub-accumulator gains v; on signed overflow it loses 0x80 and
            // the move delta gains one tile in v's direction. x axis first,
            // then y; both can step in the same tick (diagonal move).
            int delta = 0;
            auto integrateAxis = [&](int v, int& sub, int unitMagnitude) {
                const int unit = v < 0 ? -unitMagnitude : unitMagnitude;  // 3EE4/3F0B
                int sum = sub + v;                                        // 3EEB/3F11
                if (sum > 127) {          // 3EED/3F13 jno (signed overflow)
                    sum -= 128;           // 3EEF/3F15 sub 0x80
                    delta += unit;        // 3EF2/3F18
                } else if (sum < -128) {
                    sum += 128;
                    delta += unit;
                }
                sub = sum;
            };
            integrateAxis(vx, subX, 1);
            integrateAxis(vy, subY, width);
            bool resting = delta == 0;  // 4A84..4A8B

            // Support / gravity / friction / landing shatter 4A93..4B32,
            // keyed on the object byte directly below (4A9D).
            if (objectByteAt(pos + width) == 0) {
                // Unsupported: gravity +4 while vy < 0x7B signed (so the
                // attainable terminal value from a zero start is 0x7C), and
                // the rest counter resets every airborne tick (4AB3).
                if (vy < kDebrisGravityCompare) vy += kDebrisGravityStep;
                debrisQueue_[i].restTicks = 0;
            } else {
                if (!resting) {
                    // Horizontal friction 4AC0..4AE2, only on ticks whose
                    // integrator produced a step.
                    if (vx > 0) {
                        --vx;
                    } else if (vx < 0) {
                        ++vx;
                    }
                }
                // Landing shatter 4AE6..4B32. The dice is
                // (DS:78C2 + slot) mod 6 — a frame counter, not the RNG; the
                // port's logicTick_ stands in for DS:78C2 (INFERRED @unevidenced:debris_shatter_dice_phase,
                // equivalence, phase not pinned against the original).
                if (vy > 0 && vy > kDebrisLandingShatterVyGate && code > 0x66 &&
                    (logicTick_ + static_cast<uint32_t>(slot)) % 6u > 2u) {
                    setObjectByte(pos, kDebrisShatterFrame);  // 4B16
                    debrisQueue_[i].lookup = kDebrisShatterFrame;
                    code = kDebrisShatterFrame;
                    requestSoundCursor(kDebrisLandingShatterSoundCursor,
                                       kDebrisLandingShatterSoundPriority);
                }
            }

            // Move 4B35..4CB5.
            if (delta != 0) {
                const int dest = pos + delta;
                if (objectByteAt(dest) == 0) {
                    // Free move 4B61..4C1D: the fragment is materialized at
                    // the destination in BOTH planes and erased from the
                    // vacated cell — these stamps happen on every free move,
                    // not on rest.
                    debrisQueue_[i].restTicks = 0;  // 4B6E
                    setObjectByte(dest, code);      // 4B7E
                    setObjectByte(pos, 0);          // 4B89
                    setWordCell(dest, fw);          // 4B9B
                    setWordCell(pos, 0);            // 4BAB
                    debrisQueue_[i].tileIndex = dest;  // 4BB5
                    // Cascade 4BB9..4C19: a move that was not straight up
                    // re-seeds the cell above the vacated one when its word
                    // is live and unflagged (words 1..0x3FFF spawn a collapse
                    // record through the same seeder).
                    if (delta != -width) {
                        const int above = pos - width;
                        const uint16_t aboveWord = wordCellAt(above);
                        if (above >= 0 && aboveWord > 0 &&
                            aboveWord < kDamagedWordBit) {  // 4BE4..4BF5
                            queueTileDamage(above % width, above / width);  // 4C08
                            // Set even when the seeder is at capacity (no
                            // DS:79C8 check at 4C0B..4C19). queueTileDamage
                            // may reallocate the queue, so re-index.
                            debrisQueue_[i].aux |= 0x80;
                        }
                    }
                    pos = dest;
                } else {
                    // Blocked move 4C20..4CAC.
                    resting = true;  // 4C20
                    if (vy > 0) {
                        // Bounce 4C24..4C5F: exactly these two RNG draws in
                        // this order, then vy = 0.
                        vx = static_cast<int8_t>(
                            vx + static_cast<int>(randomRangeValue(0, 0x1e)) -
                            15);  // 4C2B/4C41, stored through AL
                        requestSoundOffset(
                            static_cast<uint16_t>(kDebrisBounceSoundBase +
                                                  randomRangeValue(0, 8)),
                            kDebrisBounceSoundPriority);  // 4C4A/4C51/4C57
                        vy = 0;                           // 4C5F
                    }
                    const uint16_t destWord = wordCellAt(dest);  // 4C64..4C75
                    if (destWord == 0) {
                        vx = 0;  // 4CAE
                    } else {
                        blendDebrisImpactLane(dest, destWord, vx, false);  // 4C96
                        // X may have seeded the target. The original forces
                        // its flag for the Y matcher at 4C99 before 4CA9.
                        blendDebrisImpactLane(
                            dest, static_cast<uint16_t>(destWord | kDamagedWordBit),
                            vy, true);
                    }
                }
            }

            // Lane write-back 4CB9..4CEB.
            debrisQueue_[i].velocityX = static_cast<int8_t>(vx);
            debrisQueue_[i].velocityY = static_cast<int8_t>(vy);
            debrisQueue_[i].subX = static_cast<int8_t>(subX);
            debrisQueue_[i].subY = static_cast<int8_t>(subY);

            // 4CF8 increments a byte; 4CFF tests equality with 100. Removal
            // clears only the map flag, leaves the glyph, and rewinds the
            // live loop so the shifted successor is processed this tick.
            // The original leaves stale tail bytes; they do not stay live.
            if (resting) ++debrisQueue_[i].restTicks;
            if (debrisQueue_[i].restTicks == kDebrisRestRetireTicks) {
                setWordCell(pos, static_cast<uint16_t>(wordCellAt(pos) & ~kDamagedWordBit));
                debrisQueue_.erase(debrisQueue_.begin() + static_cast<std::ptrdiff_t>(i));
                continue;
            }
            ++i;
        }
    }

void GameSession::updateCollapseRecords() {
        if (level_.width <= 0 || level_.tiles.empty()) return;
        const int width = level_.width;
        struct Contact { int cell; uint16_t word; };
        struct Scan {
            bool blocked = false;
            int firstColumn = 10000;
            int lastColumn = 0;
            std::vector<Contact> contacts;
        };
        auto mapWord = [&](int cell) -> uint16_t {
            return cell >= 0 && static_cast<size_t>(cell) < level_.wordLayer.size() ?
                level_.wordLayer[static_cast<size_t>(cell)] : 0;
        };
        auto mapTile = [&](int cell) -> uint8_t {
            return cell >= 0 && static_cast<size_t>(cell) < level_.tiles.size() ?
                level_.tiles[static_cast<size_t>(cell)] : 1;
        };
        // 1000:5102 visits the records newest-first. Cascades appended during
        // this pass start moving on the following tick.
        for (size_t remaining = collapseQueue_.size(); remaining > 0; --remaining) {
            const size_t slot = remaining - 1;
            CollapseRecord record = collapseQueue_[slot];
            int first = record.startOffsetBytes / 2;
            int last = record.endOffsetBytes / 2;
            int vx = static_cast<int8_t>(record.forwardPhase);
            int vy = static_cast<int8_t>(record.reversePhase);
            const int incomingX = vx, incomingY = vy;
            bool moved = false;
            auto cells = [&] {
                std::vector<int> result;
                for (int y = first / width; y <= last / width; ++y) {
                    for (int x = first % width; x <= last % width; ++x) {
                        const int cell = y * width + x;
                        if (mapWord(cell) == record.flaggedWord) result.push_back(cell);
                    }
                }
                return result;
            };
            auto scan = [&](int delta) {
                Scan result;
                for (int cell : cells()) {
                    const int target = cell + delta;
                    const uint16_t word = mapWord(target);
                    if (mapTile(target) == 0 || word == record.flaggedWord) continue;
                    result.blocked = true;
                    result.firstColumn = std::min(result.firstColumn, target % width);
                    result.lastColumn = std::max(result.lastColumn, target % width);
                    if (word != 0 && std::none_of(result.contacts.begin(), result.contacts.end(),
                        [&](const Contact& contact) { return contact.word == word; })) {
                        result.contacts.push_back({target, word});
                    }
                }
                return result;
            };
            auto seedAbove = [&] {
                for (const auto& contact : scan(-width).contacts) {
                    if (contact.word < kDamagedWordBit) {
                        queueTileDamage(contact.cell % width, contact.cell / width, 0, 1, true);
                    }
                }
            };
            auto move = [&](int delta) {
                Scan result = scan(delta);
                moved = false;
                if (result.blocked) return result;
                auto source = cells();
                if (delta > 0) std::reverse(source.begin(), source.end());
                for (int cell : source) {
                    const int target = cell + delta;
                    level_.wordLayer[static_cast<size_t>(target)] = mapWord(cell);
                    level_.wordLayer[static_cast<size_t>(cell)] = 0;
                    level_.tiles[static_cast<size_t>(target)] = mapTile(cell);
                    level_.tiles[static_cast<size_t>(cell)] = 0;
                }
                first += delta;
                last += delta;
                moved = true;
                return result;
            };
            auto blend = [&](const Scan& result, int& velocity, bool reverse) {
                int weight = record.affectedBytes;
                int sum = velocity * weight;
                std::vector<DamagePhaseLookup> targets;
                for (const auto& contact : result.contacts) {
                    if ((contact.word & kDamagedWordBit) == 0) {
                        const size_t beforeDebris = debrisQueue_.size();
                        const size_t beforeCollapse = collapseQueue_.size();
                        queueTileDamage(contact.cell % width, contact.cell / width, 0, 0, true);
                        if (beforeDebris == debrisQueue_.size() && beforeCollapse == collapseQueue_.size()) return;
                    }
                    auto match = resolveDamagePhase(static_cast<uint16_t>(contact.word | kDamagedWordBit), reverse);
                    if (match.slotIndex == 0) return;
                    const int contribution = match.debris ? 1 : collapseQueue_[match.slotIndex - 1].affectedBytes;
                    weight += contribution;
                    sum += contribution * static_cast<int8_t>(match.phase);
                    targets.push_back(match);
                }
                if (weight == 0) return;
                velocity = static_cast<int8_t>(sum / weight);
                for (const auto& match : targets) {
                    const size_t index = static_cast<size_t>(match.slotIndex - 1);
                    if (match.debris) {
                        if (reverse) debrisQueue_[index].velocityY = static_cast<int8_t>(velocity);
                        else debrisQueue_[index].velocityX = static_cast<int8_t>(velocity);
                    } else {
                        if (reverse) collapseQueue_[index].reversePhase = static_cast<uint8_t>(velocity);
                        else collapseQueue_[index].forwardPhase = static_cast<uint8_t>(velocity);
                    }
                }
            };
            auto integrate = [](int velocity, int8_t& fraction) {
                int sum = fraction + velocity;
                const bool overflow = sum > 127 || sum < -128;
                if (sum > 127) sum -= 128;
                else if (sum < -128) sum += 128;
                fraction = static_cast<int8_t>(sum);
                return overflow ? (velocity < 0 ? -1 : 1) : 0;
            };
            const int dx = integrate(vx, record.subX);
            if (dx != 0) {
                if ((record.flags & 0x80) == 0) seedAbove();
                else record.flags &= 0x7f;
                const auto result = move(dx);
                if (!result.contacts.empty()) blend(result, vx, false);
            }
            const int dy = integrate(vy, record.subY);
            if (dy != 0) {
                if (dy > 0 && (record.flags & 0x80) == 0) {
                    record.flags |= 0x80;
                    seedAbove();
                } else if (dy < 0) record.flags &= 0x7f;
                const auto result = move(dy * width);
                if (result.blocked && vy > 0) {
                    vy = 0;
                    cameraShakeTicks_ = 3;  // 1000:5388
                    requestSoundOffset(static_cast<uint16_t>(kDebrisBounceSoundBase + randomRangeValue(0, 8)), 1);
                }
                if (!result.contacts.empty()) blend(result, vy, true);
            }
            const auto support = scan(width);
            if (!support.blocked) {
                if (vy < 123) vy += 4;
                moved = true;
                record.flags &= 0xfc;
            } else {
                const int left = first % width, right = last % width;
                const int halfWidth = (right - left) / 2;
                const int centerLeft = left + halfWidth, centerRight = right - halfWidth;
                if (std::abs(vy) < 10 && std::abs(vx) < 30) {
                    if (support.firstColumn > centerLeft && (record.flags & 2) == 0) {
                        if (!scan(-1).blocked) { vx = -15; record.flags |= 1; }
                        else record.flags &= 0xfc;
                    } else if (support.lastColumn < centerRight && (record.flags & 1) == 0) {
                        if (!scan(1).blocked) { vx = 15; record.flags |= 2; }
                        else record.flags &= 0xfc;
                    }
                    if (support.firstColumn <= centerLeft && support.lastColumn >= centerRight) record.flags &= 0xfc;
                }
                if (vx > 0) --vx;
                else if (vx < 0) ++vx;
            }
            if (moved) record.restTicks = 0;
            ++record.restTicks;
            const int magnitude = std::abs(vx) + std::abs(vy);
            const bool fracture = std::abs(static_cast<int>(record.argMagnitude) - magnitude) > 63;
            if (fracture) {
                requestSoundOffset(0xea74, 3);
                for (int cell : cells()) {
                    level_.wordLayer[static_cast<size_t>(cell)] = nextCollapseFragmentWord_++;
                    level_.tiles[static_cast<size_t>(cell)] = static_cast<uint8_t>(0x47 + (logicTick_ & 2));
                    ++destroyed_;
                    const auto x = static_cast<uint8_t>(incomingX + randomRangeValue(0, 20) - 10);
                    const auto y = static_cast<uint8_t>(incomingY - randomRangeValue(0, 40));
                    queueTileDamage(cell % width, cell / width, x, y, true);
                }
                // 1000:558C selects a cell backward from the bottom-right.
                const int actorCell = last - randomRangeValue(0,
                    static_cast<uint16_t>(last % width - first % width + 1));
                spawnTransientActor((actorCell % width) * 8, (actorCell / width) * 8,
                                    0, 74, 0x0b, 8, ActorAnimation::initialize(74, 79, 2, 1));
            }
            if (fracture || record.restTicks == 95) {
                for (int cell : cells()) level_.wordLayer[static_cast<size_t>(cell)] &= ~kDamagedWordBit;
                collapseQueue_.erase(collapseQueue_.begin() + static_cast<std::ptrdiff_t>(slot));
                continue;
            }
            record.startOffsetBytes = static_cast<uint16_t>(first * 2);
            record.endOffsetBytes = static_cast<uint16_t>(last * 2);
            record.x = first % width;
            record.y = first / width;
            record.forwardPhase = static_cast<uint8_t>(vx);
            record.reversePhase = static_cast<uint8_t>(vy);
            record.argMagnitude = static_cast<uint16_t>(magnitude);
            collapseQueue_[slot] = record;
        }
    }

void GameSession::updateFlashes() {
    terrain_effects_.expireVisualEffects();
    updateFlameRecords();
    updateDebrisRecords();
    updateCollapseRecords();
}
}
