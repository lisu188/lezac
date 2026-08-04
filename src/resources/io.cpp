#include "resources/io.hpp"

#include <fstream>
#include <iterator>
#include <sstream>
#include <stdexcept>

namespace lezac::resources {

std::vector<uint8_t> readFile(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in && path.find('/') == std::string::npos &&
        path.find('\\') == std::string::npos) {
        in.clear();
        in.open("src/" + path, std::ios::binary);
    }
    if (!in) {
        throw std::runtime_error("cannot open " + path);
    }
    return std::vector<uint8_t>(std::istreambuf_iterator<char>(in),
                                std::istreambuf_iterator<char>());
}

std::string readTextFile(const std::string& path) {
    std::ifstream in(path);
    if (!in && path.find('/') == std::string::npos &&
        path.find('\\') == std::string::npos) {
        in.clear();
        in.open("src/" + path);
    }
    if (!in) {
        throw std::runtime_error("cannot open " + path);
    }
    return std::string(std::istreambuf_iterator<char>(in),
                       std::istreambuf_iterator<char>());
}

std::vector<uint8_t> parseHexByteList(const std::string& hexList) {
    std::vector<uint8_t> out;
    std::istringstream iss(hexList);
    std::string token;
    while (iss >> token) {
        int value = std::stoi(token, nullptr, 16);
        out.push_back(static_cast<uint8_t>(value));
    }
    return out;
}

std::vector<uint16_t> parseHexWordList(const std::string& hexList) {
    std::vector<uint16_t> out;
    std::istringstream iss(hexList);
    std::string token;
    while (iss >> token) {
        int value = std::stoi(token, nullptr, 16);
        out.push_back(static_cast<uint16_t>(value));
    }
    return out;
}

}
