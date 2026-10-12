#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace lezac::gameplay {

inline constexpr uint8_t kState2VisualStartFrame = 0x4a;
inline constexpr uint8_t kState2VisualEndFrame = 0x4f;
inline constexpr uint8_t kState2VisualDelay = 3;
inline constexpr int kMonsterCorpseSpriteLeft = 47;
inline constexpr uint8_t kLaunchPadMarkerTimer = 5;
inline constexpr uint8_t kLaunchPadMarkerFrame = 0x5b;
inline constexpr uint8_t kLaunchPadMarkerKind = 0x0b;
inline constexpr uint8_t kLaunchPadMarkerMode = 5;
inline constexpr int16_t kLaunchPadMarkerVelocityY8 = -200;
inline constexpr uint8_t kPortalMarkerFirstFrame = 0x4a;
inline constexpr uint8_t kPortalMarkerLastFrame = 0x4f;
inline constexpr uint8_t kPortalMarkerDelay = 2;
inline constexpr uint8_t kPortalMarkerTimer = 8;

inline constexpr int16_t clampConstructedActorVelocity8(int16_t velocity) {
    // 1000:2FC1..3001: WORD abs(-32768) stays negative and passes JLE.
    if (velocity == -32768) return velocity;
    if (velocity < -0x07ff) return -0x07ff;
    if (velocity > 0x07ff) return 0x07ff;
    return velocity;
}

enum class SharedActorKind { Effect, Marker, Bomb, Monster, Reward };

enum class BombType : uint8_t {
    Small = 0,
    Medium = 1,
    Large = 2,
    Super = 3,
};

struct BombProfile {
    uint8_t actorKind = 0x0d;
    uint8_t spriteBase = 57;
    // Twice the original actor +0x02 seed; placement accounts for the first
    // update's parity. See bomb_fuse_runtime_2026-09-05.md and the eight traces.
    int fuseTicks = 40;
};

struct BombInventory {
    std::array<int, 4> counts{200, 20, 6, 0};
    BombType selected = BombType::Small;
    // DS:1B75 + player: 1 refreshes digits, >1 also refreshes the icon.
    uint8_t hudDirty = 2;
};

struct Bomb {
    int x = 0;
    int y = 0;
    int timer = 40;
    BombType type = BombType::Small;
    int fuseTicks = 40;
    uint8_t owner = 1;
    int pixelX = 0;
    int pixelY = 0;
    int16_t vx8 = 0;
    int16_t vy8 = 0;
    uint8_t fracX = 0;
    uint8_t fracY = 0;
    // Tile-only aggregate probes represent an already-positioned blast.
    // Every gameplay placement enables the original actor motion path.
    bool moving = false;
    // Actor +0x14; -1 derives the constructor value from the selected sprite.
    int8_t hotspotY = -1;
    uint64_t actorOrder = 0;
    uint64_t bossVisualOrder = 0;
};

struct Flash {
    int x = 0;
    int y = 0;
    int timer = 12;
    uint8_t power = 1;
};

struct ActorAnimation {
    uint8_t current = 2;
    uint8_t first = 2;
    uint8_t last = 9;
    uint8_t counter = 1;
    uint8_t delay = 1;
    uint8_t mode = 1;
    int8_t step = 1;

    std::array<uint8_t, 7> packed() const {
        return {current, first, last, counter, delay, mode, static_cast<uint8_t>(step)};
    }

    static ActorAnimation initialize(uint8_t first, uint8_t last, uint8_t delay, uint8_t mode) {
        return {first, first, last, delay, delay, mode, 1};
    }

    bool advance(const ActorAnimation& backup) {
        // 1000:6078..615A advances before the actor's behavior/input branch.
        if (mode == 0 || ++counter <= delay) return false;
        counter = 0;
        current = static_cast<uint8_t>(current + step);
        if (mode == 2) {
            if (current >= last || current <= first) step = static_cast<int8_t>(-step);
        } else if (current > last) {
            current = first;
            if (mode == 3) *this = backup;
        }
        return true;
    }
};

