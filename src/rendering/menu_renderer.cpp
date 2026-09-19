#include "rendering/game_renderer.hpp"
#include "rendering/color.hpp"
#include <algorithm>
#include <cmath>
#include <string>

namespace lezac::rendering {
using namespace gameplay;
using namespace resources;
using namespace ui;

namespace {
class MenuPainter {
public:
    MenuPainter(Canvas& canvas, TextRenderer& text, const AssetCatalog& assets,
                const PresentationState& presentation, const GameRenderer& renderer,
                const MenuView& menu)
        : canvas_(canvas), text_(text), assets_(assets), presentation_(presentation),
          renderer_(renderer), menu_(menu) {}
    void drawBackground(int camX, int camY) {
        // The SFONLEF.ZBG title image backing the menu. The in-game
        // showBackground_ toggle only affects the gameplay sky (drawGradientSky),
        // so the menu title is always drawn.
        for (int y = 0; y < kScreenH; ++y) {
            for (int x = 0; x < kScreenW; ++x) {
                int bx = (x + camX / 4) % assets_.background().width;
                int by = (y + camY / 4) % assets_.background().height;
                if (bx < 0) bx += assets_.background().width;
                if (by < 0) by += assets_.background().height;
                canvas_.pixel(x, y,
                      argb(assets_.backgroundPalette(),
                           assets_.background().pixels[static_cast<size_t>(by) * assets_.background().width + bx]));
            }
        }
    }

    void drawMenu() {
        drawBackground(0, 0);
        if (menu_.page == MenuPage::Main) {
            // The original main menu is the SFONLEF.ZBG title screen with the
            // menu options drawn directly over the art (Italian by default; L
            // toggles English). The original source (LEZAC.EXE 0xb92a Italian,
            // 0xc679 English) uses a contiguous glyph set where ';' displays as
            // a colon and a trailing ':' displays as a period; rendered with the
            // port's standard-ASCII font map that means a ':' separator and a
            // '.' terminator -- e.g. "I: INFORMAZIONI." -- and every line ends
            // in that period, which the earlier transcription had dropped.
            static const char* kItalian[7] = {
                "PREMI 1 PER UN GIOCATORE.", "PREMI 2 PER DUE GIOCATORI.",
                "I: INFORMAZIONI.", "Z: ISTRUZIONI.", "R: VEDI RECORDS.",
                "L: ENGLISH.", "ESC PER USCIRE."};
            static const char* kEnglish[7] = {
                "PRESS 1 FOR ONE PLAYER GAME.", "PRESS 2 FOR TWO PLAYERS GAME.",
                "I: INFOS.", "Z: INSTRUCTIONS.", "R: SHOW RECORDS.",
                "L: ITALIANO.", "ESC EXITS."};
            const char* const* lines = menu_.italian ? kItalian : kEnglish;
            for (int i = 0; i < 7; ++i) {
                const std::string line = lines[i];
                const int x = (kScreenW - text_.textWidth(line)) / 2;
                // The original draws each line as a white glyph with a blue
                // (0,0,255) shadow, centred, on a 10px pitch (measured against
                // the original level-select frame: first line at y74, one pixel
                // below the vertical middle of the title art).
                text_.text(std::max(0, x), 74 + i * 10, line, 0xffffffffu, false,
                     0xff0000ffu);
            }
            return;
        }
        canvas_.rect(0, 0, 320, 200, 0x99000000u);
        text_.text(84, 26, "LARAX & ZACO", 0xffffe060u, true, 0xff301800u);
        switch (menu_.page) {
            case MenuPage::Main:
                drawMainMenu();
                break;
            case MenuPage::Info:
                drawInfoMenu();
                break;
            case MenuPage::Instructions:
                drawInstructionsMenu();
                break;
            case MenuPage::Records:
                drawRecordsMenu();
                break;
            case MenuPage::NameEntry:
                drawNameEntryMenu();
                break;
            case MenuPage::GameOver:
                drawGameOverMenu();
                break;
            case MenuPage::CompletedGame:
                drawCompletedGameMenu();
                break;
        }
    }

