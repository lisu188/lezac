#pragma once

#include "core/pic_work_clock.hpp"
#include "core/keyboard_controller.hpp"

#include <array>
#include <bit>
#include <cstdint>
#include <optional>
#include <stdexcept>
#include <vector>

namespace lezac::core {

struct RenderPaletteClockSnapshot {
    uint32_t first=256,last=0,inMode=0,outMode=3;
    std::array<uint32_t,256> rgb{},lut{};
    std::array<uint8_t,256> modified{};
    // RGB32 layout, lock flags, idle-update coherence, backend and channel losses.
    std::array<uint32_t,18> format{};
    bool operator==(const RenderPaletteClockSnapshot&) const = default;
};

struct PacingDeviceClockSnapshot {
    PicWorkClockSnapshot clock;
    std::array<uint64_t, 25> devices{};
    std::array<uint64_t, 6> delayBits{};
    std::vector<uint8_t> tickers;
    uint64_t deviceCallbacks = 0, tickerCallbacks = 0;
    std::optional<RenderPaletteClockSnapshot> palette=std::nullopt;
    std::optional<KeyboardControllerSnapshot> keyboard=std::nullopt;
    bool operator==(const PacingDeviceClockSnapshot&) const = default;
};

// Timing-relevant VGA PART callbacks and optional active keyboard/silent-mixer tickers.
// Rendering pixels and other device/IRQ profiles are not implemented here.
class PacingDeviceClock {
public:
    explicit PacingDeviceClock(PacingDeviceClockSnapshot state)
        : clock_(state.clock), state_(std::move(state)) {
        const auto& d = state_.devices;
        if (d[0] != 5 || d[1] != 3 || d[2] != 0 || d[4] != 4 || d[5] != 50 || d[7] != 200 ||
            d[3] > d[4] || d[6] > d[7] || d[8] || d[9] > 1 || d[10] > 255 || d[11] != 1 || d[12] > 1 ||
            d[13] || d[14] || d[15] > (state_.palette?1u:0u) || d[16] > (state_.palette?1u:0u) ||
            (!state_.keyboard && (d[17] || d[18] || d[19] || d[20])) || d[21] != 1 || d[22] || d[23] || d[24] ||
            state_.tickers != std::vector<uint8_t>{11,10})
            throw std::invalid_argument("Pacing device clock differs from the observed VGA/idle/silent profile");
        if(state_.palette) validatePalette(*state_.palette);
        if (state_.keyboard) {
            const auto& k = *state_.keyboard;
            KeyboardController validated(k);
            unsigned transfers = 0;
            for (const auto& event : state_.clock.queue) if (event.kind == PicClockEventKind::KeyboardTransfer) {
                if (event.value) throw std::invalid_argument("Keyboard transfer callback value differs");
                ++transfers;
            }
            if (d[17] != k.repeatWait || d[18] != static_cast<uint8_t>(k.repeatKey) || d[19] != k.used || d[20] != uint64_t{k.scheduled})
                throw std::invalid_argument("Keyboard controller and device observations disagree");
            if (transfers != static_cast<unsigned>(k.scheduled))
                throw std::invalid_argument("Keyboard transfer scheduling and queue disagree");
        }
        for (auto bits : state_.delayBits) {
            const double delay = std::bit_cast<double>(bits);
            if (!std::isfinite(delay) || delay <= 0 || delay > 1024)
                throw std::invalid_argument("VGA delay is outside the recovered bounds");
        }
        for (const auto& event : state_.clock.queue)
            if (static_cast<unsigned>(event.kind) < 1 || event.kind == PicClockEventKind::Foreign ||
                static_cast<unsigned>(event.kind) > (state_.keyboard ? 8u : 7u))
                throw std::invalid_argument("Pacing device callback identity is unknown");
    }
    PacingDeviceClockSnapshot snapshot() const {
        auto result = state_; result.clock = clock_.snapshot(); return result;
    }
    PicWorkClock& workClock() noexcept { return clock_; }
    const PicWorkClock& workClock() const noexcept { return clock_; }
    void setPaletteColor(uint8_t entry,uint8_t red,uint8_t green,uint8_t blue) {
        if(!state_.palette) throw std::logic_error("Palette programming has no observed renderer profile");
        auto& palette=*state_.palette;
        palette.rgb[entry]=(uint32_t{red}<<16)|(uint32_t{green}<<8)|blue;
        palette.first=std::min(palette.first,uint32_t{entry});
        palette.last=std::max(palette.last,uint32_t{entry});
    }
    void addKeyboardKey(KeyboardHardwareKey key, bool pressed) {
        auto keyboard = keyboardController();
        keyboard.addKey(key, pressed, keyboardBus());
        setKeyboard(keyboard.snapshot());
    }
    uint8_t readKeyboardPort(uint16_t port) {
        auto keyboard = keyboardController();
        const auto result = keyboard.readPort(port, keyboardBus());
        setKeyboard(keyboard.snapshot());
        return result;
    }
    void writeKeyboardPort(uint16_t port, uint8_t value, const KeyboardControllerBus& effects) {
        auto keyboard = keyboardController();
        keyboard.writePort(port, value, keyboardBus(effects));
        setKeyboard(keyboard.snapshot());
    }