struct LaunchPadMarker {
    int x = 0;
    int y = 0;
    uint8_t fracX = 0;
    uint8_t fracY = 0;
    int16_t velocityX8 = 0;
    int16_t velocityY8 = kLaunchPadMarkerVelocityY8;
    uint8_t timer = kLaunchPadMarkerTimer;
    uint8_t frame = kLaunchPadMarkerFrame;
    uint8_t kind = kLaunchPadMarkerKind;
    uint8_t mode = kLaunchPadMarkerMode;
    uint64_t actorOrder = 0;
    ActorAnimation animation{0, 0, 0, 0, 0, 0, 1};
};

inline bool advanceLaunchPadMarker(LaunchPadMarker& marker, const ActorAnimation& backup, uint32_t logicTick) {
    const bool advanced = marker.animation.advance(backup);
    if (advanced) marker.frame = marker.animation.current;
    marker.timer = static_cast<uint8_t>(marker.timer - (logicTick & 1u));
    if (marker.timer == 0) return advanced;
    const int x = marker.fracX + marker.velocityX8;
    const int y = marker.fracY + marker.velocityY8;
    marker.x = static_cast<int16_t>(marker.x + (x >> 8));
    marker.y = static_cast<int16_t>(marker.y + (y >> 8));
    marker.fracX = static_cast<uint8_t>(x);
    marker.fracY = static_cast<uint8_t>(y);
    return advanced;
}

struct TransientActor {
    int x = 0;
    int y = 0;
    int16_t vx8 = 0;
    int16_t vy8 = 0;
    uint8_t fracX = 0;
    uint8_t fracY = 0;
    uint8_t kind = 0x0a;
    uint8_t timer = 12;
    uint8_t hotspotY = 0;
    uint8_t spriteIndex = 0;
    ActorAnimation animation{0, 0, 0, 0, 0, 0, 1};
    uint64_t actorOrder = 0;
    uint64_t bossVisualOrder = 0;
    ActorAnimation animationBackup{0, 0, 0, 0, 0, 0, 0};
};

inline bool advanceTransientActor(TransientActor& actor, uint32_t logicTick) {
    const bool advanced = actor.animation.advance(actor.animationBackup);
    if (advanced) actor.spriteIndex = static_cast<uint8_t>(actor.animation.current - 1);
    actor.timer = static_cast<uint8_t>(actor.timer - (logicTick & 1u));
    if (actor.timer == 0) return advanced;
    const int y = actor.fracY + actor.vy8;
    const int x = actor.fracX + actor.vx8;
    actor.y = static_cast<int16_t>(actor.y + (y >> 8));
    actor.x = static_cast<int16_t>(actor.x + (x >> 8));
    actor.fracY = static_cast<uint8_t>(y);
    actor.fracX = static_cast<uint8_t>(x);
    return advanced;
}

struct Player {
    float x = 24.0f;
    float y = 24.0f;
    // vx/vy are float MIRRORS of the 8.8 fixed-point velocities below, kept
    // so the many call sites that test a sign or print a magnitude keep
    // working. The authoritative state is vx8/vy8 plus the fractional carry;
    // motion is integrated once per tick with integrateAxis8_8, exactly as
    // monsters, boss links, debris and launch-pad markers already are.
    float vx = 0.0f;
    float vy = 0.0f;
    int16_t vx8 = 0;
    int16_t vy8 = 0;
    uint8_t fracX = 0;
    uint8_t fracY = 0;
    bool grounded = false;
    ActorAnimation animation;
    ActorAnimation animationBackup{0, 0, 0, 0, 0, 0, 0};
    uint8_t idleTicks = 0;
    uint8_t spriteIndex = 0;
    uint16_t dropTicks = 0;
    bool singlePixelSprite = false;
};

inline constexpr std::array<uint8_t, 2> monsterAnimationSelectors(uint8_t kind) {
    // DS:0080/0081 pairs used by the shipped kind-1..4 constructors.
    switch (kind) {
        case 1: return {1, 2};
        case 2: return {11, 11};
        case 3: return {12, 12};
        case 4: return {13, 13};
        default: return {11, 11};
    }
}

