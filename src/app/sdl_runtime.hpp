#pragma once

namespace lezac::app {

class SdlRuntime {
public:
    SdlRuntime() = default;
    ~SdlRuntime();
    SdlRuntime(const SdlRuntime&) = delete;
    SdlRuntime& operator=(const SdlRuntime&) = delete;
    void initialize();
};

}