    void drawMainMenu() {
        text_.text(61, 43, "GHIDRA CPP RECONSTRUCTION", 0xffffffffu, false, 0xff101010u);
        text_.text(34, 67, "PRESS 1 FOR ONE PLAYER GAME.", 0xffffe060u, false, 0xff101010u);
        text_.text(34, 79, "PRESS 2 FOR TWO PLAYERS GAME.", 0xffffe060u, false, 0xff101010u);
        text_.text(34, 91, "I: INFOS. Z: INSTRUCTIONS.", 0xffffffffu, false, 0xff101010u);
        text_.text(34, 103, "R: SHOW RECORDS. ESC EXITS.", 0xffffffffu, false, 0xff101010u);
        text_.text(34, 115, "S: BACKGROUND.", 0xffffffffu, false, 0xff101010u);

        text_.text(88, 139, "BEST SCORES", 0xff90ffb0u, false, 0xff101010u);
        int y = 154;
        for (size_t i = 0; i < menu_.records.size() && i < 4; ++i) {
            drawRecordLine(i, y);
            y += 10;
        }
    }

    void drawCenteredMenuLines(const char* title, const char* const* lines,
                               int count) {
        const int tx = (kScreenW - static_cast<int>(std::string(title).size()) * 8) / 2;
        text_.text(std::max(0, tx), 40, title, 0xff90ffb0u, false, 0xff101010u);
        for (int i = 0; i < count; ++i) {
            const std::string line = lines[i];
            const int x = (kScreenW - static_cast<int>(line.size()) * 8) / 2;
            text_.text(std::max(0, x), 60 + i * 11, line, 0xffffffffu, false, 0xff101010u);
        }
        const char* back = menu_.italian ? "ESC PER TORNARE" : "ESC: BACK";
        const int bx = (kScreenW - static_cast<int>(std::string(back).size()) * 8) / 2;
        text_.text(std::max(0, bx), 184, back, 0xff90ffb0u, false, 0xff101010u);
    }

    void drawInfoMenu() {
        // Recovered from LEZAC.EXE: Italian at 1000:b000, English at 1000:bcab.
        static const char* kIta[8] = {
            "PER PROCEDERE NEL GIOCO DOVETE",
            "RACCOGLIERE BONUS E SOPRATTUTTO",
            "FAR SALTARE IN ARIA OGNI COSA",
            "IL RIQUADRO CENTRALE VI INDICA",
            "IL NUMERO MINIMO DI BONUS DA",
            "RACCOGLIERE E LA PERCENTUALE DELLE",
            "COSTRUZIONI DA DISTRUGGERE PER",
            "COMPLETARE IL QUADRO"};
        static const char* kEng[7] = {
            "YOU MUST COLLECT BONUSES AND",
            "DESTROY BUILDINGS TO PROCEED",
            "THE CENTRAL WINDOW WILL TELL",
            "YOU THE NUMBER OF BONUS TO",
            "COLLECT AND THE PERCENTAGE",
            "OF BUILDINGS YOU MUST DESTROY",
            "TO COMPLETE THE LEVEL"};
        if (menu_.italian) {
            drawCenteredMenuLines("INFORMAZIONI", kIta, 8);
        } else {
            drawCenteredMenuLines("INFOS", kEng, 7);
        }
    }

