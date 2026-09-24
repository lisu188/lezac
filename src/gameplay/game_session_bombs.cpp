#include "gameplay/game_session.hpp"
#include "gameplay/motion_math.hpp"
#include "core/progress.hpp"
#include <cmath>

namespace lezac::gameplay {
using namespace lezac::core;
using detail::clampI16;
using detail::integrateAxis8_8;

void GameSession::placeBombAt(const Player& player, BombInventory& inventory, uint8_t owner) {
        // 1000:6C00 leaves an empty selection and both fire latches unchanged.
        if (!hasBomb(inventory, inventory.selected)) return;
        // Both latches are consumed after a constructor attempt, even when
        // the shared actor pool rejects it (1000:6CA9..6CAE).
        reentryFire1_ = reentryFire2_ = false;
        if (sharedActorCount() >= 30) return;
        // Original pixel->tile mapping, from the blast routine at 655B..6582
        // (re-read this session: base = ((py>>3)-1)*width + (((px+4)>>3)-1))
        // plus the burn walk at 6CB8..6D1B, whose consumed 2x2 block has its
        // top-left tile at ((px+4)>>3, py>>3). The L2 capture pins the
        // arithmetic: player pixel (200,308) at drop -> base 3724 and
        // post-walk DS:C1E8 = 3925, exactly as measured. The identification
        // of initial bomb pixels with player pixels is also explicit in the
        // constructor call at 1000:6C25..6C5B. Motion refreshes these tile
        // coordinates from the bomb's own pixels before detonation.
        int tx = (static_cast<int>(player.x) + 4) / 8;
        int ty = static_cast<int>(player.y) / 8;
        BombProfile profile = bombProfile(inventory.selected);
        // First update is on the frame after construction. Encode the
        // odd-frame byte countdown as remaining game ticks.
        int timer = profile.fuseTicks - static_cast<int>((logicTick_ + 1) & 1u);
        const uint64_t actorOrder = claimActorOrder();
        bombs_.push_back({tx, ty, timer, inventory.selected, profile.fuseTicks, owner});
        Bomb& bomb = bombs_.back();
        bomb.actorOrder = actorOrder;
        bomb.pixelX = static_cast<int>(player.x);
        bomb.pixelY = static_cast<int>(player.y);
        // 6C2B..6C41 scales vx by 3/2 (signed truncation), and subtracts
        // 500 from vy. The actor constructor clamps each to +/-0x07ff
        // and clears both fractional accumulators.
        bomb.vx8 = static_cast<int16_t>(std::clamp(3 * player.vx8 / 2, -0x07ff, 0x07ff));
        bomb.vy8 = static_cast<int16_t>(std::clamp(player.vy8 - 500, -0x07ff, 0x07ff));
        bomb.moving = true;
        requestBombPlaceSound();
        --inventory.counts[static_cast<size_t>(bombTypeIndex(inventory.selected))];
    }

int GameSession::bombHeightOffset(BombType type) const {
        const size_t sprite = bombProfile(type).spriteBase;
        return 16 - sprites_.sprites.at(sprite).height;
    }

void GameSession::updateBombMotion(Bomb& bomb) {
        if (!bomb.moving) return;
        const int heightOffset = bomb.hotspotY >= 0 ? bomb.hotspotY : bombHeightOffset(bomb.type);
        int collideY = bomb.pixelY - heightOffset;
        ActiveMonster::EdgeFlags edges;
        if (bomb.type == BombType::Small) {
            // 1000:65DA..6640 selects four single cells for actor kind 0x0d.
            // Other bombs use the usual two-cell actor edges.
            const int column = (bomb.pixelX + 4) >> 3;
            const int row = collideY >> 3;
            edges.top = solidTileSide(static_cast<uint8_t>(tileAt(column, row)));
            edges.bottom = solidTileBottom(static_cast<uint8_t>(tileAt(column, row + 2)));
            edges.left = solidTileSide(static_cast<uint8_t>(tileAt(column - 1, row + 1)));
            edges.right = solidTileSide(static_cast<uint8_t>(tileAt(column + 1, row + 1)));
        } else {
            edges = scanActorEdges(bomb.pixelX, collideY);
        }
        updateTimedActorMotion(bomb.pixelX, collideY, bomb.vx8, bomb.vy8,
                               bomb.fracX, bomb.fracY, edges);
        bomb.pixelY = collideY + heightOffset;
        // 1000:75E3 uses visual X directly, without the collision-scan +4.
        bomb.x = bomb.pixelX >> 3;
        bomb.y = bomb.pixelY >> 3;
    }

void GameSession::updateTimedActorMotion(int& x, int& y, int16_t& vx, int16_t& vy, uint8_t& fracX, uint8_t& fracY, const ActiveMonster::EdgeFlags& edges) {
        if (!edges.bottom || vy < 0) vy = static_cast<int16_t>(std::min(0x07ff, vy + 0x40));
        else if (vy > 0) {
            vy = 0;
            y &= ~7;
        }
        if (edges.bottom) vx = actorFloorFriction(vx);
        if (edges.top && vy < 0) vy = 1;
        if (edges.left && edges.right) vx = 0;
        else if ((edges.left && vx < 0) || (edges.right && vx > 0)) {
            vx = static_cast<int16_t>(-vx / 2);
            x += vx < 0 ? -1 : 1;
        }
        integrateAxis8_8(y, fracY, vy);
        integrateAxis8_8(x, fracX, vx);
    }

void GameSession::updateBombs(uint64_t onlyOrder) {
        std::vector<Bomb> expired;
        for (Bomb& b : bombs_) {
            if (onlyOrder && b.actorOrder != onlyOrder) continue;
            updateBombMotion(b);
            if (--b.timer <= 0) expired.push_back(b);
        }
        bombs_.erase(std::remove_if(bombs_.begin(), bombs_.end(),
                                    [onlyOrder](const Bomb& b) { return b.timer <= 0 && (!onlyOrder || b.actorOrder == onlyOrder); }),
                     bombs_.end());
        int generation = levelResetGeneration_;
        for (const Bomb& b : expired) {
            if (levelResetGeneration_ != generation) break;
            explode(b);
        }
    }

std::vector<std::array<int, 2>> GameSession::explosionTilesFor(const Bomb& bomb) const {
        std::vector<std::array<int, 2>> tiles;
        auto add = [&](int x, int y) {
            if (x < 0 || y < 0 || x >= level_.width || y >= level_.height) return;
            std::array<int, 2> pos{x, y};
            if (std::find(tiles.begin(), tiles.end(), pos) == tiles.end()) {
                tiles.push_back(pos);
            }
        };
        add(bomb.x, bomb.y);
        add(bomb.x + 1, bomb.y);
        add(bomb.x + 1, bomb.y + 1);
        add(bomb.x, bomb.y + 1);
        return tiles;
    }

void GameSession::spawnExplosionEffect(const Bomb& bomb) {
        if (explosionVisualType(bomb.type) > 1) cameraShakeTicks_ = 2;  // 1000:4164
        int visualType = explosionVisualType(bomb.type);
        int ticks = explosionEffectTicks(visualType);
        ExplosionEffect effect;
        effect.x = bomb.x;
        effect.y = bomb.y;
        effect.visualSelector = static_cast<uint8_t>(visualType);
        effect.dispatcherState = explosionDispatcherState(visualType);
        effect.timer = ticks;
        effect.totalTimer = ticks;
        effect.soundOffset = explosionSoundOffset(visualType);
        effect.soundSelector = explosionSoundSelector(visualType);
        effect.seedTicksByte = static_cast<uint8_t>(ticks & 0xff);
        effect.variantByte = explosionVariantByte(visualType);
        effect.computedX = bomb.x * kTileSize;
        effect.computedY = bomb.y * kTileSize;
        explosionEffects_.push_back(effect);
        seedFlameRecords(bomb.y * level_.width + bomb.x, visualType);
        requestSoundOffset(effect.soundOffset, effect.soundSelector);
    }
}
