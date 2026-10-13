#include "gameplay/map_plane_memory.hpp"

#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using lezac::gameplay::MapPlaneMemory;

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

void unit() {
    MapPlaneMemory memory;
    std::vector<uint8_t> tiles;
    std::vector<uint16_t> words;
    memory.beginLevel(tiles, words, 1980);
    tiles.assign(1980, 0);
    words.assign(1980, 0);
    words[7] = 0x1234;
    require(memory.readObject(2014, tiles, words) == 0x34, "live word low alias");
    memory.writeObject(2015, 0xab, tiles, words);
    require(words[7] == 0xab34, "live word high alias");
    words[7] = 0x5c16;
    require(memory.readObject(2015, tiles, words) == 0x5c, "direct word writes stay live");
    require(memory.readWord(32775, tiles, words) == 0x5c16, "word cell wrap");
    memory.writeWord(32775, 0x1b2c, tiles, words);
    require(words[7] == 0x1b2c, "word alias write");
    memory.writeObject(-1, 0x3c, tiles, words);
    require(memory.readObject(65535, tiles, words) == 0x3c, "object offset wrap");
    memory.writeWord(-1, 0x45ac, tiles, words);
    require(memory.readWord(32767, tiles, words) == 0x45ac, "negative word wrap");
    memory.writeObject(30000, 0x56, tiles, words);
    memory.beginLevel(tiles, words, 1980);
    tiles.assign(1980, 0);
    words.assign(1980, 0);
    require(memory.readObject(30000, tiles, words) == 0x56, "retained map heap");
    require(memory.readObject(1996, tiles, words) == 8, "word free size offset");
    require(memory.readObject(1998, tiles, words) == 0xf8, "word free size paragraph");
    memory.beginLevel(tiles, words, 5304);
    tiles.assign(5304, 0);
    words.assign(5304, 0);
    words[7] = 0x5d29;
    require(memory.readObject(5326, tiles, words) == 0x29, "eight-byte aligned word allocation");
    require(memory.readObject(30000, tiles, words) == 0x56, "tail retained across map sizes");
    memory.restoreSeparatedPlanesForFixture();
    require(memory.readObject(30000, tiles, words) == 0, "fixture resets retained bytes");
    require(memory.readObject(5326, tiles, words) == 0, "fixture planes do not alias");
    memory.writeWord(32775, 0x12ab, tiles, words);
    require(words[7] == 0x12ab, "fixture word wrap");
    bool rejected = false;
    try { memory.restoreSeparatedPlanesForFixture(std::vector<uint8_t>(1)); }
    catch (const std::runtime_error&) { rejected = true; }
    require(rejected, "reject partial seeded planes");
    std::cout << "map_plane_memory_unit=ok object_wrap=1 word_wrap=1 live_alias=1 retained_heap=1 fixture_isolation=1\n";
}

uint32_t read(std::istream& input, size_t count) {
    uint32_t value = 0;
    for (size_t i = 0; i < count; ++i) {
        const int byte = input.get();
        require(byte != EOF, "truncated map replay");
        value |= static_cast<uint32_t>(byte) << (8 * i);
    }
    return value;
}

void write(std::ostream& output, uint32_t value, size_t count) {
    for (size_t i = 0; i < count; ++i) output.put(static_cast<char>(value >> (8 * i)));
}

void replay(const char* source, const char* target) {
    std::ifstream input(source, std::ios::binary);
    std::ofstream output(target, std::ios::binary);
    require(input.good() && output.good(), "open map replay files");
    char magic[8]{};
    input.read(magic, 8);
    require(std::string(magic, 8) == "LZMP0001", "map replay magic");
    const uint32_t cases = read(input, 4);
    require(cases == 12, "map replay scene count");
    output.write("LZMR0001", 8);
    write(output, cases, 4);
    size_t totalReads = 0, totalWrites = 0;
    for (uint32_t scene = 0; scene < cases; ++scene) {
        const uint32_t layout = read(input, 4);
        const uint32_t width = read(input, 2), height = read(input, 2);
        const uint32_t events = read(input, 4);
        require(layout <= 1 && width == 60 && height == 33 && events <= 256, "map replay dimensions");
        std::vector<uint8_t> planes(131072);
        input.read(reinterpret_cast<char*>(planes.data()), static_cast<std::streamsize>(planes.size()));
        require(input.gcount() == static_cast<std::streamsize>(planes.size()), "truncated seeded planes");
        std::vector<uint8_t> tiles(planes.begin(), planes.begin() + 1980);
        std::vector<uint16_t> words(1980);
        for (size_t i = 0; i < words.size(); ++i) {
            words[i] = static_cast<uint16_t>(planes[65536 + 2 * i] | (planes[65537 + 2 * i] << 8));
        }
        MapPlaneMemory memory;
        if (layout == 0) memory.restoreSeparatedPlanesForFixture(planes);
        else {
            memory.beginLevel({}, {}, 1980);
            memory.seedPlanesForFixture(planes);
        }
        std::vector<uint16_t> reads;
        for (uint32_t event = 0; event < events; ++event) {
            const uint32_t plane = read(input, 1), writing = read(input, 1);
            const uint32_t offset = read(input, 2), value = read(input, 2);
            require(plane <= 1 && writing <= 1 && (plane == 0 || offset % 2 == 0), "invalid map access");
            require((writing || value == 0) && (plane != 0 || value <= 255), "read events must not supply expected bytes");
            if (writing) {
                if (plane == 0) memory.writeObject(static_cast<int>(offset), static_cast<uint8_t>(value), tiles, words);
                else memory.writeWord(static_cast<int>(offset / 2), static_cast<uint16_t>(value), tiles, words);
                ++totalWrites;
            } else {
                reads.push_back(plane == 0 ? memory.readObject(static_cast<int>(offset), tiles, words) :
                    memory.readWord(static_cast<int>(offset / 2), tiles, words));
                ++totalReads;
            }
        }
        write(output, static_cast<uint32_t>(reads.size()), 4);
        for (uint16_t value : reads) write(output, value, 2);
        for (int cell = 0; cell < 65536; ++cell) write(output, memory.readObject(cell, tiles, words), 1);
        for (int cell = 0; cell < 32768; ++cell) write(output, memory.readWord(cell, tiles, words), 2);
    }
    require(input.get() == EOF && output.good(), "map replay trailing bytes or output failure");
    std::cout << "map_plane_memory_app=ok scenes=" << cases << " reads=" << totalReads
              << " writes=" << totalWrites << " production_app=0\n";
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 1) unit();
        else if (argc == 4 && std::string(argv[1]) == "--replay") replay(argv[2], argv[3]);
        else throw std::runtime_error("invalid map memory test command");
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    return 0;
}
