#pragma once
#include "gameplay/gameplay_operations.hpp"

namespace lezac::gameplay {
struct FixtureCopyCounts {
    size_t snapshots = 0;
    size_t restores = 0;
};
class GameSession final : private detail::GameplayOperations {
public:
    explicit GameSession(GameplayServices services) : GameplayOperations(std::move(services)) {}
    GameplayView view() const { return currentView(); }
    GameplayFixture snapshot() const { ++copies_.snapshots; return fixture_; }
    std::unique_ptr<GameplayFixture> snapshotOwned() const {
        ++copies_.snapshots;
        return std::make_unique<GameplayFixture>(fixture_);
    }
    void restoreFixture(const GameplayFixture& fixture) { ++copies_.restores; fixture_ = fixture; }
    FixtureCopyCounts fixtureCopyCounts() const { return copies_; }
    void setFireLatch(uint8_t player, bool held) { (player == 2 ? reentryFire2_ : reentryFire1_) = held; }
    void setRandomSeed(uint32_t seed) { randomSeed_ = seed; }
    void configureDiagnosticActorSeeds(bool enabled) { legacyActorSeedsEnabled_ = enabled; }
    void releasePortalDown(uint8_t bank) { portalDownConsumed_.at(bank) = false; }
    void fireAtPlayer(uint8_t player, int x, int y) { tryActivePlayerFireAt(player == 2 ? player2_ : player_, x, y, player); }
    void initializeAssetState(bool preview) {
        actorSlots_.setSavedViewportColumns(40);
        actorSlots_.setSpriteBankTag(1);
        if (preview) buildBackdropBuffer();
        else presentation_.initializeBackdropBuffer(playerCount_);
    }
    using GameplayOperations::abortRun;
    using GameplayOperations::addScore;
    using GameplayOperations::adjustGameplayViewWidth;
    using GameplayOperations::allPlayersOutOfLives;
    using GameplayOperations::beginEndRun;
    using GameplayOperations::beginGameOver;
    using GameplayOperations::beginLevelForPlay;
    using GameplayOperations::beginLevelOutro;
    using GameplayOperations::buildBackdropBuffer;
    using GameplayOperations::canReenterLevel;
    using GameplayOperations::cancelPendingRecord;
    using GameplayOperations::capturedLevelIntroPattern;
    using GameplayOperations::clearPendingRecord;
    using GameplayOperations::clearRunScores;
    using GameplayOperations::clearSoundLatch;
    using GameplayOperations::destructionPercent;
    using GameplayOperations::endMenuPage;
    using GameplayOperations::finalizePendingRecord;
    using GameplayOperations::finishLevelIntro;
    using GameplayOperations::finishLevelOutro;
    using GameplayOperations::hudView;
    using GameplayOperations::initializeGameplayView;
    using GameplayOperations::isComplete;
    using GameplayOperations::isFinalLevel;
    using GameplayOperations::latchSoundRequest;
    using GameplayOperations::levelOutroLines;
    using GameplayOperations::levelOutroSchedule;
    using GameplayOperations::makeLevelIntroPattern;
    using GameplayOperations::menuRenderView;
    using GameplayOperations::onUiKey;
    using GameplayOperations::originalPlayerState;
    using GameplayOperations::playCompatibilitySound;
    using GameplayOperations::prepareHudObjectives;
    using GameplayOperations::prepareRenderState;
    using GameplayOperations::pumpSoundLatch;
    using GameplayOperations::remainingObjectiveTiles;
    using GameplayOperations::remainingPlayerCount;
    using GameplayOperations::requestRecordNameCommitSound;
    using GameplayOperations::requestRecordNamePromptSound;
    using GameplayOperations::requestRecordsPageSound;
    using GameplayOperations::requestSoundCursor;
    using GameplayOperations::requestSoundOffset;
    using GameplayOperations::resetLevel;
    using GameplayOperations::scoreQualifies;
    using GameplayOperations::serviceSoundClock;
    using GameplayOperations::startClockedSound;
    using GameplayOperations::startNextPendingRecord;
    using GameplayOperations::uiActions;
    using GameplayOperations::updateHudScores;
    using GameplayOperations::updateLevelCompletion;
    using GameplayOperations::updateLevelIntro;
    using GameplayOperations::updateLevelOutro;
    using GameplayOperations::updateWithControls;
    using GameplayOperations::visibleLevelIntroCharacters;
    using GameplayOperations::worldRenderView;
    using GameplayOperations::writeViewportDestinations;
private:
    mutable FixtureCopyCounts copies_;
};
}
