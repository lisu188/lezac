#include <cstddef>
#include <iostream>
#include <sys/user.h>

int main() {
    static_assert(sizeof(void*)==8 && sizeof(user_regs_struct)==216);
    static_assert(offsetof(user,u_debugreg)==848);
    std::cout<<"{\"debug_offset\":"<<offsetof(user,u_debugreg)
        <<",\"register_bytes\":"<<sizeof(user_regs_struct)<<",\"word_bytes\":"<<sizeof(unsigned long)<<"}\n";
}
