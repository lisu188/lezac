#include "gameplay/monster_spawners.hpp"
#include "resources/levels.hpp"

#include <iostream>
#include <stdexcept>

using Storage = lezac::gameplay::MonsterSpawnerStorage;

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

int main() {
    try {
        Storage::State initial{};
        for (size_t source = 0; source < initial.size(); ++source)
            for (size_t byte = 0; byte < initial[source].size(); ++byte)
                initial[source][byte] = static_cast<uint8_t>(source * 31 + byte * 17 + 13);
        for (size_t byte = 0; byte < 30; ++byte)
            for (unsigned value = 0; value < 256; ++value) {
                auto row = initial[1];
                row[byte] = static_cast<uint8_t>(value);
                require(lezac::resources::packMonsterSpawner(lezac::resources::parseMonsterSpawner(row)) == row,
                        "spawner codec lost a byte");
            }
        Storage storage;
        for (uint8_t source = 0; source < 9; ++source)
            for (unsigned value = 0; value < 256; ++value) {
                auto before = initial;
                before[source][10] = static_cast<uint8_t>(value);
                storage.restoreForFixture(before);
                require(storage.release(source) == (source != 0), "spawner release gate differs");
                if (source) ++before[source][10];
                require(storage.state() == before, "spawner release changed an unowned byte");
            }
        for (uint8_t source = 1; source < 9; ++source)
            for (unsigned cooldown = 0; cooldown < 256; ++cooldown)
                for (uint8_t enabled = 0; enabled < 3; ++enabled)
                    for (uint8_t budget = 0; budget < 2; ++budget)
                        for (uint8_t available = 0; available < 2; ++available) {
                            auto before = initial;
                            auto& row = before[source];
                            row[8] = enabled; row[9] = budget; row[10] = available;
                            row[27] = static_cast<uint8_t>(cooldown);
                            storage.restoreForFixture(before);
                            --row[27];
                            const bool ready = !row[27] && available && budget && enabled == 1;
                            if (ready) row[27] = row[28];
                            require(storage.tick(source) == ready, "spawner readiness differs");
                            require(storage.state() == before, "spawner tick changed an unowned byte");
                            if (ready) {
                                storage.consume(source);
                                --row[9]; --row[10];
                                require(storage.state() == before, "spawner consumption changed an unowned byte");
                            }
                        }
        for (const uint8_t source : {uint8_t{9}, uint8_t{255}}) {
            size_t rejected = 0;
            try { storage.record(source); } catch (const std::out_of_range&) { ++rejected; }
            try { storage.loadRecord(source, initial[0]); } catch (const std::out_of_range&) { ++rejected; }
            try { storage.release(source); } catch (const std::out_of_range&) { ++rejected; }
            try { storage.tick(source); } catch (const std::out_of_range&) { ++rejected; }
            try { storage.consume(source); } catch (const std::out_of_range&) { ++rejected; }
            require(rejected == 5, "invalid spawner source accepted");
        }
        std::cout << "spawner_storage=ok roundtrips=7680 releases=2304 ticks=24576 invalid_sources=10\n";
    } catch (const std::exception& error) {
        std::cerr << "spawner_storage=failed " << error.what() << '\n';
        return 1;
    }
}