inline constexpr std::array<int, 2> monsterAnimationSetRange(uint8_t selector) {
    // DS:0058 pairs are one-based; the port's sprite indexes are zero-based.
    switch (selector) {
        case 1: return {43, 44};
        case 2: return {45, 46};
        case 11: return {39, 41};
        case 12: return {49, 51};
        case 13: return {53, 55};
        default: return {39, 41};
    }
}

struct ActiveMonster {
    int x = 0;
    int y = 0;
    int16_t vx8 = 0;
    int16_t vy8 = 0;
    uint8_t fracX = 0;
    uint8_t fracY = 0;
    uint8_t kind = 0;
    // Original actor +3/+4, retained independently of the animation cursor.
    uint8_t animationSetLeft = 0;
    uint8_t animationSetRight = 0;
    uint8_t behavior = 0;
    uint16_t ai0 = 0;
    uint16_t ai1 = 0;
    uint16_t ai2 = 0;
    uint8_t animFrame = 0;
    // Latched before kind changes to 0x0c; later bounces do not change the sprite.
    uint8_t corpseSprite = kMonsterCorpseSpriteLeft;
    uint8_t animStart = 0;
    uint8_t animEnd = 0;
    uint8_t animDelay = 0;
    uint8_t animMode = 1;
    int8_t animStep = 1;
    // Recovered original animation cursor (actor anim struct +0x00). The
    // per-tick advance steps THIS value; animFrame is the VISIBLE sprite (the
    // visual-table word), rewritten only on advance ticks (1000:60E8..6103).
    // A facing reselection resets the cursor to the new range base without
    // touching animFrame, so the flip becomes visible at the next boundary.
    uint8_t animCursor = 0;
    ActorAnimation animationBackup{0, 0, 0, 0, 0, 0, 0};
    // Original actor byte +0x14: the collision-space y is visual_y - hotspotY
    // (1000:629D `mov al,es:[di+0x14]; cbw; ... sub`). monster.y stores the
    // COLLISION-space y; rendering adds hotspotY back. Value 6 for kind 1 is
    // uniquely forced by the motion lockstep (2370/2370 vs <=14/2370 for every
    // other value 0..22); other kinds are unevidenced and keep 0.
    int8_t hotspotY = 0;
    // Per-tick facing-reselect request, mirroring the original's [bp-0x20]
    // flag: seeded from wall contact at behaviour-3 dispatch (1000:7159..716B),
    // set again on the landing snap (1000:71A0) and on the grounded vx
    // renormalisation (1000:71F3), consumed at 1000:727D.
    bool facingDirty = false;
    size_t spawnerIndex = 0;
    bool hasSpawner = false;
    int hp = 1;
    // Normal corpses store remaining updates, not the original half-rate byte.
    int stateTimer = 0;
    int motionTimer = 0;
    // Recovered original 2x2 tile-cell edge scan, computed once per tick from
    // the PRE-integration position by the caller (updateMonsters).
    struct EdgeFlags { bool top = false, bottom = false, left = false, right = false; };
    EdgeFlags edges;
    int animTick = 0;
    bool deathCredited = false;
    bool deathRewardPending = false;
    bool alive = true;
    // Level-7 boss fields recovered from the GRAN.MST static consumer model:
    // kind 0x1e runs the original 1000:5CB0 head brain (behavior/state 6) and
    // kind 0x1f segments follow DS:0x79EA motion links (behavior/state 5).
    uint8_t bossVisual = 0;
    uint8_t bossLives = 0;
    uint8_t bossHpByte = 0;
    uint8_t bossBoxW = 0;
    uint8_t bossBoxH = 0;
    uint8_t linkA = 0;
    uint8_t linkB = 0;
    uint8_t linkC = 0;
    int bossTick = 0;
    uint64_t actorOrder = 0;
    uint64_t bossVisualOrder = 0;
    bool bossDebris = false;
    uint16_t bossGroup = 0;
};

inline ActorAnimation monsterAnimation(const ActiveMonster& monster) {
    return {static_cast<uint8_t>(monster.animCursor + 1),
            static_cast<uint8_t>(monster.animStart + 1),
            static_cast<uint8_t>(monster.animEnd + 1),
            static_cast<uint8_t>(monster.animTick), monster.animDelay,
            monster.animMode, monster.animStep};
}

