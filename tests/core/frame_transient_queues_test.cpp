#include "core/frame_transient_queues.hpp"

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
using FrameQueuesProbe=FrameTransientQueuesOperation;
using Snapshot=FrameTransientQueuesSnapshot;
uint64_t rejected=0,irqCases=0;unsigned copyControls=0;
std::set<uint32_t> irqBoundaries;std::set<uint16_t> copied;
constexpr std::array<uint16_t,9> callerPcs{{0x804e,0x8053,0x8055,0x805b,0x805d,0x8060,0x8065,0x8067,0x806a}};
bool caller(const DosGetTimeRegisters& r) {return r.cs==0x1000 && std::binary_search(callerPcs.begin(),callerPcs.end(),r.ip);}
void compare(DosGetTimeRegisters actual,DosGetTimeRegisters expected,unsigned index,size_t row,uint32_t undefined=0x8d5) {
    const bool flags=((actual.flags^expected.flags)&~undefined)==0;const auto actualFlags=actual.flags;actual.flags=expected.flags;
    if (!flags || actual!=expected) {
        std::cerr << "case=" << index << " row=" << row << " actual=" << std::hex << actual.cs << ':' << actual.ip
            << " expected=" << expected.cs << ':' << expected.ip << " ax=" << actual.ax << '/' << expected.ax
            << " sp=" << actual.sp << '/' << expected.sp << " bp=" << actual.bp << '/' << expected.bp
            << " flags=" << actualFlags << '/' << expected.flags << std::dec << '\n';
        throw std::runtime_error("Frame queue register/control trace differs");
    }
}
void rejectionControls(const Snapshot& good) {
    for (unsigned field=0;field<23;++field) {
        auto bad=good;
        switch (field) {
        case 0:++bad.callerSs;break;case 1:++bad.callerSp;break;case 2:++bad.callerBp;break;
        case 3:++bad.dispatchedInstructions;break;case 4:++bad.timerInstructions;break;
        case 5:++bad.timerDeliveries;break;case 6:++bad.transferredBytes;break;
        case 7:++bad.caller.registers.ss;break;case 8:bad.caller.registers.cs=0;break;
        case 9:bad.outcome=static_cast<FrameTransientQueuesOutcome>(99);break;
        case 10:++bad.caller.registers.sp;break;case 11:++bad.caller.registers.bp;break;
        case 12:bad.caller.registers.ip=0;break;case 13:++bad.completed[0];break;
        case 14:++bad.calls[0];break;case 15:++bad.returns[0];break;
        case 16:bad.caller.outcome=ActorFinishOutcome::Returned;break;case 17:++bad.caller.transferredBytes;break;
        case 18:if (bad.child) ++bad.child->callerSp;else ++bad.returns[0];break;
        case 19:if (bad.child) bad.child->entry=bad.child->entry==TransientUpdateEntry::Collapse ?
            TransientUpdateEntry::SparksAndDebris : TransientUpdateEntry::Collapse;else ++bad.caller.timerDeliveries;break;
        case 20:++bad.completed[2];break;case 21:++bad.calls[1];break;
        case 22:++bad.caller.dispatchedInstructions;++bad.dispatchedInstructions;break;
        }
        bool failed=false;try {(void)FrameQueuesProbe(bad);} catch (const std::invalid_argument&) {failed=true;}
        if (!failed) std::cerr << "accepted_field=" << field << " caller_pc=" << std::hex << good.caller.registers.ip << std::dec << '\n';
        require(failed,"Malformed frame queue state accepted");++rejected;
    }
}
void irqControl(const FrameQueuesProbe& source,const Memory& original,bool partial=false,bool continueChild=true) {
    const auto pc=source.registers();
    const bool selected=caller(pc) || ((pc.cs==0x1000 || pc.cs==0x1920) &&
        (pc.ip==0x45fa || pc.ip==0x5102 || pc.ip==0x3bb2 || pc.ip==0x3d46 || pc.ip==0x4df || pc.ip==0x945 ||
         pc.ip==0x452a || pc.ip==0x458d || pc.ip==0x508b || pc.ip==0x456b || pc.ip==0x45ce || pc.ip==0x50be));
    if (!selected) return;
    const auto key=(uint32_t{pc.cs}*65536+pc.ip)^(partial ? 0x40000000u : 0u);
    if (!irqBoundaries.insert(key).second) return;
    auto op=source;auto memory=original;memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);
    memory.store(0x46c,100);memory.bytes[0x440]=2;const auto bus=memory.bus();
    op.deliverTimerInterrupt(bus);const auto delivered=op.snapshot();const auto writes=memory.writes;
    bool nested=false;try {op.deliverTimerInterrupt(bus);} catch (const std::logic_error&) {nested=true;}
    require(nested && op.snapshot()==delivered && memory.writes==writes,"Nested frame queue IRQ changed state");
    unsigned steps=0;
    while (op.interruptInProgress()) {
        require(steps++<4096,"Frame queue IRQ stalled");op.advance(1,bus,[](uint16_t n) {return n;});op=FrameQueuesProbe(op.snapshot());
    }
    require(op.registers()==pc && memory.word(0x40,0x6c)==101,"Frame queue IRQ did not restore CPU/clock");
    if (continueChild) {
        auto other=op;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
        while (!op.finished()) {require(steps++<1000000,"Frame queue post-IRQ stalled");op.advance(1,bus,[](uint16_t) {return uint16_t{1};});}
        while (!other.finished()) {require(steps++<2000000,"Frame queue alternate stalled");other.advance(17,otherBus,[](uint16_t) {return uint16_t{1};});other=FrameQueuesProbe(other.snapshot());}
        require(op.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes && memory.writes==otherMemory.writes,
            "Frame queue post-IRQ grant/snapshot differs");
    }
    ++irqCases;
}
void copyControl(const FrameQueuesProbe& source,const Memory& original) {
    const auto before=source.registers();
    if (before.cs!=0x1000 || (before.ip!=0x456b && before.ip!=0x45ce && before.ip!=0x50be) ||
        before.cx<=1 || before.cx==65535 || copied.contains(before.ip)) return;
    copied.insert(before.ip);auto op=source;auto memory=original;const auto bus=memory.bus();
    require(op.advance(1,bus,[](uint16_t) {return uint16_t{0};})==1 && op.registers()==before &&
        memory.bytes==original.bytes && memory.writes==original.writes,"Zero frame queue copy changed state");
    op=FrameQueuesProbe(op.snapshot());const auto state=op.snapshot();bool failed=false;
    try {op.advance(1,bus,[](uint16_t n) {return static_cast<uint16_t>(n+1u);});} catch (const std::domain_error&) {failed=true;}
    require(failed && op.snapshot()==state && memory.bytes==original.bytes && memory.writes==original.writes,"Oversized frame queue copy changed state");
    op=source;op.advance(1,bus,[](uint16_t) {return uint16_t{1};});op=FrameQueuesProbe(op.snapshot());
    require(op.registers().ip==before.ip && op.registers().cx==before.cx-1 && memory.writes.size()==original.writes.size()+1,
        "Partial frame queue copy left REP boundary");irqControl(op,memory,true);copyControls+=3;
}
void unit() {
    std::set<uint16_t> boundaries;unsigned entries=0;
    for (auto route : {std::array<uint16_t,3>{0,199,0},{1,199,0},{0,200,0},{0,199,1}}) {
        Memory memory;memory.store(0x1aa20+0x2076,route[0]);memory.store(0x1aa20+0x207e,route[1]);memory.store(0x1aa20+0x2080,route[2]);
        DosGetTimeRegisters r;r.cs=0x1000;r.ds=0x1aa2;r.ss=0x8000;r.sp=0xff00;r.bp=0x3fee;r.ip=0x804e;r.flags=0x202;
        FrameQueuesProbe op(r,0x1000,0x200000);const auto bus=memory.bus();unsigned steps=0;
        while (!op.finished() && !op.snapshot().child) {
            const auto good=op.snapshot();boundaries.insert(op.registers().ip);rejectionControls(good);irqControl(op,memory,false,false);
            require(op.advance(0,bus,[](uint16_t n) {return n;})==0 && op.snapshot()==good,"Zero frame queue grant changed state");
            op.advance(1,bus,[](uint16_t n) {return n;});op=FrameQueuesProbe(op.snapshot());require(++steps<9,"Queue unit caller stalled");
        }
        rejectionControls(op.snapshot());
        if (op.snapshot().child) {
            ++entries;require(op.registers().sp==0xfefe && memory.word(0x8000,0xfefe)==(route[2] ? 0x806a : 0x8060),"Queue actual CALL differs");
            irqControl(op,memory,false,false);
        } else {
            require(op.registers().ip==0x806a && op.registers().sp==r.sp && op.registers().bp==r.bp && memory.writes.empty(),"Empty queues changed stack/memory");
            const auto done=op.snapshot();require(op.advance(19,bus,[](uint16_t n) {return n;})==0 && op.snapshot()==done,"Finished queue changed state");
        }
    }
    require(boundaries.size()==8 && entries==3,"Frame queue unit caller coverage differs");
    std::cout << "frame_transient_queues_unit=ok state_rejections=" << rejected << " caller_boundaries=" << boundaries.size()
        << " real_call_entries=" << entries << " computed_irq_cases=" << irqCases << '\n';
}
void replay(const char* path,const char* root) {
    Reader input{read(path)};require(input.bytes.size()<=32*1024*1024,"Frame queue fixture exceeds reserve");
    for (char c : std::string("LZTRQP01")) require(input.number(1)==static_cast<uint8_t>(c),"Frame queue magic differs");
    const auto count=input.number(4),mzBytes=input.number(4);const auto mz=read(std::filesystem::path(root)/"LEZAC.EXE");
    require(count==3973 && mzBytes==mz.size() && input.at+mzBytes<=input.bytes.size(),"Frame queue corpus/MZ size differs");
    require(std::equal(mz.begin(),mz.end(),input.bytes.begin()+static_cast<std::ptrdiff_t>(input.at)),"Frame queue canonical MZ bytes differ");
    input.at+=mzBytes;const auto base=image(mz);uint64_t comparisons=0,dispatches=0,totalWrites=0,replays=0,callerFlags=0;
    std::array<unsigned,4> outcomes{},patterns{};unsigned denseCases=0;
    for (unsigned index=0;index<count;++index) {
        try {
            require(input.number(4)==index,"Frame queue case index differs");const auto pattern=input.number(4),outcome=input.number(4);
            require(pattern<4 && outcome<4,"Frame queue pattern/outcome differs");++patterns[pattern];++outcomes[outcome];
            const auto entry=input.registers(),endpoint=input.registers();auto initial=base;const auto seeds=input.number(4);require(seeds<64,"Queue seed reserve differs");
            for (unsigned i=0;i<seeds;++i) {
                const auto at=input.number(4),size=input.number(4);require(size<=65536 && uint64_t{at}+size<=initial.bytes.size() && input.at+size<=input.bytes.size(),"Queue seed exceeds memory");
                std::copy_n(input.bytes.begin()+static_cast<std::ptrdiff_t>(input.at),size,initial.bytes.begin()+at);input.at+=size;
            }
            const auto states=input.number(4);require(states>=2 && states<=4001,"Queue trace reserve differs");const auto trace=input.trace(states);
            const auto written=input.number(4);require(written<200000,"Queue writes exceed reserve");auto expected=initial;std::vector<Write> writes;
            for (unsigned i=0;i<written;++i) {
                const auto at=input.number(4),size=input.number(1),value=input.number(2);require((size==1 || size==2) && uint64_t{at}+size<=expected.bytes.size(),"Queue write exceeds memory");
                expected.store(at,static_cast<uint16_t>(value),static_cast<uint8_t>(size));writes.push_back({at,static_cast<uint8_t>(size),static_cast<uint16_t>(value)});
            }
            const bool dense=trace.size()>2;if (dense) ++denseCases;
            for (uint16_t limit : {uint16_t{1},uint16_t{65535}}) for (uint64_t budget : {1u,17u,4096u}) {
                auto memory=initial;const auto bus=memory.bus();FrameQueuesProbe op(entry,0x1000,0x200000);const auto start=op.snapshot();
                require(op.advance(0,bus,[](uint16_t n) {return n;})==0 && op.snapshot()==start && memory.writes.empty(),"Zero queue budget changed state");
                compare(op.registers(),entry,index,0,0);++comparisons;++callerFlags;
                uint64_t steps=0;size_t cursor=0;
                while (!op.finished()) {
                    if (budget==1 && limit==1) copyControl(op,memory);
                    if (dense && budget==1 && limit==1) {if (steps%17==0) rejectionControls(op.snapshot());irqControl(op,memory);}
                    const auto before=op.registers();const auto used=op.advance(budget,bus,[=](uint16_t n) {return std::min(n,limit);});
                    require(used>0 && used<=budget && (steps+=used)<1000000,"Queue dispatch grant/reserve differs");
                    try {op=FrameQueuesProbe(op.snapshot());} catch (const std::exception&) {std::cerr << "restore_after=" << std::hex << before.cs << ':' << before.ip << std::dec << '\n';throw;}
                    if (dense && budget==1 && limit==1) {
                        ++cursor;
                        if (memory.bytes[Memory::address(before.cs,before.ip)]==0xf3 && cursor+1<trace.size() && before.cs==trace[cursor].cs &&
                            before.ip==trace[cursor].ip && trace[cursor].cx==0 && op.registers().ip!=before.ip) ++cursor;
                        require(cursor<trace.size(),"Queue exceeded original trace");const bool exact=caller(op.registers());
                        compare(op.registers(),trace[cursor],index,cursor,exact ? 0u : 0x8d5u);++comparisons;if (exact) ++callerFlags;
                    }
                }
                compare(op.registers(),endpoint,index,trace.size()-1,0);++comparisons;
                constexpr std::array<FrameTransientQueuesOutcome,4> result{{FrameTransientQueuesOutcome::FrameTail,FrameTransientQueuesOutcome::RuntimeError,
                    FrameTransientQueuesOutcome::DivideError,FrameTransientQueuesOutcome::Terminated}};
                require(op.snapshot().outcome==result[outcome] && op.snapshot().calls[0]==uint64_t{(pattern&1u)!=0 ? 1u : 0u} && op.snapshot().calls[1]==uint64_t{(pattern&2u)!=0 ? 1u : 0u},"Queue original call order/outcome differs");
                if (memory.writes!=writes) {
                    const auto n=std::min(memory.writes.size(),writes.size());size_t at=0;while (at<n && memory.writes[at]==writes[at]) ++at;
                    std::cerr << "writes_actual=" << memory.writes.size() << " expected=" << writes.size() << " first_difference=" << at << '\n';
                    if (at<n) std::cerr << std::hex << "write_address=" << memory.writes[at].address << '/' << writes[at].address << " value=" << memory.writes[at].value << '/' << writes[at].value << std::dec << '\n';
                }
                require(memory.writes==writes && memory.bytes==expected.bytes,"Queue ordered writes/complete memory differ");
                const auto done=op.snapshot();require(op.advance(19,bus,[](uint16_t n) {return n;})==0 && op.snapshot()==done,"Finished queue changed state");
                bool stopped=false;try {op.deliverTimerInterrupt(bus);} catch (const std::logic_error&) {stopped=true;}require(stopped,"Finished queue admitted IRQ");
                dispatches+=steps;++replays;
            }
            totalWrites+=writes.size();
        } catch (const std::exception&) {std::cerr << "queue_case=" << index << '\n';throw;}
    }
    require(input.at==input.bytes.size() && patterns==std::array<unsigned,4>{3,989,2390,591} &&
        outcomes==std::array<unsigned,4>{3965,6,2,0} && denseCases==55 && copyControls==9,"Queue coverage/tail differs");
    std::cout << "frame_transient_queues_original=ok cases=" << count << " replays=" << replays << " comparisons=" << comparisons << " caller_flag_checks=" << callerFlags
        << " dispatches=" << dispatches << " writes=" << totalWrites << " dense_cases=" << denseCases << " state_rejections=" << rejected
        << " computed_irq_cases=" << irqCases << " copy_grant_controls=" << copyControls
        << " all_endpoint_flags=1 full_memory=1 canonical_mz_bytes=1 later_state_injected=0 actual_app_integration=0 full_frame_claim=0\n";
}
}
int main(int argc,char** argv) {
    try {if (argc==1) unit();else {require(argc==3,"Use frame queue fixture and repository root");replay(argv[1],argv[2]);}}
    catch (const std::exception& error) {std::cerr << "frame_transient_queues_error=" << error.what() << '\n';return 1;}
}
