#pragma once

#include "diagnostics/level1_trace.hpp"

#include <bit>
#include <cstdlib>
#include <iterator>

namespace lezac::diagnostics {

struct ActorSteeringFixtureRow {
    uint32_t originalCase=0;
    int16_t dx=0,dy=0;
    uint16_t speed=0;
    int16_t vx8=0,vy8=0;
    uint8_t domain=0;
    bool homingAdmitted=false;
};

inline std::vector<ActorSteeringFixtureRow> readActorSteeringFixture(const std::filesystem::path& path) {
    if (std::filesystem::file_size(path)!=34220) throw std::runtime_error("Steering vector fixture size differs");
    std::ifstream input(path,std::ios::binary);
    if (!input.good()) throw std::runtime_error("Missing steering vector fixture");
    const std::vector<uint8_t> bytes{std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
    // The exporter authenticates SHA-256 against the original projection. This
    // independent in-process fingerprint also rejects changed direct CLI input.
    if (bytes.size()!=34220 || level1::fingerprint(bytes)!="152636e6eac73d06")
        throw std::runtime_error("Steering vector fixture fingerprint differs");
    size_t at=0;
    const auto number=[&](unsigned count) {
        if (count>4 || at+count>bytes.size()) throw std::runtime_error("Truncated steering vector fixture");
        uint32_t value=0;for (unsigned i=0;i<count;++i) value|=uint32_t{bytes[at++]}<<(8*i);return value;
    };
    for (const char c : std::string("LZSTV001"))
        if (number(1)!=static_cast<uint8_t>(c)) throw std::runtime_error("Steering vector fixture magic differs");
    const auto count=number(4);
    if (count!=2136 || level1::hexBytes(std::vector<uint8_t>(bytes.begin()+12,bytes.begin()+44))!=
            "acc7c781d4fcf5d24e16ffdccefd13032830c1010b8453b30aefd1210f8ed334")
        throw std::runtime_error("Steering vector parent/corpus differs");
    at=44;std::vector<ActorSteeringFixtureRow> rows;rows.reserve(count);unsigned callers=0,admitted=0;
    const auto signedWord=[&] { return std::bit_cast<int16_t>(static_cast<uint16_t>(number(2))); };
    for (unsigned i=0;i<count;++i) {
        ActorSteeringFixtureRow row;row.originalCase=number(4);row.dx=signedWord();row.dy=signedWord();
        row.speed=static_cast<uint16_t>(number(2));row.vx8=signedWord();row.vy8=signedWord();
        row.domain=static_cast<uint8_t>(number(1));const auto gate=number(1);
        if (row.originalCase>=3736 || (i && row.originalCase<=rows.back().originalCase) || row.domain>1 || gate>1 ||
            bool(gate)!=(std::abs(int{row.dx})+std::abs(int{row.dy})<65535))
            throw std::runtime_error("Steering vector row/domain differs");
        row.homingAdmitted=gate!=0;callers+=row.domain;admitted+=row.homingAdmitted;rows.push_back(row);
    }
    if (at!=bytes.size() || callers!=64 || admitted!=2097) throw std::runtime_error("Steering vector fixture coverage differs");
    return rows;
}

} // namespace lezac::diagnostics