inline void setMonsterAnimation(ActiveMonster& monster, const ActorAnimation& animation) {
    monster.animCursor = static_cast<uint8_t>(animation.current - 1);
    monster.animStart = static_cast<uint8_t>(animation.first - 1);
    monster.animEnd = static_cast<uint8_t>(animation.last - 1);
    monster.animTick = animation.counter;
    monster.animDelay = animation.delay;
    monster.animMode = animation.mode;
    monster.animStep = animation.step;
}

inline bool advanceMonsterAnimation(ActiveMonster& monster) {
    auto animation = monsterAnimation(monster);
    const bool advanced = animation.advance(monster.animationBackup);
    setMonsterAnimation(monster, animation);
    if (advanced) monster.animFrame = monster.animCursor;
    return advanced;
}

inline constexpr std::array<int, 2> monsterFacingFrameRange(const ActiveMonster& monster) {
    const bool right = monster.vx8 > 0;
    uint8_t selector = right ? monster.animationSetRight : monster.animationSetLeft;
    // Existing seeded diagnostics construct monsters without the spawner.
    if (selector == 0) selector = monsterAnimationSelectors(monster.kind)[right ? 1 : 0];
    return monsterAnimationSetRange(selector);
}

enum class BonusType : uint8_t {
    Present,
    FirstAid,
    HotDog,
    JollyCloud,
    YellowBombBox,
    GreenBombBox,
    BigDiamond,
};

struct BonusDrop {
    float x = 0.0f;
    float y = 0.0f;
    BonusType type = BonusType::Present;
    int16_t vx8 = 0;
    int16_t vy8 = 0;
    uint8_t fracX = 0;
    uint8_t fracY = 0;
    uint8_t hotspotY = 0;
    uint8_t timer = 100;
    bool collected = false;
    uint64_t actorOrder = 0;
    ActorAnimation animation{0, 0, 0, 0, 0, 0, 1};
};

struct BonusDropStep {
    bool animationAdvanced = false;
    bool converted = false;
    TransientActor conversion;
};

template <typename Motion, typename Random, typename Hotspot>
inline BonusDropStep advanceBonusDrop(BonusDrop& drop, const ActorAnimation& backup,
        uint32_t tick, const std::array<bool, 2>& touching, std::array<uint8_t, 2>& pending,
        Motion motion, Random random, Hotspot hotspot) {
    BonusDropStep result;
    result.animationAdvanced = drop.animation.advance(backup);
    int x = static_cast<int16_t>(drop.x);
    int y = static_cast<int16_t>(static_cast<int>(drop.y) - static_cast<int8_t>(drop.hotspotY));
    bool collected = false;
    int16_t markerVelocity = 0;
    // Both contacts use the original reward kind, including a second pickup.
    for (size_t player = 0; player < touching.size(); ++player) {
        if (touching[player] && !pending[player]) {
            pending[player] = static_cast<uint8_t>(drop.type) + 1;
            markerVelocity = static_cast<int16_t>(-100 * random());
            collected = true;
        }
    }
    if (collected) {
        constexpr std::array<uint8_t, 7> scoreSprites{{88, 86, 87, 88, 89, 86, 90}};
        auto& marker = result.conversion;
        marker.x = x;
        marker.vy8 = markerVelocity;
        marker.fracX = drop.fracX;
        marker.fracY = drop.fracY;
        // This dispatch retains cached behavior 2; later passes use behavior 5.
        motion(marker.x, y, marker.vx8, marker.vy8, marker.fracX, marker.fracY);
        marker.kind = 0x0b;
        marker.timer = static_cast<uint8_t>(26 - (tick & 1u));
        marker.spriteIndex = scoreSprites.at(static_cast<size_t>(drop.type)) - 1;
        marker.hotspotY = hotspot(marker.spriteIndex);
        marker.y = static_cast<int16_t>(y + static_cast<int8_t>(marker.hotspotY));
        marker.actorOrder = drop.actorOrder;
        marker.animation = drop.animation;
        marker.animation.mode = 0;
        marker.animationBackup = backup;
        result.converted = drop.collected = true;
        return result;
    }
    motion(x, y, drop.vx8, drop.vy8, drop.fracX, drop.fracY);
    drop.x = static_cast<float>(x);
    drop.y = static_cast<float>(static_cast<int16_t>(y + static_cast<int8_t>(drop.hotspotY)));
    drop.timer = static_cast<uint8_t>(drop.timer - (tick & 1u));
    if (drop.timer == 0 || drop.timer == 0xff) {
        auto& fade = result.conversion;
        fade.kind = 0;
        fade.x = x;
        fade.y = static_cast<int>(drop.y);
        fade.fracX = drop.fracX;
        fade.fracY = drop.fracY;
        fade.timer = 18;
        fade.spriteIndex = 73;
        fade.hotspotY = hotspot(fade.spriteIndex);
        fade.animation = ActorAnimation::initialize(74, 79, 2, 1);
        fade.actorOrder = drop.actorOrder;
        fade.animationBackup = backup;
        result.converted = drop.collected = true;
    }
    return result;
}

