#pragma once

#include <array>
#include <cstdint>
#include <stdexcept>

namespace lezac::core {
struct VgaDacWriteSnapshot {
    uint8_t index=0,component=0;
    std::array<uint8_t,3> channels{};
    bool indexKnown=false;
    bool operator==(const VgaDacWriteSnapshot&) const = default;
};

// Six-bit, unmasked VGA write transactions; initial DAC read state is not inferred.
class VgaDacWriter {
public:
    explicit VgaDacWriter(VgaDacWriteSnapshot state={}):state_(state) {
        if(state_.component>2 || (!state_.indexKnown && state_!=VgaDacWriteSnapshot{}))
            throw std::invalid_argument("VGA DAC write continuation differs");
        for(auto channel:state_.channels) if(channel>63)
            throw std::invalid_argument("VGA DAC channel differs");
    }
    const VgaDacWriteSnapshot& snapshot() const noexcept {return state_;}
    template<class SetPalette> void write(uint16_t port,uint8_t value,const SetPalette& setPalette) {
        auto next=state_;
        if(port==0x3c8) {
            next.index=value;next.component=0;next.indexKnown=true;
        } else if(port==0x3c9) {
            if(!next.indexKnown) throw std::domain_error("VGA DAC data precedes an observed index write");
            next.channels[next.component++]=value&63u;
            if(next.component==3) {
                const auto expand=[](uint8_t v) {return static_cast<uint8_t>((v<<2)|(v>>4));};
                setPalette(next.index,expand(next.channels[0]),expand(next.channels[1]),expand(next.channels[2]));
                next.index=static_cast<uint8_t>(next.index+1u);next.component=0;
            }
        } else throw std::domain_error("VGA DAC port is outside the write-only recovered profile");
        state_=next;
    }
private:
    VgaDacWriteSnapshot state_;
};
}