    void drawInstructionsMenu() {
        // Recovered keys table + notes from LEZAC.EXE: Italian at 1000:b9xx
        // ("tasti") / fire+weapon at 1000:aef4, English at 1000:baab / 1000:bbab.
        struct KeyRow { const char* action; const char* p1; const char* p2; };
        const char* title = menu_.italian ? "ISTRUZIONI" : "INSTRUCTIONS";
        const char* colHdr = menu_.italian ? "GIOC:1      GIOC:2"
                                           : "PLAYER1     PLAYER2";
        static const KeyRow kIta[5] = {
            {"SINISTRA", "Z", "FRECCE"}, {"DESTRA", "X", "="},
            {"SCENDI", "C", "="}, {"SALTA", "M", "="}, {"FUOCO", "N", "0"}};
        static const KeyRow kEng[5] = {
            {"LEFT", "Z", "ARROWS"}, {"RIGHT", "X", "="},
            {"DOWN", "C", "="}, {"JUMP", "M", "="}, {"FIRE", "N", "0"}};
        static const char* kItaNotes[4] = {
            "ESC ABBANDONA LA PARTITA",
            "PREMI SINISTRA E DESTRA INSIEME",
            "PER CAMBIARE BOMBA",
            "S ATTIVA O DISATTIVA LO SFONDO"};
        static const char* kEngNotes[4] = {
            "ESC QUITS GAME",
            "PRESS LEFT AND RIGHT TOGETHER",
            "TO CHANGE YOUR WEAPON",
            "S TOGGLES BACKGROUND"};
        const KeyRow* rows = menu_.italian ? kIta : kEng;
        const char* const* notes = menu_.italian ? kItaNotes : kEngNotes;

        const int tx = (kScreenW - static_cast<int>(std::string(title).size()) * 8) / 2;
        text_.text(std::max(0, tx), 34, title, 0xff90ffb0u, false, 0xff101010u);
        text_.text(120, 52, colHdr, 0xffffe060u, false, 0xff101010u);
        for (int i = 0; i < 5; ++i) {
            text_.text(32, 66 + i * 11, rows[i].action, 0xffffffffu, false, 0xff101010u);
            text_.text(140, 66 + i * 11, rows[i].p1, 0xffffffffu, false, 0xff101010u);
            text_.text(220, 66 + i * 11, rows[i].p2, 0xffffffffu, false, 0xff101010u);
        }
        for (int i = 0; i < 4; ++i) {
            const std::string line = notes[i];
            const int x = (kScreenW - static_cast<int>(line.size()) * 8) / 2;
            text_.text(std::max(0, x), 128 + i * 11, line, 0xffd8f0ffu, false, 0xff101010u);
        }
    }

    void drawRecordsMenu() {
        // Original records title: "il file dei records" (LEZAC.EXE 1000:16a7).
        const char* title = menu_.italian ? "IL FILE DEI RECORDS" : "BEST SCORES";
        const int tx = (kScreenW - static_cast<int>(std::string(title).size()) * 8) / 2;
        text_.text(std::max(0, tx), 48, title, 0xff90ffb0u, false, 0xff101010u);
        int y = 70;
        for (size_t i = 0; i < menu_.records.size(); ++i) {
            drawRecordLine(i, y);
            y += 12;
        }
        text_.text(38, 166, "ESC: BACK", 0xff90ffb0u, false, 0xff101010u);
    }

    void drawNameEntryMenu() {
        // Labels recovered from LEZAC.EXE: "giocatore" (1000:17f3), "punteggio
        // finale" (1000:b3ab), "inserisci il tuo nome" (1000:1826).
        const bool it = menu_.italian;
        text_.text(it ? 82 : 86, 48, it ? "NUOVO RECORD" : "NEW RECORD",
             0xff90ffb0u, false, 0xff101010u);
        text_.text(58, 64,
             (it ? "GIOCATORE " : "PLAYER ") + std::to_string(menu_.pendingPlayer),
             0xffffffffu, false, 0xff101010u);
        text_.text(58, 78,
             (it ? "PUNTEGGIO " : "SCORE ") + std::to_string(menu_.pendingScore),
             0xffffe060u, false, 0xff101010u);
        text_.text(58, 94,
             (it ? "LIVELLO " : "LEVEL ") + std::to_string(menu_.pendingLevel),
             0xffffffffu, false, 0xff101010u);
        text_.text(kNameEntryLabelX, kNameEntrySlotY, it ? "NOME " : "NAME ",
             0xffffffffu, false, 0xff101010u);
        drawNameEntrySlots();
        text_.text(30, 148,
             it ? "INSERISCI IL TUO NOME" : "TYPE LETTERS OR SPACE",
             0xffffffffu, false, 0xff101010u);
        text_.text(30, 160,
             it ? "ENTER SALVA. BACKSPACE CANCELLA" : "ENTER SAVE. BACKSPACE ERASES",
             0xff90ffb0u, false, 0xff101010u);
    }

