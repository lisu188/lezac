#pragma once

namespace lezac::gameplay {

// A logical tick's input; physical keyboard ownership belongs to InputMapper.
struct FrameControls {
    bool p1Left = false;
    bool p1Right = false;
    bool p1Jump = false;
    bool p1Down = false;
    bool p2Left = false;
    bool p2Right = false;
    bool p2Jump = false;
    bool p2Down = false;
    bool p1Reenter = false;
    bool p2Reenter = false;
};

}
