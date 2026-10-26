#pragma once
#include <cerrno>
#include <climits>
#include <sys/socket.h>
#include <unistd.h>

inline bool LezacStreamMemory(const char* phase) {
    const char* value=std::getenv("LEZAC_ACTIVE_MEMORY_FD");
    if (!value || std::getenv("LEZAC_ACTIVE_MEMORY_PREFIX")) return false;
    char* end=0;errno=0;
    const long descriptor=std::strtol(value,&end,10);
    if (errno || !*value || *end || descriptor<3 || descriptor>INT_MAX) return false;
    const int fd=static_cast<int>(descriptor);
    int type=0;socklen_t length=sizeof(type);
    sockaddr_storage address={};socklen_t addressLength=sizeof(address);
    if (getsockopt(fd,SOL_SOCKET,SO_TYPE,&type,&length) || type!=SOCK_STREAM ||
            getsockname(fd,reinterpret_cast<sockaddr*>(&address),&addressLength) || address.ss_family!=AF_UNIX)
        return false;
    const bool initial=std::strcmp(phase,"initial")==0;
    if (!initial && std::strcmp(phase,"final")) return false;
    std::vector<unsigned char> bytes(MemBase,MemBase+1048576);
    if (!LezacReadFrameVga(bytes.data()+0xa0000)) return false;
    unsigned char header[20]={'L','Z','M','E','M','S','0','1',0,0,0,0,0,0,0,0,0,0,16,0};
    const unsigned call=lezac_dos_time_probe.call;
    for (unsigned i=0;i<4;++i) header[8+i]=static_cast<unsigned char>(call>>(8*i));
    header[12]=initial?0:1;
    const auto sendAll=[fd](const unsigned char* data,size_t size) {
        while (size) {
            const ssize_t sent=send(fd,data,size,MSG_NOSIGNAL);
            if (sent<0 && errno==EINTR) continue;
            if (sent<=0) return false;
            data+=sent;size-=static_cast<size_t>(sent);
        }
        return true;
    };
    return sendAll(header,sizeof(header)) && sendAll(bytes.data(),bytes.size());
}
