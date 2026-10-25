#include "core/transient_update.hpp"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <set>
#include <vector>

using namespace lezac::core;
namespace {
void require(bool yes,const char* message) {if (!yes) throw std::runtime_error(message);}
struct Write {uint32_t address;uint8_t size;uint16_t value;bool operator==(const Write&) const = default;};
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576);std::vector<Write> writes;
    static uint32_t address(uint16_t s,uint16_t o) {return (uint32_t{s}*16+o)&0xfffffu;}
    uint16_t word(uint16_t s,uint16_t o) const {
        const auto a=address(s,o);return static_cast<uint16_t>(bytes[a]|(uint16_t{bytes[(a+1u)&0xfffffu]}<<8));
    }
    void store(uint32_t a,uint16_t v,uint8_t size=2) {
        bytes[a]=static_cast<uint8_t>(v);if (size==2) bytes[(a+1u)&0xfffffu]=static_cast<uint8_t>(v>>8);
    }
    TimerIrqBus bus() {
        return {
            [this](uint16_t s,uint16_t o) {return bytes[address(s,o)];},
            [this](uint16_t s,uint16_t o) {return word(s,o);},
            [this](uint16_t s,uint16_t o) {return uint32_t{word(s,o)}|(uint32_t{word(s,static_cast<uint16_t>(o+2u))}<<16);},
            [this](uint16_t s,uint16_t o,uint8_t v) {const auto a=address(s,o);store(a,v,1);writes.push_back({a,1,v});},
            [this](uint16_t s,uint16_t o,uint16_t v) {const auto a=address(s,o);store(a,v);writes.push_back({a,2,v});},
            [this](uint16_t s,uint16_t o,uint32_t v) {
                const auto a=address(s,o);store(a,static_cast<uint16_t>(v));store((a+2u)&0xfffffu,static_cast<uint16_t>(v>>16));
                writes.push_back({a,2,static_cast<uint16_t>(v)});writes.push_back({(a+2u)&0xfffffu,2,static_cast<uint16_t>(v>>16)});
            },
            [](uint16_t p)->uint8_t {require(p==0x61,"Unexpected updater IRQ input");return 0;},
            [](uint16_t p,uint8_t) {require(p==0x20 || p==0x61 || p==0x42 || p==0x43,"Unexpected updater IRQ output");}
        };
    }
};
std::vector<uint8_t> read(const std::filesystem::path& path) {
    std::ifstream input(path,std::ios::binary);require(input.good(),"Missing updater input");
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
struct Reader {
    std::vector<uint8_t> bytes;size_t at=0;
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Truncated updater fixture");
        uint32_t v=0;for (unsigned i=0;i<n;++i) v|=uint32_t{bytes[at++]}<<(i*8);return v;
    }
    DosGetTimeRegisters registers() {
        DosGetTimeRegisters r;
        for (auto* v : {&r.ax,&r.bx,&r.cx,&r.dx,&r.si,&r.di,&r.bp,&r.cs,&r.ds,&r.es,&r.ss,&r.sp,&r.ip})
            *v=static_cast<uint16_t>(number(2));
        r.flags=number(4);return r;
    }
    std::vector<DosGetTimeRegisters> trace(uint32_t n) {
        std::vector<DosGetTimeRegisters> rows(n);
        for (auto member : {&DosGetTimeRegisters::ax,&DosGetTimeRegisters::bx,&DosGetTimeRegisters::cx,
                &DosGetTimeRegisters::dx,&DosGetTimeRegisters::si,&DosGetTimeRegisters::di,&DosGetTimeRegisters::bp,
                &DosGetTimeRegisters::cs,&DosGetTimeRegisters::ds,&DosGetTimeRegisters::es,&DosGetTimeRegisters::ss,
                &DosGetTimeRegisters::sp,&DosGetTimeRegisters::ip})
            for (auto& r : rows) r.*member=static_cast<uint16_t>(number(2));
        for (auto& r : rows) r.flags=number(4);
        return rows;
    }
};
Memory image(const std::vector<uint8_t>& raw) {
    Reader exe{raw};require(exe.number(2)==0x5a4d,"Updater MZ differs");
    exe.at=6;const auto relocations=exe.number(2),header=exe.number(2)*16;exe.at=24;const auto table=exe.number(2);
    require(header<raw.size() && table+relocations*4<=header && raw.size()-header+0x10000<=1048576,"Updater MZ layout differs");
    Memory result;std::copy(raw.begin()+header,raw.end(),result.bytes.begin()+0x10000);exe.at=table;
    for (unsigned i=0;i<relocations;++i) {
        const auto value=exe.number(4),at=0x10000+(value>>16)*16+(value&65535);
        require(at+1<result.bytes.size(),"Updater relocation exceeds memory");
        result.store(at,static_cast<uint16_t>(result.bytes[at]+(uint16_t{result.bytes[at+1]}<<8)+0x1000));
    }
    return result;
}
void compare(DosGetTimeRegisters actual,DosGetTimeRegisters expected,unsigned index,size_t row,uint32_t undefined=0x8d5) {
    const bool flags=((actual.flags^expected.flags)&~undefined)==0;
    const auto actualFlags=actual.flags;actual.flags=expected.flags;
    if (!flags || actual!=expected) {
        std::cerr << "case=" << index << " row=" << row << " actual=" << std::hex << actual.cs << ':' << actual.ip
            << " expected=" << expected.cs << ':' << expected.ip << " ax=" << actual.ax << '/' << expected.ax
            << " bx=" << actual.bx << '/' << expected.bx << " cx=" << actual.cx << '/' << expected.cx
            << " dx=" << actual.dx << '/' << expected.dx << " si=" << actual.si << '/' << expected.si
            << " di=" << actual.di << '/' << expected.di << " sp=" << actual.sp << '/' << expected.sp
            << " bp=" << actual.bp << '/' << expected.bp << " flags=" << actualFlags << '/' << expected.flags << std::dec << '\n';
        throw std::runtime_error("Updater register/control trace differs");
    }
}
uint64_t rejected=0,irqCases=0;
std::set<uint32_t> irqBoundaries;
void rejectionControls(const TransientUpdateSnapshot& good) {
    const auto reject=[](const TransientUpdateSnapshot& state) {
        bool failed=false;try {(void)TransientUpdateOperation(state);} catch (const std::invalid_argument&) {failed=true;}
        require(failed,"Malformed updater continuation accepted");++rejected;
    };
    for (unsigned field=0;field<16;++field) {
        auto bad=good;
        switch (field) {
        case 0:++bad.callerSs;break;
        case 1:++bad.callerSp;break;
        case 2:++bad.callerBp;break;
        case 3:++bad.dispatchedInstructions;break;
        case 4:++bad.timerInstructions;break;
        case 5:++bad.timerDeliveries;break;
        case 6:++bad.transferredBytes;break;
        case 7:++bad.foreground.registers.ss;break;
        case 8:bad.foreground.registers.cs=0;break;
        case 9:bad.outcome=static_cast<TransientUpdateOutcome>(99);break;
        case 10:bad.frames.clear();break;
        case 11:++bad.frames.back().entry;break;
        case 12:++bad.frames.back().sp;break;
        case 13:++bad.frames.back().bp;break;
        case 14:++bad.helperCalls[0];break;
        case 15:++bad.completedInstructions;break;
        }
        reject(bad);
    }
    const auto& frame=good.frames.back();const auto& r=good.foreground.registers;
    const auto p=std::find_if(kTransientStackProfiles.begin(),kTransientStackProfiles.end(),[&](const auto& profile) {
        return profile.segment==frame.segment && profile.entry==frame.entry && profile.ip==r.ip;
    });
    if (good.helper || p!=kTransientStackProfiles.end()) {
        auto bad=good;++bad.foreground.registers.sp;reject(bad);
        if (good.helper || p->bpKind!=2) {bad=good;++bad.foreground.registers.bp;reject(bad);}
    }
}
void irqControl(const TransientUpdateOperation& source,const Memory& original) {
    const auto pc=source.registers();
    if (pc.cs!=0x1000 && pc.cs!=0x1920) return;
    if (pc.ip!=0x45fa && pc.ip!=0x4605 && pc.ip!=0x3eda && pc.ip!=0x452a && pc.ip!=0x458d &&
        pc.ip!=0x3bb2 && pc.ip!=0x3d46 && pc.ip!=0x945 && pc.ip!=0x4df && pc.ip!=0x3fa6 && pc.ip!=0x414a) return;
    const auto key=uint32_t{pc.cs}*65536+pc.ip;if (!irqBoundaries.insert(key).second) return;
    auto op=source;auto memory=original;memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);
    memory.store(0x46c,100);memory.bytes[0x440]=2;const auto bus=memory.bus();
    op.deliverTimerInterrupt(bus);const auto delivered=op.snapshot();const auto written=memory.writes;
    bool nested=false;try {op.deliverTimerInterrupt(bus);} catch (const std::logic_error&) {nested=true;}
    require(nested && op.snapshot()==delivered && memory.writes==written,"Nested updater IRQ changed state");
    unsigned steps=0;
    while (op.interruptInProgress()) {
        require(steps++<4096,"Updater IRQ stalled");op.advance(1,bus,[](uint16_t n) {return n;});
        op=TransientUpdateOperation(op.snapshot());
    }
    require(op.registers()==pc && memory.word(0x40,0x6c)==101,"Updater IRQ did not restore CPU/clock");
    auto other=op;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
    while (!op.finished()) {require(steps++<1000000,"Updater post-IRQ stalled");op.advance(1,bus,[](uint16_t) {return uint16_t{1};});}
    while (!other.finished()) {
        require(steps++<2000000,"Updater alternate IRQ continuation stalled");
        other.advance(17,otherBus,[](uint16_t) {return uint16_t{1};});other=TransientUpdateOperation(other.snapshot());
    }
    require(op.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes && memory.writes==otherMemory.writes,
        "Updater post-IRQ grant/snapshot continuation differs");++irqCases;
}
void replay(const char* path,const char* root) {
    Reader input{read(path)};require(input.bytes.size()<=16*1024*1024,"Updater fixture exceeds reserve");
    for (char c : std::string("LZTRUP01")) require(input.number(1)==static_cast<uint8_t>(c),"Updater magic differs");
    const auto count=input.number(4),mzBytes=input.number(4);const auto mz=read(std::filesystem::path(root)/"LEZAC.EXE");
    require(count==1142 && mzBytes==mz.size() && input.at+mzBytes<=input.bytes.size(),"Updater corpus/MZ size differs");
    require(std::equal(mz.begin(),mz.end(),input.bytes.begin()+static_cast<std::ptrdiff_t>(input.at)),"Updater canonical MZ bytes differ");
    input.at+=mzBytes;const auto base=image(mz);uint64_t comparisons=0,dispatches=0,totalWrites=0,replays=0;
    std::array<unsigned,3> outcomes{};unsigned denseCases=0;
    for (unsigned index=0;index<count;++index) {
        try {
            require(input.number(4)==index,"Updater case index differs");const auto domain=input.number(4),outcome=input.number(4);
            require(domain<2 && outcome<3,"Updater domain/outcome differs");++outcomes[outcome];
            const auto entry=input.registers(),endpoint=input.registers();auto initial=base;const auto seeds=input.number(4);
            require(seeds<64,"Updater seed reserve differs");
            for (unsigned i=0;i<seeds;++i) {
                const auto at=input.number(4),size=input.number(4);
                require(size<=65536 && uint64_t{at}+size<=initial.bytes.size() && input.at+size<=input.bytes.size(),"Updater seed exceeds memory");
                std::copy_n(input.bytes.begin()+static_cast<std::ptrdiff_t>(input.at),size,initial.bytes.begin()+at);input.at+=size;
            }
            const auto states=input.number(4);require(states>=2 && states<=4001,"Updater trace reserve differs");
            const auto trace=input.trace(states);const auto written=input.number(4);require(written<200000,"Updater write reserve differs");
            auto expected=initial;std::vector<Write> writes;
            for (unsigned i=0;i<written;++i) {
                const auto at=input.number(4),size=input.number(1),value=input.number(2);
                require((size==1 || size==2) && uint64_t{at}+size<=expected.bytes.size(),"Updater write exceeds memory");
                expected.store(at,static_cast<uint16_t>(value),static_cast<uint8_t>(size));writes.push_back({at,static_cast<uint8_t>(size),static_cast<uint16_t>(value)});
            }
            const bool dense=trace.size()>2;if (dense) ++denseCases;
            for (uint16_t limit : {uint16_t{1},uint16_t{65535}}) for (uint64_t budget : {1u,17u,4096u}) {
                auto memory=initial;const auto bus=memory.bus();TransientUpdateOperation op(entry,0x1000,0x200000);
                const auto initialState=op.snapshot();require(op.advance(0,bus,[](uint16_t n) {return n;})==0 &&
                    op.snapshot()==initialState && memory.writes.empty(),"Zero updater budget changed state");
                size_t cursor=0;uint64_t steps=0;
                while (!op.finished()) {
                    if (dense && budget==1 && limit==1) {
                        if (steps%17==0) rejectionControls(op.snapshot());
                        irqControl(op,memory);
                    }
                    const auto before=op.registers();const auto used=op.advance(budget,bus,[=](uint16_t n) {return std::min(n,limit);});
                    require(used>0 && used<=budget && (steps+=used)<1000000,"Updater dispatch grant/reserve differs");
                    try {op=TransientUpdateOperation(op.snapshot());}
                    catch (const std::exception&) {std::cerr << "restore_after=" << std::hex << before.cs << ':' << before.ip << std::dec << '\n';throw;}
                    if (dense && budget==1 && limit==1) {
                        ++cursor;
                        if (cursor+1<trace.size() && before.cs==trace[cursor].cs && before.ip==trace[cursor].ip && trace[cursor].cx==0 &&
                            op.registers().ip!=before.ip) ++cursor;
                        require(cursor<trace.size(),"Updater exceeded original trace");compare(op.registers(),trace[cursor],index,cursor);++comparisons;
                    }
                }
                compare(op.registers(),endpoint,index,trace.size()-1,0);++comparisons;
                const auto result=outcome==0 ? TransientUpdateOutcome::Returned : outcome==1 ? TransientUpdateOutcome::RuntimeError : TransientUpdateOutcome::DivideError;
                require(op.snapshot().outcome==result,"Updater outcome differs");
                if (memory.writes!=writes) {
                    const auto n=std::min(memory.writes.size(),writes.size());size_t at=0;
                    while (at<n && memory.writes[at]==writes[at]) ++at;
                    std::cerr << "writes_actual=" << memory.writes.size() << " expected=" << writes.size() << " first_difference=" << at << '\n';
                    if (at<n) std::cerr << std::hex << "write_address=" << memory.writes[at].address << '/' << writes[at].address
                        << " value=" << memory.writes[at].value << '/' << writes[at].value << std::dec << '\n';
                }
                require(memory.writes==writes && memory.bytes==expected.bytes,"Updater ordered writes/complete memory differ");
                const auto done=op.snapshot();require(op.advance(19,bus,[](uint16_t n) {return n;})==0 && op.snapshot()==done,"Finished updater changed state");
                bool stopped=false;try {op.deliverTimerInterrupt(bus);} catch (const std::logic_error&) {stopped=true;}
                require(stopped,"Finished updater admitted IRQ");dispatches+=steps;++replays;
            }
            totalWrites+=writes.size();
        } catch (const std::exception&) {std::cerr << "updater_case=" << index << '\n';throw;}
    }
    require(input.at==input.bytes.size() && outcomes[0]==1138 && outcomes[1]==3 && outcomes[2]==1 && denseCases==18,"Updater coverage/tail differs");
    std::cout << "transient_update_original=ok cases=" << count << " replays=" << replays << " comparisons=" << comparisons
        << " dispatches=" << dispatches << " writes=" << totalWrites << " dense_cases=" << denseCases
        << " state_rejections=" << rejected << " computed_irq_cases=" << irqCases << " all_endpoint_flags=1"
        << " full_memory=1 canonical_mz_bytes=1 later_state_injected=0 actual_app_integration=0 full_frame_claim=0\n";
}
}
int main(int argc,char** argv) {
    try {require(argc==3,"Use updater fixture and repository root");replay(argv[1],argv[2]);}
    catch (const std::exception& error) {std::cerr << "transient_update_error=" << error.what() << '\n';return 1;}
}
