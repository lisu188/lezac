#include "resources/json.hpp"

#include <iostream>
#include <string>
#include <vector>

int main() {
    const std::string json =
        R"({"rows":["aa","bb"],"objects":[{"x":1},{"x":2,"nested":{"y":3}}],"n":-42,"name":"lezac"})";

    const std::string normalized =
        R"({"rows":["aa","bb"],"objects":[{"x":1},{"x":2,"nested":{"y":3}}],"n":-42,"name":"lezac"})";
    const std::string actual = [&] {
        std::string value = normalized;
        for (size_t pos = 0; (pos = value.find("\\\"", pos)) != std::string::npos;) {
            value.erase(pos, 1);
            ++pos;
        }
        return value;
    }();

    const std::vector<std::string> rows = lezac::resources::extractStringArray(actual, "rows");
    if (rows != std::vector<std::string>({"aa", "bb"})) return 1;

    const std::vector<std::string> objects = lezac::resources::extractObjectArray(actual, "objects");
    if (objects.size() != 2 || objects[0] != R"({"x":1})".substr(0)) return 2;

    if (objects[0] != "{\"x\":1}" || objects[1] != "{\"x\":2,\"nested\":{\"y\":3}}") return 3;
    if (lezac::resources::extractInt(actual, "n", 7) != -42) return 4;
    if (lezac::resources::extractInt(actual, "missing", 7) != 7) return 5;
    if (lezac::resources::extractString(actual, "name", "fallback") != "lezac") return 6;
    if (lezac::resources::extractString(actual, "missing", "fallback") != "fallback") return 7;

    std::cout << "resource_json=ok rows=2 objects=2 int=-42 string=lezac fallbacks=2\n";
    return 0;
}
