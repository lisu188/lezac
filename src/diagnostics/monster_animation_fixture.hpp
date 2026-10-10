#pragma once

#include "gameplay/actor_models.hpp"

#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>

namespace lezac::diagnostics {

inline void requireMonsterAnimation(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error("monster animation fixture: " + message);
}

inline std::string readMonsterAnimationFixture(const std::string& path) {
    std::ifstream input(path, std::ios::binary);
    requireMonsterAnimation(input.is_open(), "cannot open input");
    std::string raw;
    char byte = 0;
    while (input.get(byte)) {
        requireMonsterAnimation(raw.size() < 128 * 1024, "input exceeds cap");
        raw.push_back(byte);
    }
    requireMonsterAnimation(!input.bad(), "input read failed");
    std::string text;
    for (size_t i = 0; i < raw.size(); ++i) {
        if (raw[i] == '\r') {
            requireMonsterAnimation(i + 1 < raw.size() && raw[i + 1] == '\n', "isolated carriage return");
        } else {
            text.push_back(raw[i]);
        }
    }
    uint64_t fingerprint = 14695981039346656037ull;
    for (unsigned char value : text) fingerprint = (fingerprint ^ value) * 1099511628211ull;
    requireMonsterAnimation(text.size() == 56244 && fingerprint == 0x0a33b9389958728eull,
                            "input fingerprint mismatch");
    return text;
}

inline unsigned monsterAnimationNumber(const std::string& text, unsigned maximum) {
    requireMonsterAnimation(!text.empty() && text.find_first_not_of("0123456789") == std::string::npos,
                            "invalid unsigned number");
    const auto value = std::stoul(text);
    requireMonsterAnimation(value <= maximum && std::to_string(value) == text, "number out of range");
    return static_cast<unsigned>(value);
}

inline gameplay::ActorAnimation monsterAnimationBytes(const std::string& text) {
    requireMonsterAnimation(text.size() == 14 && text.find_first_not_of("0123456789abcdef") == std::string::npos,
                            "invalid animation bytes");
    std::array<uint8_t, 7> bytes{};
    for (size_t i = 0; i < bytes.size(); ++i) {
        bytes[i] = static_cast<uint8_t>(std::stoul(text.substr(i * 2, 2), nullptr, 16));
    }
    return {bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], static_cast<int8_t>(bytes[6])};
}

template<class Seed, class Step>
void replayMonsterAnimationFixture(const std::string& path, Seed seed, Step step) {
    std::istringstream input(readMonsterAnimationFixture(path));
    std::string line;
    requireMonsterAnimation(static_cast<bool>(std::getline(input, line)), "missing header");
    requireMonsterAnimation(line == "capture=monster_animation_original_v1 seeded=1 cpu_only=1 instruction_patches=0 call_stubs=0 hardware_io=0",
                            "unexpected header");
    unsigned cases = 0, updates = 0, sample = 0;
    bool inCase = false, complete = false;
    std::string name;
    std::set<std::string> names;
    gameplay::ActiveMonster monster;
    while (std::getline(input, line)) {
        requireMonsterAnimation(!complete, "trailing record");
        std::istringstream record(line);
        std::string tag, token;
        record >> tag;
        std::map<std::string, std::string> fields;
        while (record >> token) {
            const auto equals = token.find('=');
            requireMonsterAnimation(equals != std::string::npos && equals != 0 && equals + 1 < token.size() &&
                                    token.find('=', equals + 1) == std::string::npos, "malformed field");
            requireMonsterAnimation(fields.emplace(token.substr(0, equals), token.substr(equals + 1)).second,
                                    "duplicate field");
        }
        auto keys = [&](std::set<std::string> expected) {
            std::set<std::string> actual;
            for (const auto& field : fields) actual.insert(field.first);
            requireMonsterAnimation(actual == expected, "unexpected field set");
        };
        if (tag == "case") {
            keys({"name", "active", "backup", "visible", "samples"});
            requireMonsterAnimation(!inCase && cases < 53 && fields.at("samples") == "12", "invalid case boundary");
            name = fields.at("name");
            requireMonsterAnimation(names.insert(name).second, "duplicate case");
            monster = gameplay::ActiveMonster{};
            monster.kind = 1;
            monster.behavior = 3;
            monster.actorOrder = 1;
            gameplay::setMonsterAnimation(monster, monsterAnimationBytes(fields.at("active")));
            monster.animationBackup = monsterAnimationBytes(fields.at("backup"));
            monster.animFrame = static_cast<uint8_t>(monsterAnimationNumber(fields.at("visible"), 255));
            seed(monster);
            sample = 0;
            inCase = true;
        } else if (tag == "tick") {
            keys({"sample", "advanced", "active", "backup", "visible"});
            requireMonsterAnimation(inCase && sample < 12 && monsterAnimationNumber(fields.at("sample"), 11) == sample,
                                    "nonconsecutive sample");
            const bool advanced = step(monster);
            const std::string boundary = name + " sample=" + std::to_string(sample);
            requireMonsterAnimation(advanced == (monsterAnimationNumber(fields.at("advanced"), 1) != 0),
                                    boundary + " advance mismatch");
            requireMonsterAnimation(gameplay::monsterAnimation(monster).packed() == monsterAnimationBytes(fields.at("active")).packed(),
                                    boundary + " active bytes mismatch");
            requireMonsterAnimation(monster.animationBackup.packed() == monsterAnimationBytes(fields.at("backup")).packed(),
                                    boundary + " backup bytes mismatch");
            requireMonsterAnimation(monster.animFrame == monsterAnimationNumber(fields.at("visible"), 255),
                                    boundary + " visible index mismatch");
            ++sample;
            ++updates;
        } else if (tag == "end") {
            keys({"samples"});
            requireMonsterAnimation(inCase && sample == 12 && fields.at("samples") == "12", "incomplete case");
            inCase = false;
            ++cases;
        } else if (tag == "complete") {
            keys({"cases", "updates"});
            requireMonsterAnimation(!inCase && cases == 53 && updates == 636 && fields.at("cases") == "53" &&
                                    fields.at("updates") == "636", "incomplete coverage");
            complete = true;
        } else {
            requireMonsterAnimation(false, "unknown record");
        }
    }
    requireMonsterAnimation(complete, "missing completion record");
}

} // namespace lezac::diagnostics
