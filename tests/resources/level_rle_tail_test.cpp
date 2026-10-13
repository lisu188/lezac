#include "gameplay/map_plane_memory.hpp"
#include "rendering/presentation_state.hpp"
#include "resources/levels.hpp"

#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

void unit() {
    using lezac::resources::decodeLevelRle3WithTail;
    const auto maximum = decodeLevelRle3WithTail({0xff, 0x7b, 0x9a}, 1);
    require(maximum.bytes == std::vector<uint8_t>{0x7b} &&
            maximum.tail == std::vector<uint8_t>(16, 0x7b), "maximum inclusive first-run tail");
    const auto second = decodeLevelRle3WithTail({0x0f, 0x17, 0x28}, 2);
    require(second.bytes == std::vector<uint8_t>({0x17, 0x28}) &&
            second.tail == std::vector<uint8_t>(16, 0x28), "maximum inclusive second-run tail");
    const auto shortInput = decodeLevelRle3WithTail({0, 0x11, 0x22}, 4);
    require(shortInput.bytes == std::vector<uint8_t>({0x11, 0x22, 0x22, 0}) &&
            shortInput.tail.empty(), "do not retain unwritten scratch capacity");
    const auto empty = decodeLevelRle3WithTail({}, 3);
    require(empty.bytes == std::vector<uint8_t>(3) && empty.tail.empty(), "empty input compatibility");
    const auto zero = decodeLevelRle3WithTail({0xff, 1, 2}, 0);
    require(zero.bytes.empty() && zero.tail.empty(), "zero target compatibility");

    lezac::gameplay::MapPlaneMemory memory;
    std::vector<uint8_t> tiles(1980);
    std::vector<uint16_t> words(1980);
    memory.beginLevel({}, {}, tiles.size());
    memory.writeObject(1983, 0x52, tiles, words);
    memory.retainObjectDecoderTail({0x18}, tiles, words);
    require(memory.readObject(1980, tiles, words) == 0x18 &&
            memory.readObject(1983, tiles, words) == 0x52, "only actual object writes retained");
    memory.retainWordDecoderTail(std::vector<uint8_t>(8, 0x33), tiles, words);
    require(memory.readWord(1980, tiles, words) == 0x3333 &&
            memory.readObject(5967, tiles, words) == 0x33 &&
            memory.readWord(1984, tiles, words) == 0, "word tail retained in overlapping views");
    memory.beginLevel(tiles, words, 100);
    tiles.assign(100, 0);
    words.assign(100, 0);
    require(memory.readObject(5967, tiles, words) == 0x33, "tail survives subsequent map allocation");

    lezac::gameplay::MapPlaneMemory alias;
    alias.beginLevel({}, {}, 1);
    tiles.assign(1, 0);
    words.assign(1, 0);
    std::vector<uint8_t> tail(16);
    for (size_t i = 0; i < tail.size(); ++i) tail[i] = static_cast<uint8_t>(0xa0 + i);
    alias.retainObjectDecoderTail(tail, tiles, words);
    require(words[0] == 0xaf, "object tail aliases later word allocation");
    words[0] = 0x1234;
    alias.retainWordDecoderTail({0xc1}, tiles, words);
    require(alias.readObject(15, tiles, words) == 0xae &&
            alias.readObject(16, tiles, words) == 0x34 &&
            alias.readObject(17, tiles, words) == 0x12 &&
            alias.readObject(18, tiles, words) == 0xc1, "word decoder wins in original write order");
    for (bool object : {true, false}) {
        bool rejected = false;
        try {
            if (object) alias.retainObjectDecoderTail(std::vector<uint8_t>(17), tiles, words);
            else alias.retainWordDecoderTail(std::vector<uint8_t>(17), tiles, words);
        } catch (const std::runtime_error&) { rejected = true; }
        require(rejected, "reject impossible decoder tail length");
    }
    std::cout << "level_rle_tail_unit=ok inclusive_runs=1 exact_tail=1 alias_order=1 retained_heap=1\n";
}

uint32_t read(std::istream& input) {
    uint32_t value = 0;
    for (unsigned i = 0; i < 4; ++i) {
        const int byte = input.get();
        require(byte != EOF, "truncated decoder replay");
        value |= static_cast<uint32_t>(byte) << (8 * i);
    }
    return value;
}

std::vector<uint8_t> bytes(std::istream& input, size_t size) {
    std::vector<uint8_t> result(size);
    input.read(reinterpret_cast<char*>(result.data()), static_cast<std::streamsize>(size));
    require(input.gcount() == static_cast<std::streamsize>(size), "truncated decoder bytes");
    return result;
}

void write(std::ostream& output, uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) output.put(static_cast<char>(value >> (8 * i)));
}

void replay(const char* source, const char* target) {
    std::ifstream input(source, std::ios::binary);
    std::ofstream output(target, std::ios::binary);
    require(input.good() && output.good(), "open decoder replay files");
    const auto magic = bytes(input, 8);
    require(std::string(magic.begin(), magic.end()) == "LZRT0001", "decoder replay magic");
    const auto count = read(input);
    require(count == 22, "decoder case count");
    output.write("LZRO0001", 8);
    write(output, count);
    for (uint32_t i = 0; i < count; ++i) {
        const auto size = read(input), encodedSize = read(input);
        require(size > 0 && size <= 32768 && encodedSize <= 60000, "decoder replay bounds");
        lezac::rendering::PresentationState presentation;
        presentation.restoreBackdrop(bytes(input, 60000));
        const auto encoded = bytes(input, encodedSize);
        const auto actual = presentation.decodeLevelPlaneWithTail(encoded, size);
        const auto direct = lezac::resources::decodeLevelRle3WithTail(presentation.backdropBuffer(), size);
        require(actual.bytes == direct.bytes && actual.tail == direct.tail, "presentation decoder forwarding");
        require(presentation.decodeLevelPlane(encoded, size) == actual.bytes &&
                lezac::resources::decodeLevelRle3(presentation.backdropBuffer(), size) == actual.bytes,
                "payload-only API compatibility");
        write(output, static_cast<uint32_t>(actual.bytes.size()));
        write(output, static_cast<uint32_t>(actual.tail.size()));
        for (uint8_t byte : actual.bytes) output.put(static_cast<char>(byte));
        for (uint8_t byte : actual.tail) output.put(static_cast<char>(byte));
    }
    require(input.get() == EOF && output.good(), "decoder replay trailing bytes or output failure");
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 1) unit();
        else if (argc == 4 && std::string(argv[1]) == "--replay") replay(argv[2], argv[3]);
        else throw std::runtime_error("invalid decoder test arguments");
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    return 0;
}
