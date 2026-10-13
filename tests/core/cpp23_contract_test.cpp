#include <bit>
#include <cstdint>
#include <iostream>
#include <span>
#include <string_view>
#include <utility>

enum class ContractWord : uint16_t { Value = 0x1234 };
static_assert(std::to_underlying(ContractWord::Value) == 0x1234);
static_assert(std::byteswap(uint32_t{0x12345678}) == 0x78563412);
static_assert(std::string_view{"lezac_cpp23"}.contains("cpp23"));
constexpr uint8_t bytes[]{1, 2, 3};
static_assert(std::span{bytes}.size() == 3);

int main() {
    std::cout << "cpp23_standard_contract=ok to_underlying=1 byteswap=1 contains=1 span=1\n";
}