struct State2VisualCursor {
    uint8_t current = kState2VisualStartFrame;
    uint8_t first = kState2VisualStartFrame;
    uint8_t last = kState2VisualEndFrame;
    uint8_t counter = kState2VisualDelay;
    uint8_t delay = kState2VisualDelay;
    uint8_t mode = 1;
    int8_t step = 1;
    bool active = false;
};

struct State2VisualRow {
    uint8_t frame = 0;
    uint8_t row0 = 0;
    uint8_t row1 = 0;
    uint8_t row2 = 0;
    uint8_t row3 = 0;
};

struct State2EffectEntry {
    int x = 0;
    int y = 0;
    uint8_t visualFrame = 0;
    uint8_t drawDx = 0;
    uint8_t drawDy = 0;
    uint8_t row2 = 0;
    uint8_t spriteIndex = 0;
    bool active = false;
};

struct SharedActorEntry {
    uint64_t order;
    SharedActorKind kind;
    size_t index;
};

inline int8_t blendFlameVelocity(int own, int incoming, uint8_t mass, int weight) {
    // 1000:47DF..4850 wraps the signed numerator to a word before IDIV.
    const int16_t numerator = static_cast<int16_t>(own * mass + incoming * weight);
    return static_cast<int8_t>(numerator / (mass + weight));
}

inline bool originalState2VisualRow(uint8_t frame, State2VisualRow& row) {
    if (frame < kState2VisualStartFrame || frame > kState2VisualEndFrame) {
        return false;
    }
    row.frame = frame;
    row.row0 = 0x10;
    row.row1 = 0x10;
    row.row2 = 0x7d;
    row.row3 = static_cast<uint8_t>(
        0x43 + (frame - kState2VisualStartFrame));
    return true;
}

inline BombProfile bombProfile(BombType type) {
    switch (type) {
        // The default (Small) bomb is the blue BOMOMIMK sprite 57, verified
        // against the original both in the HUD selector box and as a dropped
        // world bomb (captured under DOSBox); 58 is the green bomb.
        // 1000:6C0A..6C25 seeds actor +0x02 with 20/30/40/200.
        // 1000:75A7..75B0 subtracts DS:78C2 & 1. These are the maximum
        // game-update counts, not the original byte countdown values.
        case BombType::Small: return {0x0d, 57, 40};
        case BombType::Medium: return {0x0e, 58, 60};
        case BombType::Large: return {0x0f, 59, 80};
        case BombType::Super: return {0x10, 60, 400};
    }
    return {0x0d, 57, 40};
}

inline int bonusSpriteIndex(BonusType type) {
    switch (type) {
        case BonusType::Present: return 61;
        case BonusType::FirstAid: return 62;
        case BonusType::HotDog: return 63;
        case BonusType::JollyCloud: return 64;
        case BonusType::YellowBombBox: return 65;
        case BonusType::GreenBombBox: return 66;
        case BonusType::BigDiamond: return 67;
    }
    return 61;
}

}
