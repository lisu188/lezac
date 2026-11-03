#include <cxxabi.h>
#include <dlfcn.h>
#include <csignal>
#include <cstring>
#include <stdexcept>
#include <typeinfo>
#include <unistd.h>

// Diagnostic interposition only: stop before unwinding an actual ownership throw.
extern "C" [[noreturn]] void __cxa_throw(void* object,std::type_info* type,void (*destroy)(void*)) {
    using Throw=void (*)(void*,std::type_info*,void (*)(void*));
    static const auto original=reinterpret_cast<Throw>(dlsym(RTLD_NEXT,"__cxa_throw"));
    if(!original) _exit(125);
    if(type && std::strcmp(type->name(),"St16invalid_argument")==0) {
        const auto* exception=static_cast<const std::invalid_argument*>(object);
        const char* message=exception->what();
        if(std::strncmp(message,"Frame actor",11)==0 || std::strncmp(message,"Actor ",6)==0) {
            constexpr char marker[]="LEZAC_THROW_STOP:";
            const size_t length=strnlen(message,160);
            if(write(2,marker,sizeof(marker)-1)!=sizeof(marker)-1 ||
               write(2,message,length)!=static_cast<ssize_t>(length) || write(2,"\n",1)!=1) _exit(126);
            raise(SIGSTOP);
        }
    }
    original(object,type,destroy);
    __builtin_unreachable();
}
