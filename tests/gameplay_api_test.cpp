#include "diagnostics/gameplay/gameplay_replay.hpp"
#include <stdexcept>
#include <type_traits>

using namespace lezac;
using namespace lezac::gameplay;

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
}

int main() {
    static_assert(std::is_const_v<std::remove_reference_t<decltype(GameplayView::monsters_)>>);
    static_assert(std::is_const_v<std::remove_reference_t<decltype(GameplayView::player_)>>);
    resources::AssetCatalog assets;
    sound::SoundEngine sound(assets.sounds());
    core::TurboRandom random(0x1234abcd);
    GameSession session(assets, sound, random);
    GameplayFixture initial;
    initial.level_.width = initial.level_.height = 8;
    initial.level_.tiles.resize(64);
    initial.level_.wordLayer.resize(64);
    initial.player_.x = 32;
    initial.monsters_.push_back({});
    initial.monsters_.front().alive = false;
    session.restoreFixture(initial);

    diagnostics::GameplayReplay replay(session);
    replay.fixture().player_.x = 99;
    require(session.view().player_.x == 32, "fixture mutation leaked into live player");
    replay.commit();
    require(session.view().player_.x == 99, "explicit fixture commit failed");

    BombInventory detached;
    detached.counts = {{0, 2, 0, 0}};
    replay.selectNextAvailableBomb(detached);
    require(detached.selected == BombType::Medium, "detached replay argument lost mutation");
    require(session.view().bombInventory_.selected == BombType::Small,
            "detached inventory changed live inventory");

    replay.fixture().bombInventory_.counts = {{0, 0, 3, 0}};
    replay.selectNextAvailableBomb(replay.fixture().bombInventory_);
    require(session.view().bombInventory_.selected == BombType::Large,
            "fixture slot target did not select live inventory");

    auto* retained = &replay.fixture().monsters_.front();
    replay.claimActorOrder();
    require(retained == &replay.fixture().monsters_.front(),
            "replay reconciliation invalidated an unchanged fixture slot");

    int position = 0;
    int16_t velocityX = 256, velocityY = 512;
    uint8_t fractionX = 0, fractionY = 0;
    replay.updateTimedActorMotion(position, position, velocityX, velocityY,
                                  fractionX, fractionY, {});
    require(position == 3, "detached argument aliasing did not preserve y-then-x integration");

    ReplayTarget<int> detachedX, detachedY;
    ReplayTarget<int16_t> detachedVx, detachedVy;
    ReplayTarget<uint8_t> detachedFx, detachedFy;
    detachedVx.value = 256;
    detachedVy.value = 512;
    detachedY.detachedAlias = 3;  // Argument 3 has a different type, not a position.
    bool rejected = false;
    try {
        session.replay_updateTimedActorMotion(detachedX, detachedY, detachedVx, detachedVy,
                                              detachedFx, detachedFy, {});
    } catch (const std::runtime_error&) {
        rejected = true;
    }
    require(rejected && detachedX.value == 0 && detachedY.value == 0,
            "invalid detached alias was not rejected before motion");
    detachedY.slot = ReplaySlot::energy_;
    detachedY.detachedAlias = 1;
    rejected = false;
    const int energyBefore = session.view().energy_;
    try {
        session.replay_updateTimedActorMotion(detachedX, detachedY, detachedVx, detachedVy,
                                              detachedFx, detachedFy, {});
    } catch (const std::runtime_error&) {
        rejected = true;
    }
    require(rejected && session.view().energy_ == energyBefore,
            "owned slot accepted a detached alias");

    AfterActorPassAction injection;
    TransientActor filler;
    filler.timer = 240;
    injection.appendActors.push_back(filler);
    session.scheduleAfterActorPass(std::move(injection));
    bool observed = false;
    GameplayHooks hooks;
    hooks.actorPassObserver = [&](const GameplayView& view) {
        require(view.transientActors_.size() == 1, "phase action did not precede observer");
        require(view.transientActors_.front().timer == 240,
                "phase action advanced in the preceding actor pass");
        observed = true;
    };
    session.setHooks(std::move(hooks));
    session.tick({}, 0);
    require(observed && session.view().transientActors_.front().actorOrder != 0,
            "phase action did not receive a shared actor order");
    require(replay.fixture().transientActors_.empty(),
            "live tick wrote into the detached diagnostic copy");
}