    void drawNameEntrySlots() {
        int activeSlot = renderer_.nameEntryCursorSlot(menu_.pendingName);
        for (int slot = 0; slot < kNameEntrySlotCount; ++slot) {
            int x = renderer_.nameEntrySlotX(slot);
            bool active = slot == activeSlot;
            if (active) {
                canvas_.rect(x - 1, kNameEntrySlotY - 2, kNameEntryCursorBoxW,
                     kNameEntryCursorBoxH, kNameEntryCursorBackground);
            }
            char ch = slot < static_cast<int>(menu_.pendingName.size())
                          ? menu_.pendingName[static_cast<size_t>(slot)]
                          : '_';
            text_.text(x, kNameEntrySlotY, std::string(1, ch),
                 active ? kNameEntryCursorForeground : 0xffffffffu,
                 false, active ? 0 : 0xff101010u);
        }
    }

    void drawGameOverMenu() {
        text_.text(111, 72, "GAME OVER", 0xffff5050u, true, 0xff301010u);
        drawFinalScores(104);
        text_.text(78, 166, "ENTER: MENU", 0xff90ffb0u, false, 0xff101010u);
    }

    void drawCompletedGameMenu() {
        text_.text(90, 58, "ECCELLENTE>>>", 0xffffe060u, false, 0xff101010u);
        text_.text(54, 76, "HAI COMPLETATO IL GIOCO", 0xffffffffu, false, 0xff101010u);
        drawFinalScores(112);
        text_.text(78, 166, "ENTER: MENU", 0xff90ffb0u, false, 0xff101010u);
    }

    void drawFinalScores(int y) {
        if (menu_.scores[0] != 0) {
            text_.text(82, y, "P1 FINAL SCORE " + std::to_string(menu_.scores[0]),
                 0xffffe060u, false, 0xff101010u);
            y += 12;
        }
        if (menu_.playerCount > 1 && menu_.scores[1] != 0) {
            text_.text(82, y, "P2 FINAL SCORE " + std::to_string(menu_.scores[1]),
                 0xffffe060u, false, 0xff101010u);
        }
    }

