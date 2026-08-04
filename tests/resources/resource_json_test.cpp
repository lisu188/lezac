#include "resources/json.hpp"

#include <iostream>
#include <string>
#include <vector>

int main() {
    const std::string json =
        R"({"rows":["aa","bb"],"objects":[{"x":1},{"x":2,"nested":{"y":3}}],"n":-42,"name":"lezac"})";

    const std::vector<std::string> rows = lezac::resources::extractStringArray(json, "rows");
    if (rows != std::vector<std::string>({"aa", "bb"})) return 1;

    const std::vector<std::string> objects = lezac::resources::extractObjectArray(json, "objects");
    if (objects.size() != 2 || objects[0] != R"({"x":1})" ||
        objects[1] != R"({"x":2,"nested":{"y":3}})") return 2;

    if (lezac::resources::extractInt(json, "n", 7) != -42) return 3;
    if (lezac::resources::extractInt(json, "missing", 7) != 7) return 4;
    if (lezac::resources::extractString(json, "name", "fallback") != "lezac") return 5;
    if (lezac::resources::extractString(json, "missing", "fallback") != "fallback") return 6;

    std::cout << "resource_json=ok rows=2 objects=2 int=-42 string=lezac fallbacks=2\n";
    return 0;
}
