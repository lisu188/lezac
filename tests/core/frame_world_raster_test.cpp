#include "core/frame_world_raster.hpp"

#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool condition,const char* message) {if(!condition) throw std::runtime_error(message);}
std::vector<uint8_t> readFile(const std::filesystem::path& path) {
    std::ifstream file(path,std::ios::binary);require(file.good(),"Cannot read raster input");
    return {std::istreambuf_iterator<char>(file),std::istreambuf_iterator<char>()};
}
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    uint32_t number(unsigned count) {
        require(at+count<=bytes.size(),"Truncated raster corpus");uint32_t value=0;
        for(unsigned i=0;i<count;++i) value|=uint32_t{bytes[at++]}<<(i*8);
        return value;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;
        for(auto* value : {&r.ax,&r.bx,&r.cx,&r.dx,&r.si,&r.di,&r.bp,&r.cs,&r.ds,&r.es,&r.ss,&r.sp,&r.ip}) *value=static_cast<uint16_t>(number(2));
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
};
struct Sprite {uint16_t width,height,source;};
struct Assets {
    std::vector<uint8_t> tiles,pixels;std::vector<Sprite> sprites;
    explicit Assets(const std::filesystem::path& root) {
        auto raw=readFile(root/"CARO.CAR");require(raw.size()==8450 && raw[0]==0 && raw[1]==132,"Tile asset differs");
        tiles.assign(raw.begin()+2,raw.end());
        raw=readFile(root/"BOMOMIMK.SPR");require(!raw.empty(),"Sprite asset empty");size_t at=1;
        for(unsigned i=0;i<raw[0];++i) {
            require(at+2<=raw.size(),"Sprite header truncated");const uint16_t w=raw[at++],h=raw[at++];
            const auto count=size_t{w}*h;require(w && h && at+count<=raw.size() && pixels.size()<65536,"Sprite payload differs");
            sprites.push_back({w,h,static_cast<uint16_t>(pixels.size())});
            pixels.insert(pixels.end(),raw.begin()+static_cast<std::ptrdiff_t>(at),raw.begin()+static_cast<std::ptrdiff_t>(at+count));at+=count;
        }
        require(at==raw.size(),"Sprite asset tail differs");
    }
};
constexpr uint32_t Data=0x1aa20,Map=0x30000,Buffer=0x40010,Backdrop=0x50020,Sprites=0x60030,Stack=0x83fa4;
constexpr std::array<uint16_t,6> Scratch={0xc1e8,0xc200,0xc202,0xc210,0xc21a,0xc21c};
struct Case {
    std::array<uint16_t,12> p{};DosGetTimeRegisters initial,final;uint32_t transfers=0;
    std::array<uint16_t,6> scratch{};std::array<uint8_t,72> stack{};
    std::vector<uint8_t> buffer;std::vector<Write> writes;
};
Memory initialMemory(const Case& sample,const Assets& assets) {
    Memory m;const auto& p=sample.p;const uint32_t pitch=p[1],index=p[0];
    for(uint32_t i=0;i<65538;++i) {
        m.bytes[Data+i]=static_cast<uint8_t>(i*13+(i>>5)*7+(i>>16)*61+index);
        m.bytes[Map+i]=static_cast<uint8_t>((i*17+(i>>6)*3+index)%(p[11]?256:132));
        m.bytes[Buffer+i]=static_cast<uint8_t>(i*37+(i>>8)*11+(i>>16)*109+(index+1)*13);
        m.bytes[Backdrop+i]=static_cast<uint8_t>(6+(i%pitch/16+i/pitch/8+index)%40);
        m.bytes[Sprites+i]=static_cast<uint8_t>(i%7==0?0:(i*13+index)&255);
    }
    std::copy(assets.tiles.begin(),assets.tiles.end(),m.bytes.begin()+Data+0x36);
    for(size_t i=0;i<assets.tiles.size();++i) m.bytes[Data+0x2136+i]=assets.tiles[i]==0?255:0;
    std::copy(assets.pixels.begin(),assets.pixels.end(),m.bytes.begin()+Sprites);
    for(uint32_t i=0;i<72;++i) m.bytes[Stack+i]=static_cast<uint8_t>(i*29+index*7+11);
    struct Word {uint16_t offset,value;};
    for(const auto& [o,v] : std::array<Word,17>{{
        {0xc1ea,static_cast<uint16_t>(pitch/8)},{0xc1ec,p[1]},{0xc1ee,160},{0xc1f0,p[5]},
        {0xc1f6,p[9]},{0xc1f8,p[1]},{0xc1fa,0x6003},{0xc1fe,0x3000},{0xc208,0x36},
        {0xc20a,p[6]},{0xc20c,p[7]},{0xc212,0x4001},{0xc214,p[4]},{0xc216,16},
        {0xc218,8},{0xc498,p[8]},{0xc49a,0x5002}}})
        m.store(0x1aa2,o,v);
    for(auto o : Scratch) m.store(0x1aa2,o,0xa55a);
    m.bytes[Data+0xc49c]=static_cast<uint8_t>(p[2]);m.bytes[Data+0xc496]=static_cast<uint8_t>(p[10]);
    for(uint32_t i=0;i<p[10];++i) {
        const auto& s=assets.sprites[(i*7)%assets.sprites.size()];const int w=s.width,h=s.height,span=p[1];
        const std::array<std::array<int,2>,22> positions={{{20,20},{-w,20},{-w+1,20},{-1,20},{span-1,20},{span,20},
            {span-w,20},{span-w+1,20},{20,-h},{20,-h+1},{20,-1},{20,159},{20,160},{20,160-h},{20,161-h},
            {-1,-1},{span-1,159},{-32768,20},{32767,20},{20,-32768},{20,32767},{span-w,160-h}}};
        const auto& point=positions[i%positions.size()];const auto o=static_cast<uint16_t>(0xc21e + i*8);
        m.store(0x1aa2,o,static_cast<uint16_t>(point[0]+16));m.store(0x1aa2,static_cast<uint16_t>(o+2),static_cast<uint16_t>(point[1]+8));
        m.bytes[Data+o+4]=static_cast<uint8_t>(w);m.bytes[Data+o+5]=static_cast<uint8_t>(h);m.store(0x1aa2,static_cast<uint16_t>(o+6),s.source);
    }
    m.store(0x8000,0x3fe4,index%2?0x7a4c:0x7a2a);m.store(0x8000,0x3fe6,0x1000);
    return m;
}
void replay(const char* corpus,const std::filesystem::path& root,const std::filesystem::path& dump={}) {
    Reader r{readFile(corpus)};for(char c : std::string("LZRAST01")) require(r.number(1)==static_cast<uint8_t>(c),"Raster magic differs");
    const auto count=r.number(4);require(count==22,"Raster case count differs");Assets assets(root);uint64_t replays=0,totalWrites=0;
    for(uint32_t index=0;index<count;++index) {
        Case s;for(auto& v:s.p) v=static_cast<uint16_t>(r.number(2));require(s.p[0]==index,"Raster index differs");
        s.initial=r.registers();s.final=r.registers();s.transfers=r.number(4);
        for(auto& v:s.scratch) v=static_cast<uint16_t>(r.number(2));
        for(auto& v:s.stack) v=static_cast<uint8_t>(r.number(1));
        s.buffer.resize(65538);for(auto& v:s.buffer) v=static_cast<uint8_t>(r.number(1));
        const auto writes=r.number(4);require(writes<200000,"Raster write count differs");
        for(uint32_t i=0;i<writes;++i) {const auto a=r.number(4);const auto size=static_cast<uint8_t>(r.number(1));const auto v=static_cast<uint16_t>(r.number(2));s.writes.push_back({a,size,v});}
        struct Budget {uint64_t instructions;uint16_t words;};
        for(const auto& budget : std::array<Budget,3>{{{1,1},{17,3},{4096,65535}}}) {
            auto m=initialMemory(s,assets);const auto bus=m.bus();FrameWorldRasterOperation op(s.initial,0x1000);
            const auto grant=[&](uint16_t n){return std::min(n,budget.words);};const auto initial=op.snapshot();
            require(op.advance(0,bus,grant)==0 && op.snapshot()==initial && m.writes.empty(),"Zero raster budget mutated state");
            uint64_t steps=0;
            while(!op.returned()) {const auto used=op.advance(budget.instructions,bus,grant);require(used && used<=budget.instructions,"Raster budget differs");steps+=used;require(steps<2000000,"Raster did not return");op=FrameWorldRasterOperation(op.snapshot());}
            require(op.snapshot().registers==s.final,"Raster endpoint registers/flags differ");
            require(op.snapshot().transferredWords==s.transfers,"Raster REP transfer count differs");
            require(m.writes==s.writes,"Raster original write sequence differs");
            for(size_t i=0;i<Scratch.size();++i) require(m.word(0x1aa2,Scratch[i])==s.scratch[i],"Raster scratch differs");
            require(std::equal(s.stack.begin(),s.stack.end(),m.bytes.begin()+Stack),"Raster stack differs");
            require(std::equal(s.buffer.begin(),s.buffer.end(),m.bytes.begin()+Buffer),"Raster output buffer differs");
            if(!dump.empty() && index==2 && budget.instructions==4096) {
                std::filesystem::create_directories(dump);
                std::ofstream original(dump/"original.idx",std::ios::binary),cpp(dump/"cpp.idx",std::ios::binary);
                original.write(reinterpret_cast<const char*>(s.buffer.data()),static_cast<std::streamsize>(s.buffer.size()));
                cpp.write(reinterpret_cast<const char*>(m.bytes.data()+Buffer),static_cast<std::streamsize>(s.buffer.size()));
                require(original.good() && cpp.good(),"Raster dump failed");
            }
            const auto final=op.snapshot();require(op.advance(100,bus,grant)==0 && op.snapshot()==final,"Finished raster changed state");
            totalWrites+=m.writes.size();++replays;
        }
    }
    require(r.at==r.bytes.size(),"Raster corpus tail differs");
    std::cout << "frame_world_raster_original=ok cases="<<count<<" replays="<<replays<<" writes="<<totalWrites<<" full_frame_claim=0\n";
}
void unit() {
    DosGetTimeRegisters r;r.cs=0x18ac;r.ds=0x1aa2;r.ss=0x8000;r.sp=0x3fe4;r.ip=0xf4;
    unsigned rejected=0;
    for(unsigned field=0;field<3;++field) {auto bad=r;if(field==0)bad.cs=0;else if(field==1)bad.ds=0;else bad.ip=0;try{FrameWorldRasterOperation op(bad,0x1000);}catch(const std::invalid_argument&){++rejected;}}
    FrameWorldRasterOperation op(r,0x1000);auto state=op.snapshot();state.registers.ip=0x153;state.registers.cx=4;Memory m;const auto bus=m.bus();
    for(uint16_t invalid : {uint16_t{0},uint16_t{5}}) {FrameWorldRasterOperation copy(state);try{copy.advance(1,bus,[invalid](uint16_t){return invalid;});}catch(const std::invalid_argument&){++rejected;}require(copy.snapshot()==state && m.writes.empty(),"Rejected REP changed state");}
    state.registers.cx=0;FrameWorldRasterOperation empty(state);empty.advance(1,bus,[](uint16_t)->uint16_t{throw std::runtime_error("Zero REP asked for grant");});require(empty.snapshot().registers.ip==0x155 && m.writes.empty(),"Empty REP differs");
    require(rejected==5,"Raster rejection count differs");std::cout<<"frame_world_raster_unit=ok rejections=5\n";
}
}
int main(int argc,char** argv) {try{if(argc==1)unit();else if(argc==3 || argc==4)replay(argv[1],argv[2],argc==4?argv[3]:"");else throw std::runtime_error("Expected corpus, asset root and optional dump directory");return 0;}catch(const std::exception& e){std::cerr<<"frame_world_raster=failed "<<e.what()<<'\n';return 1;}}