    void drawRecordLine(size_t i, int y) {
        text_.text(52, y, std::to_string(i + 1) + " L" +
                        std::to_string(menu_.records[i].level) + " " + menu_.records[i].name,
             0xffffffffu, false, 0xff101010u);
        text_.text(178, y, std::to_string(menu_.records[i].score), 0xffffffffu, false, 0xff101010u);
    }
private:
    Canvas& canvas_;
    TextRenderer& text_;
    const AssetCatalog& assets_;
    const PresentationState& presentation_;
    const GameRenderer& renderer_;
    const MenuView& menu_;
};
}

void GameRenderer::drawMenu(const MenuView& menu) {
    MenuPainter(canvas_, text_, assets_, presentation_, *this, menu).drawMenu();
}

void GameRenderer::drawLevelIntro(int levelIndex, const LevelIntroPattern& pattern,
                    size_t visibleCharacters) {
    canvas_.resetClip();
    int fraction = 0;
    int phase = 0;
    for (int i = 0; i < kScreenW * kScreenH; ++i) {
        fraction += pattern.horizontalStep;
        if (fraction > 100) {
            fraction -= 100;
            ++phase;
        }
        if (i % kScreenW == 0) {
            const int sineIndex = ((i * 3) / 100) % 128;
            const int wave = static_cast<int>(
                std::sin(static_cast<float>(sineIndex) * 6.28f / 128.0f) *
                8.0f);
            fraction += pattern.verticalStep + wave;
            if (fraction > 100) {
                fraction -= 100;
                ++phase;
            }
        }
        const Rgb color =
            pattern.colors[static_cast<size_t>(phase) % pattern.colors.size()];
        canvas_.pixel(i % kScreenW, i / kScreenW,
              0xff000000u | (static_cast<uint32_t>(color.r) << 16) |
                  (static_cast<uint32_t>(color.g) << 8) | color.b);
    }

    const std::string caption = levelIntroCaption(levelIndex);
    const size_t count = std::min(visibleCharacters, caption.size());
    int x = kScreenW / 2 -
            static_cast<int>(caption.size()) * kLevelIntroCellAdvance / 2;
    for (size_t i = 0; i < count; ++i, x += kLevelIntroCellAdvance) {
        const int glyphIndex = text_.fontGlyphIndex(caption[i], false);
        if (glyphIndex < 0 ||
            glyphIndex >= static_cast<int>(assets_.fontSprites().sprites.size())) {
            continue;
        }
        const Sprite& glyph =
            assets_.fontSprites().sprites[static_cast<size_t>(glyphIndex)];
        text_.drawFontSprite(x - 1, kLevelIntroTextY - 1, glyph,
                       argb(presentation_.palette(), 1), false);
        text_.drawFontSprite(x, kLevelIntroTextY, glyph,
                       argb(presentation_.palette(), 31), false);
    }
}

void GameRenderer::drawLevelOutro(const OutroView& outro) {
    if (!outro.active) return;
    const uint32_t elapsed = outro.elapsed;
    const std::vector<OutroLine> lines = outro.lines;
    const std::vector<OutroSegment> segs = outro.segments;
    for (const OutroSegment& seg : segs) {
        if (!seg.typing || seg.line < 0 || elapsed <= seg.start) continue;
        const OutroLine& line = lines[static_cast<size_t>(seg.line)];
        size_t visible = line.text.size();
        if (elapsed < seg.end) {
            visible = std::min(
                visible, static_cast<size_t>((elapsed - seg.start) /
                                             kLevelIntroCharacterDelayMs));
        }
        // The 11px-cell headline uses the large font face; the 9px-cell
        // lines use the small face (measured against the original banner).
        const bool large = line.cell == 11;
        int x = kScreenW / 2 -
                static_cast<int>(line.text.size()) * line.cell / 2;
        for (size_t i = 0; i < visible; ++i, x += line.cell) {
            const int glyphIndex = text_.fontGlyphIndex(line.text[i], large);
            if (glyphIndex < 0 ||
                glyphIndex >= static_cast<int>(assets_.fontSprites().sprites.size())) {
                continue;
            }
            const Sprite& glyph =
                assets_.fontSprites().sprites[static_cast<size_t>(glyphIndex)];
            text_.drawFontSprite(x - 1, line.y - 1, glyph,
                           argb(presentation_.palette(), line.shadowColor), large);
            text_.drawFontSprite(x, line.y, glyph,
                           argb(presentation_.palette(), line.glyphColor), large);
        }
    }
}

void GameRenderer::drawPauseOverlay() {
    constexpr int x = 112;
    constexpr int y = 84;
    constexpr int w = 96;
    constexpr int h = 28;
    canvas_.rect(x, y, w, h, 0xdd000000u);
    canvas_.rect(x, y, w, 1, 0xfff0d060u);
    canvas_.rect(x, y + h - 1, w, 1, 0xfff0d060u);
    canvas_.rect(x, y, 1, h, 0xfff0d060u);
    canvas_.rect(x + w - 1, y, 1, h, 0xfff0d060u);
    text_.text(x + 27, y + 10, "PAUSED", 0xffffe060u, false, 0xff301800u);
}
}
