#include "core/frame_camera.hpp"
#include "rendering/world_camera.hpp"

#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

using namespace lezac::core;

namespace {
void require(bool value,const char* message) { if (!value) throw std::runtime_error(message); }
struct Write {
    uint32_t address;
    uint16_t value;
    bool operator==(const Write&) const = default;
};
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576);
    std::vector<Write> writes;
    static uint32_t address(uint16_t segment,uint16_t offset) { return (uint32_t{segment}*16+offset)&0xfffffu; }
    uint16_t read(uint16_t segment,uint16_t offset) const {
        const auto at=address(segment,offset);
        return static_cast<uint16_t>(bytes[at] | (uint16_t{bytes[(at+1u)&0xfffffu]}<<8));
    }
    void store(uint16_t segment,uint16_t offset,uint16_t value,bool record=false) {
        const auto at=address(segment,offset);
        bytes[at]=static_cast<uint8_t>(value); bytes[(at+1u)&0xfffffu]=static_cast<uint8_t>(value>>8);
        if (record) writes.push_back({at,value});
    }
    TimerIrqBus bus() {
        TimerIrqBus result;
        result.readWord=[this](uint16_t s,uint16_t o) { return read(s,o); };
        result.writeWord=[this](uint16_t s,uint16_t o,uint16_t value) { store(s,o,value,true); };
        result.inByte=[](uint16_t)->uint8_t { throw std::runtime_error("Unexpected camera I/O"); };
        result.outByte=[](uint16_t,uint8_t) { throw std::runtime_error("Unexpected camera I/O"); };
        return result;
    }
};
struct Reader {
    std::vector<uint8_t> bytes;
    size_t at=0;
    uint32_t number(unsigned count) {
        require(at+count<=bytes.size(),"Truncated camera fixture");
        uint32_t value=0;
        for (unsigned i=0;i<count;++i) value|=uint32_t{bytes[at++]}<<(i*8);
        return value;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;
        for (auto* value : {&r.ax,&r.bx,&r.cx,&r.dx,&r.si,&r.di,&r.bp,&r.cs,&r.ds,&r.es,&r.ss,&r.sp,&r.ip})
            *value=static_cast<uint16_t>(number(2));
        r.flags=number(4); return r;
    }
};
constexpr std::array<uint16_t,5> Fields={0xc216,0xc218,0xc1f0,0xc20a,0xc20c};
struct Case {
    std::array<uint16_t,11> profile{};
    DosGetTimeRegisters initial,final;
    std::array<uint16_t,5> fields{};
    std::array<uint8_t,72> stack{};
    std::vector<DosGetTimeRegisters> trace;
    std::vector<Write> writes;
};
Memory initialMemory(const Case& sample) {
    Memory memory;
    const auto& p=sample.profile;
    const auto stack=0x70000u+p[8]-64u;
    for (uint32_t i=0;i<72;++i) memory.bytes[stack+i]=static_cast<uint8_t>(i*29+p[0]*7+11);
    memory.store(0x7000,p[8],p[9]);
    memory.store(0x7000,static_cast<uint16_t>(p[8]+2u),p[5]);
    memory.store(0x7000,static_cast<uint16_t>(p[8]+4u),p[4]);
    struct Word { uint16_t offset,value; };
    for (const auto& [offset,value] : std::array<Word,7>{{
        {0xc204,p[1]},{0x78bc,static_cast<uint16_t>(p[3]*4-8)},
        {0x78be,static_cast<uint16_t>((p[3]*4-8)/8)},
        {0x2094,static_cast<uint16_t>((p[1]-p[3])*8)},
        {0x2096,static_cast<uint16_t>(p[2]*8-160)},{0x2098,p[6]},{0x1afa,p[7]}}})
        memory.store(0x1aa2,offset,value);
    for (auto offset : Fields) memory.store(0x1aa2,offset,0xa55a);
    return memory;
}
void compareTrace(DosGetTimeRegisters actual,DosGetTimeRegisters expected) {
    require(((actual.flags^expected.flags)&~uint32_t{0x8d5})==0,"Camera trace control flags differ");
    actual.flags=expected.flags;
    require(actual==expected,"Camera instruction register trace differs");
}
void replay(const char* path) {
    std::ifstream file(path,std::ios::binary); require(file.good(),"Cannot read camera fixture");
    Reader reader{{std::istreambuf_iterator<char>(file),std::istreambuf_iterator<char>()}};
    for (char c : std::string("LZCAM001")) require(reader.number(1)==static_cast<uint8_t>(c),"Camera fixture magic differs");
    const auto count=reader.number(4); require(count==1876,"Camera case count differs");
    uint64_t comparisons=0;
    uint32_t errors=0;
    uint32_t liveComparisons=0;
    for (uint32_t index=0;index<count;++index) {
        Case sample;
        for (auto& value : sample.profile) value=static_cast<uint16_t>(reader.number(2));
        require(sample.profile[0]==index,"Camera index differs");
        sample.initial=reader.registers(); sample.final=reader.registers();
        for (auto& value : sample.fields) value=static_cast<uint16_t>(reader.number(2));
        for (auto& value : sample.stack) value=static_cast<uint8_t>(reader.number(1));
        const auto states=reader.number(4); require(states>1 && states<1000,"Camera trace length differs");
        for (uint32_t i=0;i<states;++i) sample.trace.push_back(reader.registers());
        const auto writes=reader.number(4); require(writes<100,"Camera write count differs");
        for (uint32_t i=0;i<writes;++i) {
            const auto address=reader.number(4); const auto value=static_cast<uint16_t>(reader.number(2));
            sample.writes.push_back({address,value});
        }
        errors+=sample.profile[10];
        if (!sample.profile[10]) {
            const auto& p=sample.profile;
            const auto camera=lezac::rendering::calculateWorldCamera({p[4],p[5],p[1],
                static_cast<uint16_t>(p[3]*4-8),static_cast<uint16_t>((p[3]*4-8)/8),
                static_cast<uint16_t>((p[1]-p[3])*8),static_cast<uint16_t>(p[2]*8-160),p[6]});
            const std::array<uint16_t,5> fields={camera.coarseX,camera.coarseY,
                camera.mapOffset,camera.fineX,camera.fineY};
            require(fields==sample.fields,"Live world camera differs from original context");
            ++liveComparisons;
        }
        for (uint64_t budget : {1u,2u,17u,4096u}) {
            auto memory=initialMemory(sample); const auto bus=memory.bus();
            FrameCameraOperation operation(sample.initial,0x1000);
            const auto initial=operation.snapshot();
            require(operation.advance(0,bus)==0 && operation.snapshot()==initial && memory.writes.empty(),"Camera zero budget mutated state");
            size_t cursor=0;
            compareTrace(operation.snapshot().registers,sample.trace[0]); ++comparisons;
            while (!operation.finished()) {
                const auto used=operation.advance(budget,bus);
                require(used>0 && used<=budget,"Camera instruction budget differs");
                cursor+=static_cast<size_t>(used);
                require(cursor<sample.trace.size(),"Camera ran beyond original endpoint");
                compareTrace(operation.snapshot().registers,sample.trace[cursor]); ++comparisons;
                operation=FrameCameraOperation(operation.snapshot());
            }
            const auto final=operation.snapshot();
            require(cursor+1==sample.trace.size() && final.dispatchedInstructions==cursor,"Camera instruction count differs");
            require(final.registers==sample.final,"Camera complete endpoint flags/registers differ");
            require(final.outcome==(sample.profile[10] ? FrameCameraOutcome::RuntimeError : FrameCameraOutcome::Returned),"Camera outcome differs");
            require(memory.writes==sample.writes,"Camera original write sequence differs");
            for (size_t i=0;i<Fields.size();++i) require(memory.read(0x1aa2,Fields[i])==sample.fields[i],"Camera context differs");
            require(std::equal(sample.stack.begin(),sample.stack.end(),memory.bytes.begin()+0x70000+sample.profile[8]-64),"Camera stack bytes differ");
            require(operation.advance(100,bus)==0 && operation.snapshot()==final,"Finished camera changed state");
        }
    }
    require(reader.at==reader.bytes.size() && errors==3,"Camera corpus tail/outcomes differ");
    require(liveComparisons==1873,"Live world camera coverage differs");
    std::cout << "world_camera_original=ok cases=" << liveComparisons << " context_words="
        << liveComparisons*5 << " copied_world_bytes=0\n";
    std::cout << "frame_camera_original=ok cases=" << count << " replays=" << count*4 << " comparisons=" << comparisons
        << " runtime_errors=" << errors << " full_frame_claim=0\n";
}
void unit() {
    using lezac::rendering::cameraForViewport;
    const auto atEdge=cameraForViewport(319,183,60,33,320,0);
    require(atEdge.pixelX()==167 && atEdge.pixelY()==103 && atEdge.fineX==7 && atEdge.fineY==7,
        "Live world camera edge differs");
    const auto negative=cameraForViewport(-1,-1,60,33,320,0);
    require(negative.pixelX()==0 && negative.pixelY()==0,"Live world camera negative clamp differs");
    const auto wrapped=cameraForViewport(159,80,60,33,320,65534);
    require(wrapped.fineX==5 && wrapped.pixelX()==5,"Live world camera shake did not wrap at 16 bits");
    const auto signedCoordinates=cameraForViewport(65535,65535,60,33,320,0);
    require(signedCoordinates==negative,"Live world camera did not interpret visual words as signed");
    const auto narrow=cameraForViewport(104,168,60,33,168,0);
    require(narrow.pixelX()==32 && narrow.pixelY()==88,
        "Live world camera rounded an odd-column viewport center incorrectly");
    unsigned badGeometry=0;
    for (int pitch : {0,152,161,328}) {
        try { (void)cameraForViewport(0,0,60,33,pitch,0); }
        catch (const std::invalid_argument&) { ++badGeometry; }
    }
    for (int dimension : {0,-1,32768}) {
        try { (void)cameraForViewport(0,0,dimension,33,320,0); }
        catch (const std::invalid_argument&) { ++badGeometry; }
        try { (void)cameraForViewport(0,0,60,dimension,320,0); }
        catch (const std::invalid_argument&) { ++badGeometry; }
    }
    require(badGeometry==10,"Live world camera geometry validation differs");
    std::cout << "world_camera_unit=ok geometry_rejections=10\n";
    DosGetTimeRegisters r; r.cs=0x1000;r.ds=0x1aa2;r.ss=0x7000;r.sp=0x3fe4;r.ip=0x3587;
    uint32_t rejected=0;
    for (unsigned field=0;field<3;++field) {
        auto bad=r;
        if (field==0) bad.cs=0; else if (field==1) bad.ds=0; else bad.ip=0;
        try { FrameCameraOperation operation(bad,0x1000); }
        catch (const std::invalid_argument&) { ++rejected; }
    }
    require(rejected==3,"Camera accepted invalid entry");
    Memory memory; const auto bus=memory.bus();
    FrameCameraOperation operation(r,0x1000); const auto before=operation.snapshot();
    require(operation.advance(0,bus)==0 && before==operation.snapshot(),"Camera zero budget differs");
    std::cout << "frame_camera_unit=ok entry_rejections=3\n";
}
}

int main(int argc,char** argv) {
    try {
        if (argc==1) unit(); else if (argc==2) replay(argv[1]); else throw std::runtime_error("Expected optional camera corpus");
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "frame_camera=failed " << error.what() << '\n'; return 1;
    }
}
