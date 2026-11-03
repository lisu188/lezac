#include "gameplay/fracture_records.hpp"

#include <cstdint>
#include <iostream>

int main() {
    std::uint64_t cases = 0;
    for (std::uint32_t previous = 0; previous <= 0xffffu; ++previous) {
        for (std::uint32_t current = 0; current <= 256u; ++current) {
            const auto word = static_cast<std::uint16_t>(previous - current);
            const std::int32_t signedDifference = word < 0x8000u ? word : std::int32_t{word} - 65536;
            const auto expected = static_cast<std::uint16_t>(signedDifference < 0 ? -signedDifference : signedDifference);
            const auto actual = lezac::gameplay::collapseMagnitudeDelta(
                static_cast<std::uint16_t>(previous), static_cast<std::uint16_t>(current));
            if (actual != expected || (actual > 63) != (expected > 63)) {
                std::cerr << "collapse magnitude differs: " << previous << ' ' << current << '\n';
                return 1;
            }
            ++cases;
        }
    }
    std::cout << "collapse_magnitude_wrap_unit=ok cases=" << cases
              << " word_wrap=1 signed_abs=1 unsigned_threshold=1\n";
}
