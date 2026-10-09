#include "gameplay/retained_record_queue.hpp"

#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>

namespace {
using Record = std::array<uint8_t, 15>;
void require(bool condition) {
    if (!condition) throw std::runtime_error("retained record queue contract failed");
}
Record salt(uint8_t seed) {
    Record result{};
    for (size_t i = 0; i < result.size(); ++i) result[i] = static_cast<uint8_t>(seed + i * 19);
    return result;
}
}

int main() {
    lezac::gameplay::RetainedRecordQueue<Record> queue;
    require(queue.empty() && queue.begin() == queue.end());
    const auto a = salt(1), b = salt(31), c = salt(67), dormant = salt(103);
    queue.push_back(a); queue.push_back(b); queue.push_back(c);
    queue.retainedSlot(3) = dormant;
    require(queue.size() == 3 && queue.front() == a && queue.back() == c);
    size_t visited = 0;
    for (const auto& record : queue) { require(record != dormant); ++visited; }
    require(visited == 3);
    auto next = queue.erase(queue.begin() + 1);
    require(next == queue.begin() + 1 && *next == c && queue.size() == 2);
    require(queue.retainedSlot(2) == c && queue.retainedSlot(3) == dormant);
    queue.back()[0] = 9;
    require(queue[1][0] == 9 && queue.retainedSlot(2) == c);
    queue.pop_back();
    require(queue.size() == 1 && queue.retainedSlot(1)[0] == 9);
    queue.push_back(b);
    require(queue.size() == 2 && queue.back() == b && queue.retainedSlot(2) == c);
    auto copy = queue;
    copy.front()[0] = 255;
    require(queue.front() == a && copy.front()[0] == 255);
    queue.clear();
    require(queue.empty() && queue.begin() == queue.end());
    require(queue.retainedSlot(0) == a && queue.retainedSlot(1) == b);
    queue.push_back(c);
    require(queue.size() == 1 && queue.front() == c && queue.retainedSlot(1) == b);
    const auto erased = queue.erase(queue.begin());
    require(erased == queue.end() && queue.empty());
    require(queue.retainedSlot(0) == c);
    const auto& retained = queue;
    require(retained.begin() == retained.end() && retained.retainedSlot(3) == dormant);
    bool bounded = false;
    try { retained.retainedSlot(4); } catch (const std::out_of_range&) { bounded = true; }
    require(bounded);
    std::cout << "retained_record_queue=ok live_order=1 stale_tail=1 clear_retains=1 dormant_excluded=1\n";
}
