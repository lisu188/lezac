#include "core/vga_dac_writer.hpp"
#include "core/pacing_device_clock.hpp"
#include <iostream>
#include <array>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool good,const char* message) {if(!good) throw std::runtime_error(message);}
void test() {
    using Color=std::array<uint8_t,4>;
    std::vector<Color> colors;
    const auto save=[&](uint8_t index,uint8_t r,uint8_t g,uint8_t b) {colors.push_back(Color{index,r,g,b});};
    VgaDacWriter writer;
    bool rejected=false;
    try {writer.write(0x3c9,1,save);} catch(const std::domain_error&) {rejected=true;}
    require(rejected && colors.empty(),"Unobserved initial DAC index accepted");
    for(unsigned value=0;value<256;++value) {
        writer.write(0x3c8,255,save);
        for(unsigned component=0;component<3;++component) {
            writer.write(0x3c9,static_cast<uint8_t>(value),save);
            writer=VgaDacWriter(writer.snapshot());
        }
        const auto channel=static_cast<uint8_t>(((value&63u)<<2)|((value&63u)>>4));
        require(colors.back()==Color{255,channel,channel,channel},"Six-bit DAC expansion differs");
        require(writer.snapshot().index==0 && writer.snapshot().component==0,"DAC write index did not wrap");
    }
    writer.write(0x3c8,7,save);writer.write(0x3c9,1,save);writer.write(0x3c9,2,save);
    const auto size=colors.size();
    writer.write(0x3c8,9,save);
    writer.write(0x3c9,63,save);writer.write(0x3c9,0,save);writer.write(0x3c9,31,save);
    require(colors.size()==size+1 && colors.back()==Color{9,255,0,125},"DAC index restart retained partial components");
    const auto before=writer.snapshot();rejected=false;
    try {writer.write(0x3c6,0,save);} catch(const std::domain_error&) {rejected=true;}
    require(rejected && writer.snapshot()==before,"Unsupported DAC port mutated continuation");
    writer.write(0x3c9,1,save);writer.write(0x3c9,2,save);
    const auto partial=writer.snapshot();rejected=false;
    try {writer.write(0x3c9,3,[](uint8_t,uint8_t,uint8_t,uint8_t) {throw std::runtime_error("callback failed");});}
    catch(const std::runtime_error&) {rejected=true;}
    require(rejected && writer.snapshot()==partial,"Failed palette callback corrupted continuation");
    writer.write(0x3c9,3,save);
    for(unsigned invalid=0;invalid<3;++invalid) {
        auto state=writer.snapshot();
        if(invalid==0) state.component=3;
        if(invalid==1) state.channels[0]=64;
        if(invalid==2) state.indexKnown=false;
        rejected=false;
        try {VgaDacWriter invalidWriter(state);} catch(const std::invalid_argument&) {rejected=true;}
        require(rejected,"Invalid DAC continuation accepted");
    }
    PacingDeviceClockSnapshot state;
    state.devices={5,3,0,0,4,50,200,200,0,0,0x8e,1,0,0,0,0,0,0,0,0,0,1,0,0,0};
    state.tickers={11,10};
    for(auto& delay:state.delayBits) delay=std::bit_cast<uint64_t>(1.0);
    state.clock.cycleLeft=100;state.clock.pitDelay=1000.0f/(1193182.0f/65536.0f);
    state.palette.emplace();
    state.palette->format={32,4,0xff0000,0xff00,0xff,0,16,8,0,0,0,1,1,0,0,0,0,0};
    PacingDeviceClock clock(state);
    clock.setPaletteColor(9,255,0,125);
    auto after=clock.snapshot();
    require(after.palette->rgb[9]==0xff007d && after.palette->first==9 && after.palette->last==9,
            "Renderer palette programming differs");
    require(after.palette->lut==state.palette->lut && after.palette->modified==state.palette->modified &&
            after.clock==state.clock,"DAC programming prematurely committed a LUT or charged CPU work");
    clock.setPaletteColor(9,255,0,125);clock.setPaletteColor(3,1,2,3);
    after=clock.snapshot();require(after.palette->first==3 && after.palette->last==9,"Palette dirty range differs");
    require(PacingDeviceClock(after).snapshot()==after,"Palette write snapshot restore differs");
    state.palette.reset();PacingDeviceClock absent(state);rejected=false;
    try {absent.setPaletteColor(0,1,2,3);} catch(const std::logic_error&) {rejected=true;}
    require(rejected,"Palette write without an observed renderer was accepted");
    std::cout<<"vga_dac_writer_unit=ok byte_values=256 continuation_rejections=3 snapshot_restore=1 initial_index_inferred=0\n";
}
}
int main() {try {test();return 0;} catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}}
