void LezacReadDeviceClock(LezacDeviceObservation& result) {
    for (TickerBlock* ticker = firstticker; ticker; ticker = ticker->next) {
        if (result.ticker_count == 16) { result.ticker_overflow = true; break; }
        unsigned kind = LezacClockKeyboardKind(ticker->handler);
        if (kind == 2) kind = LezacClockMixerKind(ticker->handler);
        result.ticker_kinds[result.ticker_count++] = kind;
    }
    LezacReadVgaClock(result);
    LezacReadRenderClock(result);
    LezacReadKeyboardClock(result);
    LezacReadMixerClock(result);
}
