#pragma once

#include "core/dos_time.hpp"
#include "core/timer_irq.hpp"

#include <bit>
#include <functional>
#include <stdexcept>

namespace lezac::core {

struct FrameWorldRasterSnapshot {
    DosGetTimeRegisters registers;
    uint16_t gameSegment=0;
    uint64_t dispatchedInstructions=0,transferredWords=0;
    bool returned=false;
    bool operator==(const FrameWorldRasterSnapshot&) const = default;
};

// Original driver 08AC:00F4..03C7. Dispatch/REP grants are not work-clock credits.
class FrameWorldRasterOperation {
public:
    using CopyBudget=std::function<uint16_t(uint16_t)>;
    FrameWorldRasterOperation(DosGetTimeRegisters r,uint16_t game)
        :state_{r,game} {
        if(r.cs!=static_cast<uint16_t>(game+0x8ac) || r.ds!=static_cast<uint16_t>(game+0xaa2) || r.ip!=0xf4)
            throw std::invalid_argument("World raster entry differs");
    }
    explicit FrameWorldRasterOperation(FrameWorldRasterSnapshot state):state_(state) {}
    const FrameWorldRasterSnapshot& snapshot() const noexcept {return state_;}
    bool returned() const noexcept {return state_.returned;}
    uint64_t advance(uint64_t budget,const TimerIrqBus& bus,const CopyBudget& copies) {
        uint64_t used=0;
        while(used<budget && !returned()) {instruction(bus,copies);++used;++state_.dispatchedInstructions;}
        return used;
    }
private:
    static constexpr uint32_t Arithmetic=0x8d5;
    FrameWorldRasterSnapshot state_;
    static uint8_t lo(uint16_t value) {return static_cast<uint8_t>(value);}
    void al(uint8_t value) {auto& ax=state_.registers.ax;ax=static_cast<uint16_t>((ax&0xff00)|value);}
    bool flag(uint32_t mask) const {return (state_.registers.flags&mask)!=0;}
    static uint32_t valueFlags(uint16_t value,unsigned bits) {
        return (value==0?0x40u:0u) | (value&(1u<<(bits-1))?0x80u:0u) |
            (std::popcount(static_cast<uint8_t>(value))%2==0?4u:0u);
    }
    uint16_t logic(uint16_t value,unsigned bits=16) {
        value&=static_cast<uint16_t>(bits==8?255:65535);
        state_.registers.flags=(state_.registers.flags&~Arithmetic)|valueFlags(value,bits);
        return value;
    }
    uint16_t arithmetic(uint16_t left,uint16_t right,bool subtract=false,unsigned bits=16) {
        const uint32_t mask=bits==8?255u:65535u,sign=1u<<(bits-1);
        const uint32_t wide=subtract?uint32_t{left}-right:uint32_t{left}+right;
        const auto value=static_cast<uint16_t>(wide&mask);
        uint32_t flags=valueFlags(value,bits)|((left^right^value)&16u);
        if(subtract?left<right:wide>mask) flags|=1;
        if(subtract?((left^right)&(left^value)&sign):(~(left^right)&(left^value)&sign)) flags|=0x800;
        state_.registers.flags=(state_.registers.flags&~Arithmetic)|flags;
        return value;
    }
    uint16_t increment(uint16_t value,bool subtract=false) {
        const auto carry=state_.registers.flags&1u;
        value=arithmetic(value,1,subtract);
        state_.registers.flags=(state_.registers.flags&~uint32_t{1})|carry;
        return value;
    }
    uint16_t shift(uint16_t value) {
        const auto result=static_cast<uint16_t>(value>>1);
        state_.registers.flags=(state_.registers.flags&~Arithmetic)|valueFlags(result,16)|16u|
            (value&1u)|(value&0x8000?0x800u:0u);
        return result;
    }
    void multiply(uint16_t factor) {
        auto& r=state_.registers;const uint32_t product=uint32_t{r.ax}*factor;
        r.ax=static_cast<uint16_t>(product);r.dx=static_cast<uint16_t>(product>>16);
        r.flags=(r.flags&~uint32_t{0x841})|(r.dx?0x801u:0u)|(r.ax==0?0x40u:0u);
    }
    void instruction(const TimerIrqBus& bus,const CopyBudget& copies) {
        auto& r=state_.registers;
        const auto push=[&](uint16_t value) {r.sp=static_cast<uint16_t>(r.sp-2u);bus.writeWord(r.ss,r.sp,value);};
        const auto pop=[&] {const auto value=bus.readWord(r.ss,r.sp);r.sp=static_cast<uint16_t>(r.sp+2u);return value;};
        const auto at=[&](uint16_t base,uint16_t offset) {return static_cast<uint16_t>(base+offset);};
        const auto branch=[&](bool condition,uint16_t yes,uint16_t no) {r.ip=condition?yes:no;};
        const auto loop=[&](uint16_t yes,uint16_t no) {r.cx=static_cast<uint16_t>(r.cx-1u);branch(r.cx!=0,yes,no);};
        const auto signedLess=[&] {return flag(0x80)!=flag(0x800);};
        const auto lodsb=[&] {al(bus.readByte(r.ds,r.si));r.si=static_cast<uint16_t>(r.si+(flag(0x400)?-1:1));};
        const auto stosb=[&] {bus.writeByte(r.es,r.di,lo(r.ax));r.di=static_cast<uint16_t>(r.di+(flag(0x400)?-1:1));};
        if(r.cs!=static_cast<uint16_t>(state_.gameSegment+0x8ac)) throw std::domain_error("World raster left recovered code");
        switch(r.ip) {
        case 0xf4:al(bus.readByte(r.ds,0xc49c));r.ip=0xf7;break;
        case 0xf7:arithmetic(lo(r.ax),1,true,8);r.ip=0xf9;break;
        case 0xf9:branch(!flag(0x40),0x15c,0xfb);break;
        case 0xfb:push(r.ds);r.ip=0xfc;break;
        case 0xfc:r.di=bus.readWord(r.ds,0xc498);r.es=bus.readWord(r.ds,0xc49a);r.ip=0x100;break;
        case 0x100:r.ax=bus.readWord(r.ds,0xc216);r.ip=0x103;break;
        case 0x103:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc20a));r.ip=0x107;break;
        case 0x107:r.bx=4;r.ip=0x10a;break;
        case 0x10a:r.dx=logic(0);r.ip=0x10c;break;
        case 0x10c:{const uint32_t value=(uint32_t{r.dx}<<16)|r.ax;if(!r.bx || value/r.bx>65535) throw std::domain_error("World raster DIV differs");r.ax=static_cast<uint16_t>(value/r.bx);r.dx=static_cast<uint16_t>(value%r.bx);r.ip=0x10e;break;}
        case 0x10e:r.di=arithmetic(r.di,r.ax);r.ip=0x110;break;
        case 0x110:r.ax=bus.readWord(r.ds,0xc218);r.ip=0x113;break;
        case 0x113:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc20c));r.ip=0x117;break;
        case 0x117:r.ax=shift(r.ax);r.ip=0x119;break;
        case 0x119:r.ax=shift(r.ax);r.ip=0x11b;break;
        case 0x11b:r.ax=shift(r.ax);r.ip=0x11d;break;
        case 0x11d:r.bx=bus.readWord(r.ds,0xc1f8);r.ip=0x121;break;
        case 0x121:multiply(r.bx);r.ip=0x123;break;
        case 0x123:r.di=arithmetic(r.di,r.ax);r.ip=0x125;break;
        case 0x125:push(r.es);r.ip=0x126;break;
        case 0x126:push(r.di);r.ip=0x127;break;
        case 0x127:r.di=bus.readWord(r.ds,0xc214);r.ip=0x12b;break;
        case 0x12b:r.es=bus.readWord(r.ds,0xc212);r.ip=0x12f;break;
        case 0x12f:r.di=arithmetic(r.di,bus.readWord(r.ds,0xc20a));r.ip=0x133;break;
        case 0x133:r.bx=bus.readWord(r.ds,0xc1ec);r.ip=0x137;break;
        case 0x137:r.ax=bus.readWord(r.ds,0xc20c);r.ip=0x13a;break;
        case 0x13a:multiply(r.bx);r.ip=0x13c;break;
        case 0x13c:r.di=arithmetic(r.di,r.ax);r.ip=0x13e;break;
        case 0x13e:r.ax=bus.readWord(r.ds,0xc1ec);r.ip=0x141;break;
        case 0x141:r.bx=bus.readWord(r.ds,0xc1ee);r.ip=0x145;break;
        case 0x145:r.ax=shift(r.ax);r.ip=0x147;break;
        case 0x147:r.dx=bus.readWord(r.ds,0xc1f6);r.ip=0x14b;break;
        case 0x14b:r.si=pop();r.ip=0x14c;break;
        case 0x14c:r.ds=pop();r.ip=0x14d;break;
        case 0x14d:r.cx=r.bx;r.ip=0x14f;break;
        case 0x14f:r.bx=r.cx;r.ip=0x151;break;
        case 0x151:r.cx=r.ax;r.ip=0x153;break;
        case 0x153:case 0x1ec:{
            const auto count=r.cx?copies(r.cx):uint16_t{0};
            if((r.cx && !count)||count>r.cx) throw std::invalid_argument("World raster REP grant differs");
            const auto step=flag(0x400)?-2:2;
            for(uint32_t i=0;i<count;++i) {const auto value=bus.readWord(r.ds,r.si);bus.writeWord(r.es,r.di,value);r.si=static_cast<uint16_t>(r.si+step);r.di=static_cast<uint16_t>(r.di+step);}
            r.cx=static_cast<uint16_t>(r.cx-count);state_.transferredWords+=count;
            if(!r.cx) r.ip=static_cast<uint16_t>(r.ip+2u);
            break;
        }
        case 0x155:r.cx=r.bx;r.ip=0x157;break;
        case 0x157:r.si=arithmetic(r.si,r.dx);r.ip=0x159;break;
        case 0x159:loop(0x14f,0x15b);break;
        case 0x15b:r.ds=pop();r.ip=0x15c;break;
        case 0x15c:r.di=bus.readWord(r.ds,0xc214);r.ip=0x160;break;
        case 0x160:r.es=bus.readWord(r.ds,0xc212);r.ip=0x164;break;
        case 0x164:r.si=bus.readWord(r.ds,0xc1f0);r.ip=0x168;break;
        case 0x168:r.bx=64;r.ip=0x16b;break;
        case 0x16b:r.cx=20;r.ip=0x16e;break;
        case 0x16e:al(bus.readByte(r.ds,0xc49c));r.ip=0x171;break;
        case 0x171:arithmetic(lo(r.ax),1,true,8);r.ip=0x173;break;
        case 0x173:branch(!flag(0x40),0x1c5,0x175);break;
        case 0x175:push(r.cx);r.ip=0x176;break;
        case 0x176:r.ax=bus.readWord(r.ds,0xc208);r.ip=0x179;break;
        case 0x179:bus.writeWord(r.ds,0xc210,r.ax);r.ip=0x17c;break;
        case 0x17c:r.cx=8;r.ip=0x17f;break;
        case 0x17f:push(r.si);r.ip=0x180;break;
        case 0x180:push(r.cx);r.ip=0x181;break;
        case 0x181:r.cx=bus.readWord(r.ds,0xc1ea);r.ip=0x185;break;
        case 0x185:push(r.ds);r.ip=0x186;break;
        case 0x186:r.ds=bus.readWord(r.ds,0xc1fe);r.ip=0x18a;break;
        case 0x18a:lodsb();r.ip=0x18b;break;
        case 0x18b:r.ds=pop();r.ip=0x18c;break;
        case 0x18c:r.ax=lo(r.ax);logic(0,8);r.ip=0x18e;break;
        case 0x18e:multiply(r.bx);r.ip=0x190;break;
        case 0x190:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc210));r.ip=0x194;break;
        case 0x194:push(r.si);r.ip=0x195;break;
        case 0x195:r.si=r.ax;r.ip=0x197;break;
        case 0x197:push(r.cx);r.ip=0x198;break;
        case 0x198:r.cx=4;r.ip=0x19b;break;
        case 0x19b:r.ax=bus.readWord(r.ds,at(r.si,0x2136));r.ip=0x19f;break;
        case 0x19f:bus.writeWord(r.es,r.di,logic(bus.readWord(r.es,r.di)&r.ax));r.ip=0x1a2;break;
        case 0x1a2:r.ax=bus.readWord(r.ds,r.si);r.si=static_cast<uint16_t>(r.si+(flag(0x400)?-2:2));r.ip=0x1a3;break;
        case 0x1a3:bus.writeWord(r.es,r.di,logic(bus.readWord(r.es,r.di)|r.ax));r.ip=0x1a6;break;
        case 0x1a6:r.di=arithmetic(r.di,2);r.ip=0x1a9;break;
        case 0x1a9:loop(0x19b,0x1ab);break;
        case 0x1ab:r.cx=pop();r.ip=0x1ac;break;
        case 0x1ac:r.si=pop();r.ip=0x1ad;break;
        case 0x1ad:loop(0x185,0x1af);break;
        case 0x1af:r.ax=bus.readWord(r.ds,0xc210);r.ip=0x1b2;break;
        case 0x1b2:r.ax=arithmetic(r.ax,8);r.ip=0x1b5;break;
        case 0x1b5:bus.writeWord(r.ds,0xc210,r.ax);r.ip=0x1b8;break;
        case 0x1b8:r.cx=pop();r.ip=0x1b9;break;
        case 0x1b9:r.si=pop();r.ip=0x1ba;break;
        case 0x1ba:loop(0x17f,0x1bc);break;
        case 0x1bc:r.si=arithmetic(r.si,bus.readWord(r.ds,0xc204));r.ip=0x1c0;break;
        case 0x1c0:r.cx=pop();r.ip=0x1c1;break;
        case 0x1c1:loop(0x175,0x1c3);break;
        case 0x1c3:r.ip=0x207;break;
        case 0x1c5:push(r.cx);r.ip=0x1c6;break;
        case 0x1c6:r.ax=bus.readWord(r.ds,0xc208);r.ip=0x1c9;break;
        case 0x1c9:bus.writeWord(r.ds,0xc210,r.ax);r.ip=0x1cc;break;
        case 0x1cc:r.cx=8;r.ip=0x1cf;break;
        case 0x1cf:push(r.si);r.ip=0x1d0;break;
        case 0x1d0:push(r.cx);r.ip=0x1d1;break;
        case 0x1d1:r.cx=bus.readWord(r.ds,0xc1ea);r.ip=0x1d5;break;
        case 0x1d5:push(r.ds);r.ip=0x1d6;break;
        case 0x1d6:r.ds=bus.readWord(r.ds,0xc1fe);r.ip=0x1da;break;
        case 0x1da:lodsb();r.ip=0x1db;break;
        case 0x1db:r.ds=pop();r.ip=0x1dc;break;
        case 0x1dc:r.ax=lo(r.ax);logic(0,8);r.ip=0x1de;break;
        case 0x1de:multiply(r.bx);r.ip=0x1e0;break;
        case 0x1e0:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc210));r.ip=0x1e4;break;
        case 0x1e4:push(r.si);r.ip=0x1e5;break;
        case 0x1e5:r.si=r.ax;r.ip=0x1e7;break;
        case 0x1e7:r.ax=r.cx;r.ip=0x1e9;break;
        case 0x1e9:r.cx=4;r.ip=0x1ec;break;
        case 0x1ee:r.cx=r.ax;r.ip=0x1f0;break;
        case 0x1f0:r.si=pop();r.ip=0x1f1;break;
        case 0x1f1:loop(0x1d5,0x1f3);break;
        case 0x1f3:r.ax=bus.readWord(r.ds,0xc210);r.ip=0x1f6;break;
        case 0x1f6:r.ax=arithmetic(r.ax,8);r.ip=0x1f9;break;
        case 0x1f9:bus.writeWord(r.ds,0xc210,r.ax);r.ip=0x1fc;break;
        case 0x1fc:r.cx=pop();r.ip=0x1fd;break;
        case 0x1fd:r.si=pop();r.ip=0x1fe;break;
        case 0x1fe:loop(0x1cf,0x200);break;
        case 0x200:r.si=arithmetic(r.si,bus.readWord(r.ds,0xc204));r.ip=0x204;break;
        case 0x204:r.cx=pop();r.ip=0x205;break;
        case 0x205:loop(0x1c5,0x207);break;
        case 0x207:r.cx=static_cast<uint16_t>((r.cx&0xff00)|bus.readByte(r.ds,0xc496));r.ip=0x20b;break;
        case 0x20b:r.cx=lo(r.cx);logic(0,8);r.ip=0x20d;break;
        case 0x20d:arithmetic(r.cx,0,true);r.ip=0x210;break;
        case 0x210:branch(!flag(0x40),0x215,0x212);break;
        case 0x212:r.ip=0x3c7;break;
        case 0x215:r.bx=logic(0);r.ip=0x217;break;
        case 0x217:al(bus.readByte(r.ds,at(r.bx,0xc222)));r.ip=0x21b;break;
        case 0x21b:r.ax=lo(r.ax);logic(0,8);r.ip=0x21d;break;
        case 0x21d:bus.writeWord(r.ds,0xc202,r.ax);r.ip=0x220;break;
        case 0x220:al(bus.readByte(r.ds,at(r.bx,0xc223)));r.ip=0x224;break;
        case 0x224:bus.writeWord(r.ds,0xc200,r.ax);r.ip=0x227;break;
        case 0x227:r.ax=bus.readWord(r.ds,at(r.bx,0xc21e));r.ip=0x22b;break;
        case 0x22b:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc216),true);r.ip=0x22f;break;
        case 0x22f:bus.writeWord(r.ds,0xc21a,r.ax);r.ip=0x232;break;
        case 0x232:r.ax=bus.readWord(r.ds,at(r.bx,0xc220));r.ip=0x236;break;
        case 0x236:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc218),true);r.ip=0x23a;break;
        case 0x23a:bus.writeWord(r.ds,0xc21c,r.ax);r.ip=0x23d;break;
        case 0x23d:arithmetic(r.ax,bus.readWord(r.ds,0xc1ee),true);r.ip=0x241;break;
        case 0x241:branch(signedLess(),0x246,0x243);break;
        case 0x243:r.ip=0x2e2;break;
        case 0x246:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc200));r.ip=0x24a;break;
        case 0x24a:arithmetic(r.ax,0,true);r.ip=0x24d;break;
        case 0x24d:branch(!flag(0x40)&&!signedLess(),0x252,0x24f);break;
        case 0x24f:r.ip=0x2e2;break;
        case 0x252:r.ax=bus.readWord(r.ds,0xc21a);r.ip=0x255;break;
        case 0x255:arithmetic(r.ax,bus.readWord(r.ds,0xc1ec),true);r.ip=0x259;break;
        case 0x259:branch(signedLess(),0x25e,0x25b);break;
        case 0x25b:r.ip=0x2e2;break;
        case 0x25e:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc202));r.ip=0x262;break;
        case 0x262:arithmetic(r.ax,0,true);r.ip=0x265;break;
        case 0x265:branch(flag(0x40)||signedLess(),0x2e2,0x267);break;
        case 0x267:r.ax=bus.readWord(r.ds,0xc21c);r.ip=0x26a;break;
        case 0x26a:arithmetic(r.ax,0xffff,true);r.ip=0x26d;break;
        case 0x26d:branch(!flag(0x40)&&!signedLess(),0x272,0x26f);break;
        case 0x26f:r.ip=0x2ef;break;
        case 0x272:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc200));r.ip=0x276;break;
        case 0x276:r.ax=increment(r.ax,true);r.ip=0x277;break;
        case 0x277:arithmetic(r.ax,bus.readWord(r.ds,0xc1ee),true);r.ip=0x27b;break;
        case 0x27b:branch(!signedLess(),0x2ef,0x27d);break;
        case 0x27d:r.ax=bus.readWord(r.ds,0xc21a);r.ip=0x280;break;
        case 0x280:arithmetic(r.ax,0xffff,true);r.ip=0x283;break;
        case 0x283:branch(flag(0x40)||signedLess(),0x2ef,0x285);break;
        case 0x285:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc202));r.ip=0x289;break;
        case 0x289:r.ax=increment(r.ax,true);r.ip=0x28a;break;
        case 0x28a:arithmetic(r.ax,bus.readWord(r.ds,0xc1ec),true);r.ip=0x28e;break;
        case 0x28e:branch(!signedLess(),0x2ef,0x290);break;
        case 0x290:push(r.cx);r.ip=0x291;break;
        case 0x291:r.es=bus.readWord(r.ds,0xc212);r.ip=0x295;break;
        case 0x295:r.di=bus.readWord(r.ds,0xc214);r.ip=0x299;break;
        case 0x299:r.ax=bus.readWord(r.ds,0xc21c);r.ip=0x29c;break;
        case 0x29c:r.cx=r.bx;r.ip=0x29e;break;
        case 0x29e:r.bx=bus.readWord(r.ds,0xc1ec);r.ip=0x2a2;break;
        case 0x2a2:multiply(r.bx);r.ip=0x2a4;break;
        case 0x2a4:r.bx=r.cx;r.ip=0x2a6;break;
        case 0x2a6:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc21a));r.ip=0x2aa;break;
        case 0x2aa:r.di=arithmetic(r.di,r.ax);r.ip=0x2ac;break;
        case 0x2ac:r.si=bus.readWord(r.ds,at(r.bx,0xc224));r.ip=0x2b0;break;
        case 0x2b0:r.ax=bus.readWord(r.ds,0xc1ec);r.ip=0x2b3;break;
        case 0x2b3:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc202),true);r.ip=0x2b7;break;
        case 0x2b7:bus.writeWord(r.ds,0xc1e8,r.ax);r.ip=0x2ba;break;
        case 0x2ba:r.cx=bus.readWord(r.ds,0xc200);r.ip=0x2be;break;
        case 0x2be:r.dx=bus.readWord(r.ds,0xc202);r.ip=0x2c2;break;
        case 0x2c2:push(r.bx);r.ip=0x2c3;break;
        case 0x2c3:r.bx=bus.readWord(r.ds,0xc1e8);r.ip=0x2c7;break;
        case 0x2c7:push(r.ds);r.ip=0x2c8;break;
        case 0x2c8:r.ds=bus.readWord(r.ds,0xc1fa);r.ip=0x2cc;break;
        case 0x2cc:push(r.cx);r.ip=0x2cd;break;
        case 0x2cd:r.cx=r.dx;r.ip=0x2cf;break;
        case 0x2cf:lodsb();r.ip=0x2d0;break;
        case 0x2d0:arithmetic(lo(r.ax),0,true,8);r.ip=0x2d2;break;
        case 0x2d2:branch(!flag(0x40),0x2d7,0x2d4);break;
        case 0x2d4:r.di=increment(r.di);r.ip=0x2d5;break;
        case 0x2d5:r.ip=0x2d8;break;
        case 0x2d7:stosb();r.ip=0x2d8;break;
        case 0x2d8:loop(0x2cf,0x2da);break;
        case 0x2da:r.cx=pop();r.ip=0x2db;break;
        case 0x2db:r.di=arithmetic(r.di,r.bx);r.ip=0x2dd;break;
        case 0x2dd:loop(0x2cc,0x2df);break;
        case 0x2df:r.ds=pop();r.ip=0x2e0;break;
        case 0x2e0:r.bx=pop();r.ip=0x2e1;break;
        case 0x2e1:r.cx=pop();r.ip=0x2e2;break;
        case 0x2e2:r.ip=0x2e3;break;
        case 0x2e3:r.bx=arithmetic(r.bx,8);r.ip=0x2e6;break;
        case 0x2e6:r.cx=increment(r.cx,true);r.ip=0x2e7;break;
        case 0x2e7:branch(r.cx==0,0x2ec,0x2e9);break;
        case 0x2e9:r.ip=0x217;break;
        case 0x2ec:r.ip=0x3c7;break;
        case 0x2ef:push(r.cx);r.ip=0x2f0;break;
        case 0x2f0:bus.writeWord(r.ds,0xc210,0);r.ip=0x2f6;break;
        case 0x2f6:r.es=bus.readWord(r.ds,0xc212);r.ip=0x2fa;break;
        case 0x2fa:r.di=bus.readWord(r.ds,0xc214);r.ip=0x2fe;break;
        case 0x2fe:r.ax=bus.readWord(r.ds,0xc21c);r.ip=0x301;break;
        case 0x301:r.si=bus.readWord(r.ds,at(r.bx,0xc224));r.ip=0x305;break;
        case 0x305:r.ax=bus.readWord(r.ds,0xc21c);r.ip=0x308;break;
        case 0x308:arithmetic(r.ax,0,true);r.ip=0x30b;break;
        case 0x30b:branch(!signedLess(),0x31f,0x30d);break;
        case 0x30d:r.cx=r.bx;r.ip=0x30f;break;
        case 0x30f:r.bx=bus.readWord(r.ds,0xc202);r.ip=0x313;break;
        case 0x313:r.ax=arithmetic(0,r.ax,true);r.ip=0x315;break;
        case 0x315:bus.writeWord(r.ds,0xc200,arithmetic(bus.readWord(r.ds,0xc200),r.ax,true));r.ip=0x319;break;
        case 0x319:multiply(r.bx);r.ip=0x31b;break;
        case 0x31b:r.si=arithmetic(r.si,r.ax);r.ip=0x31d;break;
        case 0x31d:r.bx=r.cx;r.ip=0x31f;break;
        case 0x31f:r.ax=bus.readWord(r.ds,0xc21a);r.ip=0x322;break;
        case 0x322:arithmetic(r.ax,0,true);r.ip=0x325;break;
        case 0x325:branch(!signedLess(),0x330,0x327);break;
        case 0x327:r.ax=arithmetic(0,r.ax,true);r.ip=0x329;break;
        case 0x329:r.si=arithmetic(r.si,r.ax);r.ip=0x32b;break;
        case 0x32b:bus.writeWord(r.ds,0xc210,r.ax);r.ip=0x32e;break;
        case 0x32e:r.ip=0x341;break;
        case 0x330:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc202));r.ip=0x334;break;
        case 0x334:arithmetic(r.ax,bus.readWord(r.ds,0xc1ec),true);r.ip=0x338;break;
        case 0x338:branch(flag(0x40)||signedLess(),0x341,0x33a);break;
        case 0x33a:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc1ec),true);r.ip=0x33e;break;
        case 0x33e:bus.writeWord(r.ds,0xc210,r.ax);r.ip=0x341;break;
        case 0x341:r.ax=bus.readWord(r.ds,0xc21c);r.ip=0x344;break;
        case 0x344:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc200));r.ip=0x348;break;
        case 0x348:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc1ee),true);r.ip=0x34c;break;
        case 0x34c:arithmetic(r.ax,0xffff,true);r.ip=0x34f;break;
        case 0x34f:branch(flag(0x40)||signedLess(),0x35b,0x351);break;
        case 0x351:r.cx=r.ax;r.ip=0x353;break;
        case 0x353:r.ax=bus.readWord(r.ds,0xc200);r.ip=0x356;break;
        case 0x356:r.ax=arithmetic(r.ax,r.cx,true);r.ip=0x358;break;
        case 0x358:bus.writeWord(r.ds,0xc200,r.ax);r.ip=0x35b;break;
        case 0x35b:r.ax=bus.readWord(r.ds,0xc202);r.ip=0x35e;break;
        case 0x35e:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc210),true);r.ip=0x362;break;
        case 0x362:bus.writeWord(r.ds,0xc202,r.ax);r.ip=0x365;break;
        case 0x365:r.ax=bus.readWord(r.ds,0xc21c);r.ip=0x368;break;
        case 0x368:arithmetic(r.ax,0,true);r.ip=0x36b;break;
        case 0x36b:branch(!signedLess(),0x373,0x36d);break;
        case 0x36d:bus.writeWord(r.ds,0xc21c,0);r.ip=0x373;break;
        case 0x373:r.ax=bus.readWord(r.ds,0xc21a);r.ip=0x376;break;
        case 0x376:arithmetic(r.ax,0,true);r.ip=0x379;break;
        case 0x379:branch(!signedLess(),0x381,0x37b);break;
        case 0x37b:bus.writeWord(r.ds,0xc21a,0);r.ip=0x381;break;
        case 0x381:r.ax=bus.readWord(r.ds,0xc21c);r.ip=0x384;break;
        case 0x384:r.cx=r.bx;r.ip=0x386;break;
        case 0x386:r.bx=bus.readWord(r.ds,0xc1ec);r.ip=0x38a;break;
        case 0x38a:multiply(r.bx);r.ip=0x38c;break;
        case 0x38c:r.bx=r.cx;r.ip=0x38e;break;
        case 0x38e:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc21a));r.ip=0x392;break;
        case 0x392:r.di=arithmetic(r.di,r.ax);r.ip=0x394;break;
        case 0x394:r.ax=bus.readWord(r.ds,0xc1ec);r.ip=0x397;break;
        case 0x397:r.ax=arithmetic(r.ax,bus.readWord(r.ds,0xc202),true);r.ip=0x39b;break;
        case 0x39b:bus.writeWord(r.ds,0xc1e8,r.ax);r.ip=0x39e;break;
        case 0x39e:r.cx=bus.readWord(r.ds,0xc200);r.ip=0x3a2;break;
        case 0x3a2:push(r.cx);r.ip=0x3a3;break;
        case 0x3a3:r.cx=bus.readWord(r.ds,0xc202);r.ip=0x3a7;break;
        case 0x3a7:push(r.ds);r.ip=0x3a8;break;
        case 0x3a8:r.ds=bus.readWord(r.ds,0xc1fa);r.ip=0x3ac;break;
        case 0x3ac:lodsb();r.ip=0x3ad;break;
        case 0x3ad:arithmetic(lo(r.ax),0,true,8);r.ip=0x3af;break;
        case 0x3af:branch(!flag(0x40),0x3b4,0x3b1);break;
        case 0x3b1:r.di=increment(r.di);r.ip=0x3b2;break;
        case 0x3b2:r.ip=0x3b5;break;
        case 0x3b4:stosb();r.ip=0x3b5;break;
        case 0x3b5:loop(0x3ac,0x3b7);break;
        case 0x3b7:r.ds=pop();r.ip=0x3b8;break;
        case 0x3b8:r.cx=pop();r.ip=0x3b9;break;
        case 0x3b9:r.di=arithmetic(r.di,bus.readWord(r.ds,0xc1e8));r.ip=0x3bd;break;
        case 0x3bd:r.si=arithmetic(r.si,bus.readWord(r.ds,0xc210));r.ip=0x3c1;break;
        case 0x3c1:loop(0x3a2,0x3c3);break;
        case 0x3c3:r.cx=pop();r.ip=0x3c4;break;
        case 0x3c4:r.ip=0x2e3;break;
        case 0x3c7:r.ip=pop();r.cs=pop();state_.returned=true;break;
        default:throw std::domain_error("World raster reached an unrecovered instruction");
        }
    }
};

} // namespace lezac::core