    PicClockBoundary nextDispatch(bool coreReturned, uint32_t flags) {
        auto boundary = clock_.nextDispatch(coreReturned, flags);
        while (boundary.kind == PicClockBoundaryKind::ForeignEvent) {
            const auto event = clock_.consumeDeviceEvent();
            callback(event);
            ++state_.deviceCallbacks;
            boundary = clock_.nextDispatch(false, flags);
        }
        return boundary;
    }
    void grantMillisecond() {
        clock_.grantMillisecond();
        if (state_.keyboard) {
            auto keyboard = keyboardController();
            keyboard.tick(keyboardBus());
            setKeyboard(keyboard.snapshot());
        }
        // The mixer is silent; the original ticker order is mixer then keyboard.
        state_.tickerCallbacks += state_.tickers.size();
    }

private:
    KeyboardController keyboardController() const {
        if (!state_.keyboard) throw std::logic_error("Active keyboard controller is not attached");
        return KeyboardController(*state_.keyboard);
    }
    void setKeyboard(const KeyboardControllerSnapshot& keyboard) {
        state_.keyboard = keyboard;
        auto& d = state_.devices;
        d[17] = keyboard.repeatWait; d[18] = static_cast<uint8_t>(keyboard.repeatKey);
        d[19] = keyboard.used; d[20] = keyboard.scheduled;
    }
    KeyboardControllerBus keyboardBus(const KeyboardControllerBus& effects = {}) {
        return {[this](float delay) {
                clock_.scheduleDeviceEvent({clock_.fractionalTickIndex() + delay, PicClockEventKind::KeyboardTransfer, 0});
            }, [this] {clock_.removeDeviceEvents(PicClockEventKind::KeyboardTransfer);},
            [this] {clock_.activateKeyboardIrq();}, effects.a20Enabled, effects.setA20, effects.setGate2, effects.setSpeakerType};
    }
    static uint32_t mapped(const RenderPaletteClockSnapshot& p,uint32_t rgb) {
        return (((rgb>>16)&255u)<<p.format[6])|(((rgb>>8)&255u)<<p.format[7])|((rgb&255u)<<p.format[8])|p.format[5];
    }
    static void validatePalette(const RenderPaletteClockSnapshot& p) {
        const auto& f=p.format;
        if(p.first>256 || p.last>255 || p.inMode!=0 || p.outMode!=3 || f[0]!=32 || f[1]!=4 ||
            f[6]>24 || f[7]>24 || f[8]>24 || f[6]%8 || f[7]%8 || f[8]%8 ||
            f[2]!=(255u<<f[6]) || f[3]!=(255u<<f[7]) || f[4]!=(255u<<f[8]) ||
            (f[2]&f[3]) || (f[2]&f[4]) || (f[3]&f[4]) ||
            (f[5]!=0 && f[5]!=~(f[2]|f[3]|f[4])) || (f[9]&0x4005u) || f[10] || f[11]!=1 ||
            f[12]!=1 || f[13] || f[14] || f[15] || f[16] || f[17])
            throw std::invalid_argument("Renderer palette differs from the observed software RGB32 profile");
        for(unsigned i=0;i<256;++i)
            if(p.rgb[i]>0xffffffu || p.modified[i]>1) throw std::invalid_argument("Renderer palette fields differ");
    }
    void checkPalette() {
        if(!state_.palette) return;
        auto& p=*state_.palette;auto& d=state_.devices;
        if(d[16]) {p.modified.fill(0);d[16]=0;}
        if(p.first>p.last) return;
        for(unsigned i=p.first;i<=p.last;++i) {
            const auto value=mapped(p,p.rgb[i]);
            if(value!=p.lut[i]) {p.lut[i]=value;p.modified[i]=1;d[16]=1;}
        }
        p.first=256;p.last=0;
    }
    double delay(unsigned index) const { return std::bit_cast<double>(state_.delayBits[index]); }
    void schedule(const PicClockEvent& source, PicClockEventKind kind, float delta, uint64_t value = 0) {
        clock_.scheduleDeviceEvent({source.index + delta, kind, value});
    }
    void callback(const PicClockEvent& event) {
        auto& d = state_.devices;
        switch (event.kind) {
        case PicClockEventKind::KeyboardTransfer: {
            if (event.value) throw std::domain_error("Keyboard transfer callback value differs");
            auto keyboard = keyboardController();
            keyboard.transferBuffer(keyboardBus());
            setKeyboard(keyboard.snapshot());
            break;
        }
        case PicClockEventKind::VgaDrawPart:
            if (!d[3] || event.value > 200 || d[6] + event.value > d[7])
                throw std::domain_error("VGA draw part left the recovered line domain");
            d[6] += event.value;
            if (--d[3]) schedule(event, event.kind, static_cast<float>(delay(0)), d[3] != 1 ? d[5] : d[7] - d[6]);
            else d[12] = 0;
            break;
        case PicClockEventKind::VgaVertical:
            schedule(event, event.kind, static_cast<float>(delay(1)));
            schedule(event, PicClockEventKind::VgaDisplayLatch, static_cast<float>(delay(2)));
            schedule(event, PicClockEventKind::VgaPanningLatch, static_cast<float>(delay(3)));
            schedule(event, PicClockEventKind::VgaVerticalInterrupt, static_cast<float>(delay(4) + 0.005));
            if (d[12]) break;
            checkPalette();
            d[15]=0; d[12] = 1;
            if (d[3]) {
                clock_.removeDeviceEvents(PicClockEventKind::VgaDrawPart);
                d[12] = 0;
            }
            d[6] = 0; d[3] = d[4];
            schedule(event, PicClockEventKind::VgaDrawPart, static_cast<float>(delay(0)), d[5]);
            break;
        case PicClockEventKind::VgaVerticalInterrupt:
            if (!d[9] && (d[10] & 0x30) == 0x10) d[9] = 1;
            break;
        case PicClockEventKind::VgaDisplayLatch:
        case PicClockEventKind::VgaPanningLatch:
            break;
        default: throw std::domain_error("Unrecovered pacing device callback");
        }
    }
    PicWorkClock clock_;
    PacingDeviceClockSnapshot state_;
};

}
