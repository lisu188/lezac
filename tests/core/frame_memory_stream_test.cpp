#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static std::vector<unsigned char> memory(1048576,0x5a);
static unsigned char* MemBase=memory.data();
static struct {unsigned call=1;} lezac_dos_time_probe;
static bool LezacReadFrameVga(unsigned char* out) {
    for(unsigned i=0;i<65536;++i) out[i]=static_cast<unsigned char>(i);
    return true;
}
#include "../../tools/frame_iteration_live_probe/memory_stream.h"

int main(int argc,char** argv) {
    if(argc!=2) return 2;
    if(std::strcmp(argv[1],"pair")==0)
        return LezacStreamMemory("initial") && LezacStreamMemory("final") ? 0 : 1;
    return LezacStreamMemory(argv[1]) ? 0 : 1;
}
