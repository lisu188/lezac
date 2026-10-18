#include "core/frame_render.hpp"

#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool value,const char* message) {if(!value) throw std::runtime_error(message);}
std::vector<uint8_t> readFile(const std::filesystem::path& path) {
    std::ifstream file(path,std::ios::binary);require(file.good(),"Cannot read render input");
    return {std::istreambuf_iterator<char>(file),std::istreambuf_iterator<char>()};
}
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    uint32_t number(unsigned count) {
        require(count<=4 && at+count<=bytes.size(),"Truncated render corpus");uint32_t value=0;
        for(unsigned i=0;i<count;++i) value|=uint32_t{bytes[at++]}<<(i*8);
        return value;
    }
    uint64_t wide() {const uint64_t low=number(4);return low|(uint64_t{number(4)}<<32);}
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;
        for(auto* value : {&r.ax,&r.bx,&r.cx,&r.dx,&r.si,&r.di,&r.bp,&r.cs,&r.ds,&r.es,&r.ss,&r.sp,&r.ip})
            *value=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
};
struct Write {uint32_t address;uint8_t size;uint16_t value;bool operator==(const Write&) const = default;};
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576);std::vector<Write> writes;
    static uint32_t address(uint16_t s,uint16_t o) {return (uint32_t{s}*16+o)&0xfffffu;}
    uint16_t word(uint16_t s,uint16_t o) const {const auto a=address(s,o);return static_cast<uint16_t>(bytes[a]|(uint16_t{bytes[(a+1)&0xfffffu]}<<8));}
    void store(uint16_t s,uint16_t o,uint16_t value,bool record=false) {
        const auto a=address(s,o);bytes[a]=static_cast<uint8_t>(value);bytes[(a+1)&0xfffffu]=static_cast<uint8_t>(value>>8);
        if(record) writes.push_back({a,2,value});
    }
    TimerIrqBus bus() {
        TimerIrqBus b;
        b.readByte=[this](uint16_t s,uint16_t o){return bytes[address(s,o)];};
        b.readWord=[this](uint16_t s,uint16_t o){return word(s,o);};
        b.writeByte=[this](uint16_t s,uint16_t o,uint8_t value){const auto a=address(s,o);bytes[a]=value;writes.push_back({a,1,value});};
        b.writeWord=[this](uint16_t s,uint16_t o,uint16_t value){store(s,o,value,true);};
        return b;
    }
    uint64_t fingerprint() const {
        uint64_t value=14695981039346656037ull;
        for(auto byte:bytes) value=(value^byte)*1099511628211ull;
        return value;
    }
};
struct Sprite {uint16_t width,height,source;};
struct Assets {
    std::vector<uint8_t> tiles,pixels,image;std::vector<Sprite> sprites;
    explicit Assets(const std::filesystem::path& root) {
        auto raw=readFile(root/"CARO.CAR");require(raw.size()==8450 && raw[0]==0 && raw[1]==132,"Tile asset differs");
        tiles.assign(raw.begin()+2,raw.end());raw=readFile(root/"BOMOMIMK.SPR");require(!raw.empty(),"Sprite asset empty");size_t at=1;
        for(unsigned i=0;i<raw[0];++i) {
            require(at+2<=raw.size(),"Sprite header truncated");const uint16_t w=raw[at++],h=raw[at++];
            const size_t count=size_t{w}*h;require(w && h && at+count<=raw.size() && pixels.size()<65536,"Sprite payload differs");
            sprites.push_back({w,h,static_cast<uint16_t>(pixels.size())});
            pixels.insert(pixels.end(),raw.begin()+static_cast<std::ptrdiff_t>(at),raw.begin()+static_cast<std::ptrdiff_t>(at+count));at+=count;
        }
        require(at==raw.size(),"Sprite asset tail differs");raw=readFile(root/"LEZAC.EXE");
        const auto word=[&](size_t offset){require(offset+2<=raw.size(),"MZ header differs");return static_cast<uint16_t>(raw[offset]|(uint16_t{raw[offset+1]}<<8));};
        const size_t header=size_t{word(8)}*16;require(header==0x770 && header<raw.size(),"MZ image differs");
        image.assign(raw.begin()+static_cast<std::ptrdiff_t>(header),raw.end());
        for(size_t i=0;i<word(6);++i) {
            const size_t entry=word(24)+i*4,offset=word(entry)+size_t{word(entry+2)}*16;
            require(offset+2<=image.size(),"MZ relocation differs");
            const auto value=static_cast<uint16_t>((image[offset]|(uint16_t{image[offset+1]}<<8))+0x1000);
            image[offset]=static_cast<uint8_t>(value);image[offset+1]=static_cast<uint8_t>(value>>8);
        }
    }
};
constexpr uint32_t Data=0x1aa20,Map=0x30000,Buffer=0x40010,Backdrop=0x50020,Sprites=0x60030,Stack=0x83fa4;
struct Case {
    std::array<uint16_t,12> p{};DosGetTimeRegisters initial,final;
    uint32_t transfers=0,steps=0,repStops=0;bool error=false;uint64_t initialFingerprint=0,finalFingerprint=0;
    std::vector<Write> writes;
};
Memory initialMemory(const Case& sample,const Assets& assets) {
    Memory m;const auto& p=sample.p;const uint32_t index=p[0],pitch=p[1]==1?320u:160u;
    std::copy(assets.image.begin(),assets.image.end(),m.bytes.begin()+0x10000);
    for(uint32_t i=0;i<65538;++i) {
        m.bytes[Data+i]=static_cast<uint8_t>(i*13+(i>>5)*7+(i>>16)*61+index);
        m.bytes[Map+i]=static_cast<uint8_t>((i*17+(i>>6)*3+index)%132);
        m.bytes[Buffer+i]=static_cast<uint8_t>(i*37+(i>>8)*11+(i>>16)*109+(index+1)*13);
        m.bytes[Backdrop+i]=static_cast<uint8_t>(6+(i%pitch/16+i/pitch/8+index)%40);
        m.bytes[Sprites+i]=static_cast<uint8_t>(i%7==0?0:(i*13+index)&255);
        m.bytes[0xa0000+i]=static_cast<uint8_t>(i*11+(i>>8)*7+index);
    }
    std::copy(assets.tiles.begin(),assets.tiles.end(),m.bytes.begin()+Data+0x36);
    for(size_t i=0;i<assets.tiles.size();++i) m.bytes[Data+0x2136+i]=assets.tiles[i]==0?255:0;
    std::copy(assets.pixels.begin(),assets.pixels.end(),m.bytes.begin()+Sprites);
    for(uint32_t i=0;i<72;++i) m.bytes[Stack+i]=static_cast<uint8_t>(i*29+index*7+11);
    struct Word {uint16_t offset,value;};
    for(const auto& [o,v] : std::initializer_list<Word>{
        {0xc1ea,static_cast<uint16_t>(pitch/8)},{0xc1ec,static_cast<uint16_t>(pitch)},
        {0xc1ee,160},{0xc1f0,2},{0xc1f6,0},{0xc1f8,static_cast<uint16_t>(pitch)},
        {0xc1fa,0x6003},{0xc1fe,0x3000},{0xc208,0x36},{0xc20a,7},{0xc20c,7},
        {0xc212,0x4001},{0xc214,p[10]},{0xc216,16},{0xc218,8},{0xc498,48},{0xc49a,0x5002}}) m.store(0x1aa2,o,v);
    for(uint16_t o : std::array<uint16_t,6>{0xc1e8,0xc200,0xc202,0xc210,0xc21a,0xc21c}) m.store(0x1aa2,o,0xa55a);
    m.bytes[Data+0xc49c]=static_cast<uint8_t>(p[4]);m.bytes[Data+0xc496]=22;
    for(uint32_t i=0;i<22;++i) {
        const auto& s=assets.sprites[(i*7)%assets.sprites.size()];const int w=s.width,h=s.height,span=static_cast<int>(pitch);
        const std::array<std::array<int,2>,22> positions={{{20,20},{-w,20},{-w+1,20},{-1,20},{span-1,20},{span,20},
            {span-w,20},{span-w+1,20},{20,-h},{20,-h+1},{20,-1},{20,159},{20,160},{20,160-h},{20,161-h},
            {-1,-1},{span-1,159},{-32768,20},{32767,20},{20,-32768},{20,32767},{span-w,160-h}}};
        const auto& point=positions[i];const auto o=static_cast<uint16_t>(0xc21e + i*8);
        m.store(0x1aa2,o,static_cast<uint16_t>(point[0]+16));m.store(0x1aa2,static_cast<uint16_t>(o+2),static_cast<uint16_t>(point[1]+8));
        m.bytes[Data+o+4]=static_cast<uint8_t>(w);m.bytes[Data+o+5]=static_cast<uint8_t>(h);m.store(0x1aa2,static_cast<uint16_t>(o+6),s.source);
    }
    const auto half=static_cast<uint16_t>(pitch/2-8);
    for(const auto& [o,v] : std::initializer_list<Word>{{0x1afa,p[11]},{0x78bc,half},{0x78be,static_cast<uint16_t>(half/8)},
        {0x2094,static_cast<uint16_t>((60-pitch/8)*8)},{0x2096,480},{0x2098,0},{0x79f0,1284},{0x79f2,1444},
        {0xc204,60},{0xc206,static_cast<uint16_t>(320-pitch)},{0xc21e,p[6]},{0xc220,p[7]},{0xc226,p[8]},{0xc228,p[9]}}) m.store(0x1aa2,o,v);
    m.bytes[Data+0x79e6]=static_cast<uint8_t>(p[2]);m.bytes[Data+0x79e7]=static_cast<uint8_t>(p[3]);
    m.store(0x8000,0x3fe4,index%2?0x7a4c:0x7a2a);m.store(0x8000,0x3fe6,0x1000);
    return m;
}
void dumpMemory(const std::filesystem::path& path,const Memory& m) {
    std::ofstream file(path,std::ios::binary);file.write(reinterpret_cast<const char*>(m.bytes.data()),static_cast<std::streamsize>(m.bytes.size()));
    require(file.good(),"Render memory dump failed");
}
void replay(const char* corpus,const std::filesystem::path& root,const std::filesystem::path& dump) {
    Reader r{readFile(corpus)};for(char c:std::string("LZREND01")) require(r.number(1)==static_cast<uint8_t>(c),"Render magic differs");
    const auto count=r.number(4);require(count==26,"Render case count differs");Assets assets(root);uint64_t replays=0,writes=0,errors=0;
    if(!dump.empty()) std::filesystem::create_directories(dump);
    for(uint32_t index=0;index<count;++index) {
        Case s;for(auto& v:s.p)v=static_cast<uint16_t>(r.number(2));require(s.p[0]==index,"Render index differs");
        s.initial=r.registers();s.final=r.registers();s.transfers=r.number(4);s.steps=r.number(4);s.repStops=r.number(4);s.error=r.number(1)!=0;
        s.initialFingerprint=r.wide();s.finalFingerprint=r.wide();const auto events=r.number(4);require(events<1000000,"Render write count differs");
        for(uint32_t i=0;i<events;++i) {const auto a=r.number(4);const auto size=static_cast<uint8_t>(r.number(1));const auto v=static_cast<uint16_t>(r.number(2));s.writes.push_back({a,size,v});}
        struct Budget {uint64_t instructions;uint16_t words;};
        for(const auto& budget:std::array<Budget,3>{{{1,1},{17,3},{4096,65535}}}) {
            auto m=initialMemory(s,assets);require(m.fingerprint()==s.initialFingerprint,"Render complete initial memory differs");
            if(!dump.empty() && budget.instructions==4096) dumpMemory(dump/(std::to_string(index)+"-initial.ram"),m);
            const auto bus=m.bus();const auto grant=[&](uint16_t n){return std::min(n,budget.words);};FrameRenderOperation op(s.initial,0x1000);
            const auto before=op.snapshot();require(op.advance(0,bus,grant)==0 && op.snapshot()==before && m.writes.empty(),"Zero render budget changed state");
            uint64_t steps=0;
            while(!op.finished()) {const auto used=op.advance(budget.instructions,bus,grant);require(used && used<=budget.instructions,"Render dispatch budget differs");steps+=used;require(steps<4000000,"Render did not finish");op=FrameRenderOperation(op.snapshot());}
            require(op.returned()!=s.error,"Render outcome differs");require(op.snapshot().registers==s.final,"Render endpoint registers/flags differ");
            require(op.snapshot().transferredWords==s.transfers,"Render REP transfer count differs");
            require(m.writes==s.writes,"Render original write sequence differs");require(m.fingerprint()==s.finalFingerprint,"Render complete final memory differs");
            if(budget.words==1) require(steps+s.repStops==s.steps,"Render single-word dispatch count differs");
            if(!dump.empty() && budget.instructions==4096) dumpMemory(dump/(std::to_string(index)+"-final.ram"),m);
            const auto final=op.snapshot();require(op.advance(100,bus,grant)==0 && op.snapshot()==final,"Finished render changed state");
            ++replays;writes+=m.writes.size();errors+=s.error;
        }
    }
    require(r.at==r.bytes.size(),"Render corpus tail differs");
    std::cout<<"frame_render_original=ok cases="<<count<<" replays="<<replays<<" writes="<<writes<<" runtime_errors="<<errors<<" full_frame_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r;r.cs=0x1000;r.ds=0x1aa2;r.ss=0x8000;r.sp=0x3fe4;r.ip=0x7a13;
    unsigned rejected=0;
    for(unsigned field=0;field<3;++field) {auto bad=r;if(field==0)bad.cs=0;else if(field==1)bad.ds=0;else bad.ip=0;try{FrameRenderOperation op(bad,0x1000);}catch(const std::invalid_argument&){++rejected;}}
    Memory m;const auto bus=m.bus();FrameRenderOperation op(r,0x1000);const auto grant=[](uint16_t)->uint16_t{throw std::runtime_error("Inactive view asked for copy grant");};
    require(op.advance(3,bus,grant)==3 && !op.finished() && op.snapshot().registers.ip==0x7a3a,"Inactive view partial dispatch differs");
    require(op.advance(10,bus,grant)==1 && op.returned() && m.writes.empty(),"Inactive view changed memory");
    require(op.snapshot().registers.sp==r.sp && op.snapshot().registers.flags==0x246 && rejected==3,"Inactive view registers differ");
    std::cout<<"frame_render_unit=ok entry_rejections=3\n";
}
}
int main(int argc,char** argv) {try{if(argc==1)unit();else if(argc==3 || argc==4)replay(argv[1],argv[2],argc==4?argv[3]:"");else throw std::runtime_error("Expected corpus, assets and optional RAM dump directory");return 0;}catch(const std::exception& e){std::cerr<<"frame_render=failed "<<e.what()<<'\n';return 1;}}
