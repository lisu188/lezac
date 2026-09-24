#pragma once

#include "gameplay/actor_models.hpp"
#include "core/hud.hpp"
#include "resources/levels.hpp"
#include "resources/records.hpp"
#include "ui/models.hpp"
#include <array>
#include <string>
#include <vector>

namespace lezac::rendering {

struct PlayerRenderView {
    const gameplay::Player& player;
    bool dead;
    int lives;
    const gameplay::State2VisualCursor& state2Cursor;
    const gameplay::State2EffectEntry& state2Effect;
};

// Read-only world data needed for painting. Visual order is prepared by the
// simulation before entry; rendering never allocates actor identities.
struct WorldRenderView {
    const resources::Level& level;
    int levelIndex;
    int playerCount;
    std::array<PlayerRenderView, 2> players;
    const std::vector<gameplay::Bomb>& bombs;
    const std::vector<gameplay::ActiveMonster>& monsters;
    const std::vector<gameplay::BonusDrop>& bonusDrops;
    const std::vector<gameplay::Flash>& flashes;
    const std::vector<gameplay::LaunchPadMarker>& launchPadMarkers;
    const std::vector<gameplay::TransientActor>& transientActors;
    const std::vector<gameplay::SharedActorEntry>& visualOrder;
    int viewWidth;
    bool showBackground;
    uint16_t cameraShakeOffset;
    bool state2CursorPreview;
    bool state2RowPreview;
};

struct PlayerHudView {
    int energy;
    uint32_t score;
    int lives;
    bool dead;
    const gameplay::BombInventory& inventory;
};

struct HudView {
    int playerCount;
    std::array<PlayerHudView, 2> players;
    uint8_t objectiveTile;
    uint16_t requiredBonus;
    uint8_t requiredDestruction;
    int collected;
    int destructionPercent;
    bool complete;
    bool outroActive;
    std::array<core::HudScoreReel, 2> scoreReels{};
    std::array<bool, 2> columnReady{};
};

struct MenuView {
    ui::MenuPage page;
    bool italian;
    const std::vector<resources::Record>& records;
    uint8_t pendingPlayer;
    uint32_t pendingScore;
    uint8_t pendingLevel;
    const std::string& pendingName;
    int playerCount;
    std::array<uint32_t, 2> scores;
};

struct OutroView {
    bool active;
    uint32_t elapsed;
    std::vector<ui::OutroLine> lines;
    std::vector<ui::OutroSegment> segments;
};

}
