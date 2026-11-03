#include "core/actor_contact.hpp"

#include <array>
#include <charconv>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <utility>

namespace {
using namespace lezac::core;
constexpr std::size_t words=259;
constexpr std::uint64_t owner=0x0020000000001000ull;
constexpr std::uint64_t ownerMask=0xffffffff0000ffffull;
struct Snapshot { std::array<std::uint64_t,words> cells{}; };
static_assert(sizeof(Snapshot)==2072);

// Keep the by-value copy boundary visible in the generated diagnostic code.
[[gnu::noinline]] Snapshot clone(Snapshot input) { return input; }

[[gnu::noinline]] DosGetTimeRegisters variantProbe(FrameActorContactSnapshot input) {
    const FrameActorContactOperation active(std::move(input));
    if (active.interruptInProgress()) throw std::runtime_error("Copy control unexpectedly owns a timer");
    return active.registers();
}

int variantControl(std::uint64_t iterations) {
    DosGetTimeRegisters expected;
    expected.ax=80;expected.si=0x1357;expected.di=0xc236;expected.bp=0x3fdc;
    expected.cs=0x1000;expected.ds=expected.es=0x1aa2;expected.ss=0x7000;
    expected.sp=0x3fa2;expected.ip=0x615a;expected.flags=0x602;
    auto animation=expected;animation.ip=0x6053;
    auto contact=expected;contact.ip=0x654e;
    const std::array expectedStates{expected,animation,contact};
    const std::array<FrameActorContactSnapshot,3> frozen{
        FrameActorContactOperation(expected,0x1000,0x200000).snapshot(),
        FrameActorContactOperation(animation,0x1000,0x200000).snapshot(),
        FrameActorContactOperation(contact,0x1000,0x200000).snapshot()};
    auto current=frozen.front();
    using Probe=DosGetTimeRegisters (*)(FrameActorContactSnapshot);
    Probe volatile probe=&variantProbe;
    std::uint64_t checksum=0,iteration=0;
    try {
        for (;iteration<iterations;++iteration) {
            const auto phase=iteration%frozen.size();
            current.callee=frozen[phase].callee;
            const auto actual=probe(current);
            if (actual!=expectedStates[phase]) {
                std::cerr<<"actor_variant_control=failed iteration="<<iteration<<" actual_cx="<<std::hex
                    <<actual.cx<<" expected_cx="<<expectedStates[phase].cx<<std::dec
                    <<" guest_instructions=0 diagnosis_claim=0 intermittent_hold_cleared=0\n";
                return 1;
            }
            checksum^=actual.ax+actual.bx+actual.cx+actual.flags+iteration;
        }
    } catch (const std::exception& error) {
        std::cerr<<"actor_variant_control=failed iteration="<<iteration<<" error="<<error.what()
            <<" guest_instructions=0 diagnosis_claim=0 intermittent_hold_cleared=0\n";
        return 1;
    }
    std::cout<<"actor_variant_control=ok iterations="<<iterations<<" snapshot_bytes="<<sizeof(FrameActorContactSnapshot)
        <<" phases=3 mutable_callee=1"
        <<" checksum="<<std::hex<<checksum<<std::dec
        <<" guest_instructions=0 diagnosis_claim=0 intermittent_hold_cleared=0\n";
    return 0;
}

bool mismatch(std::uint64_t iteration,std::size_t word,std::uint64_t actual,std::uint64_t expected) {
    if (actual==expected) return false;
    std::cerr<<"actor_copy_control=failed iteration="<<iteration<<" word="<<word
        <<" actual="<<std::hex<<actual<<" expected="<<expected<<" xor="<<(actual^expected)
        <<std::dec<<" game_logic=0 diagnosis_claim=0 intermittent_hold_cleared=0\n";
    return true;
}
}

int main(int argc,char** argv) {
    std::uint64_t iterations=2000000;
    if (argc==2 || argc==3) {
        const std::string_view text=argv[1];
        const auto parsed=std::from_chars(text.data(),text.data()+text.size(),iterations);
        if (text.empty() || parsed.ec!=std::errc{} || parsed.ptr!=text.data()+text.size() ||
            !iterations || iterations>16000000) return 2;
    } else if (argc!=1) return 2;
    if (argc==3) {
        if (std::string_view(argv[2])=="variant") {
            try { return variantControl(iterations); }
            catch (const std::exception& error) {
                std::cerr<<"actor_variant_control=setup_failed error="<<error.what()<<'\n';return 1;
            }
        }
        if (std::string_view(argv[2])!="words") return 2;
    }
    Snapshot original;
    for (std::size_t i=0;i<words;++i) original.cells[i]=0x9e3779b97f4a7c15ull*(i+1);
    original.cells[4]=owner;original.cells[248]=owner;original.cells[254]=owner;
    std::uint64_t checksum=0;
    for (std::uint64_t iteration=0;iteration<iterations;++iteration) {
        original.cells[0]=iteration*0xd1342543de82ef95ull;
        const auto first=clone(original);
        const auto second=clone(first);
        if (mismatch(iteration,254,second.cells[254]&ownerMask,second.cells[248]&ownerMask)) return 1;
        for (std::size_t word=0;word<words;++word) {
            if (mismatch(iteration,word,first.cells[word],original.cells[word]) ||
                mismatch(iteration,word,second.cells[word],original.cells[word])) return 1;
            checksum^=second.cells[word]+iteration;
        }
    }
    std::cout<<"actor_copy_control=ok iterations="<<iterations<<" words="<<words
        <<" copies="<<iterations*2<<" checksum="<<std::hex<<checksum<<std::dec
        <<" game_logic=0 diagnosis_claim=0 intermittent_hold_cleared=0\n";
}
