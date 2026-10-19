#pragma once

#include "core/actor_motion_prefix.hpp"
#include "diagnostics/level1_trace.hpp"

#include <bit>
#include <iterator>

namespace lezac::diagnostics {

struct NonplayerMotionRow {
    uint32_t originalCase=0;
    uint8_t domain=0;
    core::ActorMotionPrefixInput input;
    std::array<uint8_t,512> animationBytes{};
    core::ActorMotionPrefixResult expected;
};

inline std::vector<NonplayerMotionRow> readNonplayerMotionFixture(const std::filesystem::path& path) {
    if (std::filesystem::file_size(path)!=4296170) throw std::runtime_error("Nonplayer motion fixture size differs");
    std::ifstream stream(path,std::ios::binary);
    if (!stream.good()) throw std::runtime_error("Missing nonplayer motion fixture");
    const std::vector<uint8_t> bytes{std::istreambuf_iterator<char>(stream),std::istreambuf_iterator<char>()};
    if (bytes.size()!=4296170 || level1::fingerprint(bytes)!="ffca38be79cab355")
        throw std::runtime_error("Nonplayer motion fixture fingerprint differs");
    size_t at=0;
    const auto number=[&](unsigned count) {
        if (count>4 || at+count>bytes.size()) throw std::runtime_error("Truncated nonplayer motion fixture");
        uint32_t value=0;for (unsigned i=0;i<count;++i) value|=uint32_t{bytes[at++]}<<(8*i);return value;
    };
    const auto word=[&] { return static_cast<uint16_t>(number(2)); };
    const auto signedWord=[&] { return std::bit_cast<int16_t>(word()); };
    for (const char c : std::string("LZNPM001"))
        if (number(1)!=static_cast<uint8_t>(c)) throw std::runtime_error("Nonplayer motion magic differs");
    const auto count=number(4);
    if (count!=6569 || level1::hexBytes(std::vector<uint8_t>(bytes.begin()+12,bytes.begin()+44))!=
            "07f6cc24b0e2460b23908306d34445cd1b4a5e0014253dc394ca2b3b945756b8")
        throw std::runtime_error("Nonplayer motion parent/domain differs");
    at=44;std::vector<NonplayerMotionRow> rows;rows.reserve(count);
    std::array<unsigned,3> domains{},outcomes{};
    for (unsigned i=0;i<count;++i) {
        NonplayerMotionRow row;row.originalCase=number(4);row.domain=static_cast<uint8_t>(number(1));
        if (row.originalCase>=78927 || (i && row.originalCase<=rows.back().originalCase) ||
                (row.domain!=0 && row.domain!=4 && row.domain!=5))
            throw std::runtime_error("Nonplayer motion row/domain differs");
        ++domains[row.domain==0 ? 0u : row.domain==4 ? 1u : 2u];
        auto& input=row.input;
        for (auto& byte : input.actor) byte=static_cast<uint8_t>(number(1));
        input.originalX=signedWord();input.x=signedWord();input.y=signedWord();input.dx=signedWord();
        input.dy=signedWord();input.vx8=signedWord();input.vy8=signedWord();
        for (auto& byte : input.edges) byte=static_cast<uint8_t>(number(1));
        for (auto& byte : input.tiles) byte=static_cast<uint8_t>(number(1));
        for (auto& value : input.shared) value=word();
        input.tick=word();input.randomSeed=number(4);input.facingRequest=static_cast<uint8_t>(number(1));
        for (auto& byte : row.animationBytes) byte=static_cast<uint8_t>(number(1));
        auto& expected=row.expected;
        for (auto& byte : expected.actor) byte=static_cast<uint8_t>(number(1));
        expected.x=signedWord();expected.y=signedWord();expected.vx8=signedWord();expected.vy8=signedWord();
        for (auto& value : expected.shared) value=word();
        expected.randomSeed=number(4);expected.facingRequest=static_cast<uint8_t>(number(1));
        const auto outcome=number(1);expected.outcome=static_cast<core::ActorMotionPrefixOutcome>(outcome);
        expected.stopIp=word();expected.instructions=number(4);
        if (outcome>2 || expected.instructions==0 || expected.instructions>=65536 ||
                (outcome==0 && expected.stopIp!=0x732c) || (outcome==2 && expected.stopIp!=0x70dc))
            throw std::runtime_error("Nonplayer motion outcome differs");
        ++outcomes[outcome];rows.push_back(row);
    }
    if (at!=bytes.size() || domains!=std::array<unsigned,3>{6461,54,54} ||
            outcomes!=std::array<unsigned,3>{6539,0,30})
        throw std::runtime_error("Nonplayer motion fixture coverage differs");
    return rows;
}

} // namespace lezac::diagnostics
