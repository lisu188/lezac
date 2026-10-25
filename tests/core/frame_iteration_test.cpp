#include "core/frame_iteration.hpp"

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
struct Port {uint16_t port;uint8_t size,value;bool operator==(const Port&) const = default;};
struct Memory {
    std::vector<uint8_t> bytes=std::vector<uint8_t>(1048576);std::vector<Write> writes;std::vector<Port> ports;
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
            [this](uint16_t p,uint8_t v) {require(p==0x20 || p==0x61 || p==0x42 || p==0x43 || p==0x3c8 || p==0x3c9,"Unexpected iteration output");ports.push_back({p,1,v});}
        };
    }
};
std::vector<uint8_t> read(const std::filesystem::path& path) {
    const auto size=std::filesystem::file_size(path);require(size<=48*1024*1024,"Iteration input reserve differs");
    std::ifstream input(path,std::ios::binary);require(input.good(),"Missing iteration input");
    std::vector<uint8_t> raw(static_cast<size_t>(size));
    input.read(reinterpret_cast<char*>(raw.data()),static_cast<std::streamsize>(size));
    require(input.gcount()==static_cast<std::streamsize>(size) && input.peek()==std::char_traits<char>::eof(),"Iteration input extent changed");
    return raw;
}
uint64_t fingerprint(const std::vector<uint8_t>& raw) {
    uint64_t value=14695981039346656037ull;
    for (const auto byte:raw) value=(value^byte)*1099511628211ull;
    return value;
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
void compare(DosGetTimeRegisters actual,DosGetTimeRegisters expected,unsigned index,size_t row,bool exact) {
    const auto flags=actual.flags;const bool defined=((actual.flags^expected.flags)&~uint32_t{0x8d5})==0;
    if (!exact) actual.flags=expected.flags;
    if (!defined || actual!=expected) {
        std::cerr<<"case="<<index<<" row="<<row<<" actual="<<std::hex<<actual.cs<<':'<<actual.ip<<" expected="<<expected.cs<<':'<<expected.ip
            <<" sp="<<actual.sp<<'/'<<expected.sp<<" bp="<<actual.bp<<'/'<<expected.bp<<" flags="<<flags<<'/'<<expected.flags<<std::dec<<'\n';
        throw std::runtime_error("Iteration register/control trace differs");
    }
}
void replay(const char* path,const char* root) {
    Reader input{read(path)};
    require(input.bytes.size()==20887011 && fingerprint(input.bytes)==0x58af9ccfb5e68f3cull,"Iteration projection fingerprint differs");
    for (char c:std::string("LZITER01")) require(input.number(1)==static_cast<uint8_t>(c),"Iteration magic differs");
    const auto count=input.number(4),size=input.number(4);const auto exe=read(std::filesystem::path(root)/"LEZAC.EXE");
    require(count==1102 && exe.size()==52384 && fingerprint(exe)==0x2ae32f89b95e200bull,"Iteration proof domain differs");
    require(size==exe.size() && input.at+size<=input.bytes.size() &&
        std::equal(exe.begin(),exe.end(),input.bytes.begin()+input.at),"Iteration canonical MZ bytes differ");
    input.at+=size;const auto base=image(exe);
    uint64_t replays=0,comparisons=0,dispatches=0,writeCount=0,portCount=0,callerFlags=0;unsigned denseCases=0;
    std::array<unsigned,11> outcomes{};std::array<unsigned,8> phaseMasks{};
    constexpr std::array<uint16_t,6> exactCaller{{0x8053,0x8055,0x805b,0x805d,0x8065,0x8067}};
    for (unsigned index=0;index<count;++index) {
        require(input.number(4)==index,"Iteration case order differs");const auto outcome=input.number(4),phases=input.number(4);
        require(outcome<outcomes.size() && phases<phaseMasks.size(),"Iteration result reserve differs");
        const auto entry=input.registers(),endpoint=input.registers();auto initial=base;
        const auto patches=input.number(4);
        for (unsigned p=0;p<patches;++p) {
            const auto address=input.number(4),length=input.number(4);
            require(address<=1048576 && length<=1048576-address && input.at+length<=input.bytes.size(),"Iteration patch exceeds memory");
            std::copy_n(input.bytes.begin()+input.at,length,initial.bytes.begin()+address);input.at+=length;
        }
        const auto trace=input.trace(input.number(4));require(trace.size()>1 && trace.size()<=10002 && trace.front()==entry && trace.back()==endpoint,"Iteration trace shape differs");
        const bool dense=trace.size()>2;if (dense) ++denseCases;
        std::vector<Write> writes(input.number(4));auto expected=initial;
        for (auto& event:writes) {
            event={input.number(4),static_cast<uint8_t>(input.number(1)),static_cast<uint16_t>(input.number(2))};
            require((event.size==1 || event.size==2) && event.address+event.size<=1048576,"Iteration write extent differs");
            expected.store(event.address,event.value,event.size);
        }
        std::vector<Port> ports(input.number(4));
        for (auto& event:ports) event={static_cast<uint16_t>(input.number(2)),static_cast<uint8_t>(input.number(1)),static_cast<uint8_t>(input.number(1))};
        for (uint16_t copyLimit:{uint16_t{1},uint16_t{65535}}) for (uint64_t budget:{uint64_t{1},uint64_t{17},uint64_t{4096}}) {
            auto memory=initial;const auto bus=memory.bus();FrameIterationOperation frame(entry,0x1000,0x200000);
            compare(frame.registers(),entry,index,0,true);++comparisons;size_t cursor=0;uint64_t steps=0;
            while (!frame.finished()) {
                const auto before=frame.registers();const auto used=frame.advance(budget,bus,[=](uint16_t n) {return std::min(n,copyLimit);});
                require(used && used<=budget && (steps+=used)<3000000,"Iteration dispatch grant differs");
                try {frame=FrameIterationOperation(frame.snapshot());}
                catch (const std::exception&) {std::cerr<<"restore_after="<<std::hex<<before.cs<<':'<<before.ip<<std::dec<<'\n';throw;}
                if (dense && budget==1 && copyLimit==1) {
                    ++cursor;
                    if (memory.bytes[Memory::address(before.cs,before.ip)]==0xf3 && cursor+1<trace.size() &&
                        trace[cursor].cs==before.cs && trace[cursor].ip==before.ip && trace[cursor].cx==0 && frame.registers().ip!=before.ip) ++cursor;
                    require(cursor<trace.size(),"Iteration exceeded original trace");
                    const bool exact=frame.registers().cs==0x1000 && std::binary_search(exactCaller.begin(),exactCaller.end(),frame.registers().ip);
                    compare(frame.registers(),trace[cursor],index,cursor,exact);++comparisons;if (exact) ++callerFlags;
                }
            }
            compare(frame.registers(),endpoint,index,trace.size()-1,true);++comparisons;
            require(frame.snapshot().outcome==static_cast<FrameIterationOutcome>(outcome) &&
                (1u<<frame.snapshot().callee.index())-1u==phases,"Iteration phase/outcome differs");
            if (memory.writes!=writes) {
                size_t at=0;while (at<std::min(memory.writes.size(),writes.size()) && memory.writes[at]==writes[at]) ++at;
                std::cerr<<"case="<<index<<" writes="<<memory.writes.size()<<'/'<<writes.size()<<" first_difference="<<at<<'\n';
                throw std::runtime_error("Iteration ordered writes differ");
            }
            require(memory.ports==ports,"Iteration ordered palette ports differ");
            require(memory.bytes==expected.bytes,"Iteration complete memory differs");
            dispatches+=steps;++replays;
        }
        ++outcomes[outcome];++phaseMasks[phases];writeCount+=writes.size();portCount+=ports.size();
    }
    require(input.at==input.bytes.size(),"Iteration fixture has trailing bytes");
    require(outcomes==std::array<unsigned,11>{0,952,0,0,30,53,9,16,24,18,0} &&
        phaseMasks==std::array<unsigned,8>{0,70,0,2,0,0,0,1030} && denseCases==64 &&
        writeCount==675918 && portCount==480,"Iteration observed coverage differs");
    std::cout<<"frame_iteration_original=ok cases="<<count<<" replays="<<replays<<" comparisons="<<comparisons<<" dispatches="<<dispatches
        <<" writes="<<writeCount<<" ports="<<portCount<<" dense_cases="<<denseCases<<" caller_flag_checks="<<callerFlags
        <<" next_frames="<<outcomes[1]<<" restarts="<<outcomes[4]<<" completion="<<outcomes[5]<<" escape="<<outcomes[6]
        <<" view_change="<<outcomes[7]<<" runtime_errors="<<outcomes[8]<<" divide_errors="<<outcomes[9]
        <<" all_endpoint_flags=1 full_memory=1 canonical_mz_bytes=1 later_state_injected=0 rendering_prefix_executed=0 actual_app_integration=0 full_frame_claim=0 actor_pass_hold_cleared=0\n";
}
uint64_t rejections=0;
void rejectControls(const FrameIterationSnapshot& good) {
    for (unsigned field=0;field<36;++field) {
        auto bad=good;
        switch (field) {
        case 0:++bad.gameSegment;break;case 1:++bad.callerSs;break;case 2:++bad.callerSp;break;case 3:++bad.callerBp;break;
        case 4:bad.idToggleMask=1;break;case 5:bad.entry=static_cast<FrameIterationEntry>(99);break;
        case 6:bad.outcome=static_cast<FrameIterationOutcome>(99);break;case 7:++bad.dispatchedInstructions;break;
        case 8:++bad.timerInstructions;break;case 9:++bad.timerDeliveries;break;
        case 31:bad.callee=FramePrefixSnapshot{};break;
        case 32:bad.entry=FrameIterationEntry::Full;break;case 33:bad.entry=FrameIterationEntry::PostRender;break;
        case 34:++bad.completed[bad.callee.index()][0];++bad.dispatchedInstructions;break;
        case 35:++bad.completed[0][0];++bad.dispatchedInstructions;break;
        default:
            if (field<22) ++bad.completed[(field-10)/3][(field-10)%3];
            else std::visit([&](auto& child) {
                using Child=std::remove_cvref_t<decltype(child)>;
                if (field==22 || field==23) {
                    if constexpr (std::is_same_v<Child,FrameTransientQueuesSnapshot>) {
                        if (field==22) ++child.caller.gameSegment;else child.caller.idToggleMask=1;
                    } else {if (field==22) ++child.gameSegment;else child.idToggleMask=1;}
                } else if constexpr (!std::is_same_v<Child,FramePrefixSnapshot>) {
                    if (field==24) ++child.callerSs;
                    if (field==25) ++child.callerSp;
                    if (field==26) ++child.callerBp;
                    if (field==27) ++child.dispatchedInstructions;
                    if (field==28) ++child.timerInstructions;
                    if (field==29) ++child.timerDeliveries;
                    if (field==30) child.outcome=static_cast<std::remove_cvref_t<decltype(child.outcome)>>(99);
                }
            },bad.callee);
        }
        bool failed=false;try {(void)FrameIterationOperation(bad);} catch (const std::invalid_argument&) {failed=true;}
        if (!failed) std::cerr<<"accepted_field="<<field<<" phase="<<good.callee.index()<<'\n';
        require(failed,"Iteration admitted a contradictory continuation");++rejections;
    }
}
void irqControl(FrameIterationOperation frame,Memory memory) {
    memory.store(0x70,0x0fbe);memory.store(0x72,0x1000);memory.store(0x46c,100);memory.store(0x46e,0);
    memory.bytes[0x440]=2;memory.bytes[0x43f]=0xa5;memory.bytes[0x1aa20+0x79c4]=0;
    const auto bus=memory.bus();const auto before=frame.registers();const auto original=frame.snapshot();
    frame.deliverTimerInterrupt(bus);
    bool nested=false;try {frame.deliverTimerInterrupt(bus);} catch (const std::logic_error&) {nested=true;}
    require(nested,"Iteration admitted nested timer IRQ");unsigned steps=0;
    while (frame.interruptInProgress()) {
        require(steps++<4096,"Iteration timer stalled");frame.advance(1,bus,[](uint16_t n) {return n;});frame=FrameIterationOperation(frame.snapshot());
    }
    require(steps==36 && frame.registers()==before && memory.word(0x40,0x6c)==101 &&
        frame.snapshot().timerInstructions==original.timerInstructions+36 && frame.snapshot().timerDeliveries==original.timerDeliveries+1 &&
        frame.snapshot().dispatchedInstructions==original.dispatchedInstructions+36,"Iteration timer restoration/accounting differs");
    auto other=frame;auto otherMemory=memory;const auto otherBus=otherMemory.bus();
    while (!frame.finished()) {require(steps++<100000,"Iteration IRQ continuation stalled");frame.advance(1,bus,[](uint16_t n) {return n;});frame=FrameIterationOperation(frame.snapshot());}
    while (!other.finished()) {require(steps++<100000,"Iteration alternate continuation stalled");other.advance(17,otherBus,[](uint16_t n) {return n;});other=FrameIterationOperation(other.snapshot());}
    require(frame.snapshot()==other.snapshot() && memory.bytes==otherMemory.bytes && memory.writes==otherMemory.writes && memory.ports==otherMemory.ports,
        "Iteration IRQ continuation differs across grants");
}
void unit() {
    Memory memory;memory.store(0x1aa20+0x207e,199);memory.store(0x1aa20+0x1afa,0x200);const auto bus=memory.bus();
    DosGetTimeRegisters r;r.cs=0x1000;r.ds=0x1aa2;r.es=0x40;r.ss=0x7000;r.sp=0x3fe4;r.bp=0x3ffe;r.ip=0x7ebb;r.flags=0x202;
    FrameIterationOperation frame(r,0x1000,0x200000);const auto initial=frame.snapshot();
    require(frame.advance(0,bus,[](uint16_t n) {return n;})==0 && frame.snapshot()==initial && memory.writes.empty(),"Iteration zero grant changed state");
    std::set<size_t> phases;unsigned steps=0;
    while (!frame.finished()) {
        if (phases.insert(frame.snapshot().callee.index()).second) {rejectControls(frame.snapshot());irqControl(frame,memory);}
        require(++steps<100000,"Iteration unit stalled");frame.advance(1,bus,[](uint16_t n) {return n;});frame=FrameIterationOperation(frame.snapshot());
    }
    rejectControls(frame.snapshot());const auto terminal=frame.snapshot();const auto writes=memory.writes.size();
    require(frame.snapshot().outcome==FrameIterationOutcome::NextFrame && frame.registers().ip==0x7903 && phases==std::set<size_t>{1,2,3},"Iteration unit phase/endpoint differs");
    require(frame.advance(17,bus,[](uint16_t n) {return n;})==0 && frame.snapshot()==terminal && memory.writes.size()==writes,"Iteration terminal consumed work");
    bool ended=false;try {frame.deliverTimerInterrupt(bus);} catch (const std::logic_error&) {ended=true;}
    require(ended,"Finished iteration admitted IRQ");
    r.ip=0x7903;FrameIterationOperation full(r,0x140,0x160,0x900,0x1000,0x200000);
    require(full.snapshot().entry==FrameIterationEntry::Full && full.snapshot().callee.index()==0 && FrameIterationOperation(full.snapshot()).registers()==r,"Full iteration entry admission differs");
    r.ip=0x7a57;FrameIterationOperation post(r,0x1000,0x200000);
    require(post.snapshot().entry==FrameIterationEntry::PostRender && post.snapshot().callee.index()==0 && FrameIterationOperation(post.snapshot()).registers()==r,"Post-render entry admission differs");
    unsigned entries=0;
    for (unsigned field=0;field<4;++field) {
        auto bad=r;bad.ip=0x7ebb;uint32_t id=0x200000;
        if (field==0) bad.ip=0;
        if (field==1) ++bad.cs;
        if (field==2) ++bad.ds;
        if (field==3) id=1;
        bool failed=false;try {(void)FrameIterationOperation(bad,0x1000,id);} catch (const std::invalid_argument&) {failed=true;}
        require(failed,"Iteration admitted invalid entry");++entries;
    }
    std::cout<<"frame_iteration_unit=ok state_rejections="<<rejections<<" phase_boundaries="<<phases.size()<<" computed_irq_cases=3 irq_instructions=108 entry_rejections="<<entries
        <<" full_entry_admission=1 post_render_admission=1 zero_budget=1 terminal_no_work=1 full_frame_claim=0\n";
}
} // namespace
int main(int argc,char** argv) {
    try {if (argc==1) unit();else {require(argc==3,"Expected iteration fixture and repository");replay(argv[1],argv[2]);}}
    catch (const std::exception& error) {std::cerr<<"frame_iteration_error="<<error.what()<<'\n';return 1;}
}
