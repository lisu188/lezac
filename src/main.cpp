#define main(...) lezac_app_main(__VA_ARGS__)
#include "app/app.cpp"
#undef main

int main(int argc, char** argv) {
    return lezac_app_main(argc, argv);
}
