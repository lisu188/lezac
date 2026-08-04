#include "resources/io.hpp"

#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

int main() {
    const std::vector<uint8_t> bytes = lezac::resources::parseHexByteList("00 7f ff 100");
    if (bytes != std::vector<uint8_t>({0x00, 0x7f, 0xff, 0x00})) return 1;

    const std::vector<uint16_t> words = lezac::resources::parseHexWordList("0000 1234 ffff 10000");
    if (words != std::vector<uint16_t>({0x0000, 0x1234, 0xffff, 0x0000})) return 2;

    const std::string path = "resource_io_test.tmp";
    {
        std::ofstream out(path, std::ios::binary);
        out << "A\nB\0C";
    }

    const std::vector<uint8_t> fileBytes = lezac::resources::readFile(path);
    if (fileBytes != std::vector<uint8_t>({'A', '\n', 'B', 0, 'C'})) return 3;

    const std::string text = lezac::resources::readTextFile(path);
    if (text.size() != 5 || text[0] != 'A' || text[1] != '\n' || text[2] != 'B' ||
        text[3] != '\0' || text[4] != 'C') return 4;

    std::remove(path.c_str());
    std::cout << "resource_io=ok bytes=4 words=4 binary=5 text=5\n";
    return 0;
}
