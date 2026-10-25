#include "gameplay/actor_slots.hpp"

#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <string>

using namespace lezac;
namespace {
void require(bool yes,const char* message) { if (!yes) throw std::runtime_error(message); }
std::vector<uint8_t> read(const std::string& path) {
    std::ifstream input(path,std::ios::binary);
    require(input.good(),"Missing GRAN group input");
    return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
}
struct Reader {
    std::vector<uint8_t> bytes;
    size_t at=0;
    uint32_t number(unsigned count) {
        require(at+count<=bytes.size(),"Truncated GRAN fixture");
        uint32_t result=0;
        for (unsigned i=0;i<count;++i) result|=uint32_t{bytes[at++]}<<(8*i);
        return result;
    }
    gameplay::ActorStorage::State state() {
        gameplay::ActorStorage::State result;
        for (auto& row : result.actors) for (auto& value : row) value=static_cast<uint8_t>(number(1));
        for (auto& row : result.visuals) for (auto& value : row) value=static_cast<uint8_t>(number(1));
        for (auto& row : result.links) for (auto& value : row) value=static_cast<uint8_t>(number(1));
        result.count=static_cast<uint8_t>(number(1));result.visualCount=static_cast<uint8_t>(number(1));
        require(number(1)==result.links[0][15],"GRAN link-count alias differs");
        result.success=static_cast<uint16_t>(number(2));
        return result;
    }
};
std::vector<uint8_t> project(const gameplay::ActorStorage::State& state) {
    std::vector<uint8_t> output;
    for (const auto& row : state.actors) output.insert(output.end(),row.begin(),row.end());
    for (const auto& row : state.visuals) output.insert(output.end(),row.begin(),row.end());
    for (const auto& row : state.links) output.insert(output.end(),row.begin(),row.end());
    output.insert(output.end(),{state.count,state.visualCount,state.links[0][15],
        static_cast<uint8_t>(state.success),static_cast<uint8_t>(state.success>>8)});
    return output;
}
template<class Function> void rejected(Function action) {
    bool threw=false;
    try { action(); } catch (const std::exception&) { threw=true; }
    require(threw,"Invalid GRAN operation was accepted");
}
template<class DescriptorLookup,class AnimationRange>
void rejectionControls(const std::vector<uint8_t>& gran,const gameplay::GranGroup& group,
        const gameplay::ActorStorage::State& initial,const DescriptorLookup& descriptor,
        const AnimationRange& animation) {
    rejected([] { gameplay::GranGroup invalid(std::vector<uint8_t>{}); });
    auto altered=gran;altered.pop_back();
    rejected([&] { gameplay::GranGroup invalid(altered); });
    altered=gran;altered.push_back(0);
    rejected([&] { gameplay::GranGroup invalid(altered); });
    altered=gran;altered[40]=altered[2];
    rejected([&] { gameplay::GranGroup invalid(altered); });
    altered=gran;altered[2]=7;
    rejected([&] { gameplay::GranGroup invalid(altered); });
    for (unsigned fault=0;fault<5;++fault) {
        auto state=initial;
        if (fault==0) { state.count=24;state.visualCount=26; }
        if (fault==1) state.visualCount=1;
        if (fault==2) state.links[0][15]=2;
        const auto before=project(state);
        unsigned callbacks=0;
        const auto image=[&](uint8_t index) {
            if (fault==3 && ++callbacks==3) throw std::runtime_error("Descriptor lookup failure");
            return descriptor(index);
        };
        const auto range=[&](uint8_t index) {
            if (fault==4 && ++callbacks==2) throw std::runtime_error("Animation lookup failure");
            return animation(index);
        };
        rejected([&] { group.append(state,0,0,image,range); });
        require(project(state)==before,"Failed GRAN append changed physical storage");
    }
    gameplay::ActorSlots slots;
    auto state=initial;state.count=1;state.visualCount=3;state.actors[1][1]=2;
    std::array<uint64_t,gameplay::ActorStorage::capacity+1> orders{};
    orders[1]=1003;
    slots.restoreForFixture(state,orders);
    for (const auto identity : {uint64_t{0},std::numeric_limits<uint64_t>::max(),uint64_t{1000}}) {
        rejected([&] { slots.appendGranGroup(identity,group,0,0,descriptor,animation); });
        require(project(slots.state())==project(state) && slots.order(1)==1003,
            "Failed GRAN identity binding changed existing ownership");
    }
    rejected([&] { slots.appendGranGroup(2000,group,0,0,descriptor,[](uint8_t)->std::array<uint8_t,2> {
        throw std::runtime_error("Animation lookup failure");
    }); });
    require(project(slots.state())==project(state) && slots.order(1)==1003,
        "Callback failure changed existing ownership");
    slots.appendGranGroup(2000,group,0,0,descriptor,animation);
    const auto before=slots.state();
    rejected([&] { slots.writeLinkMotion(0,0,0,0); });
    rejected([&] { slots.writeLinkMotion(7,0,0,0); });
    require(project(slots.state())==project(before),"Invalid link update changed storage");
    auto expected=before;
    slots.writeLinkMotion(1,77,-32768,32767);
    expected.links[1][6]=77;expected.links[1][11]=0;expected.links[1][12]=128;
    expected.links[1][13]=255;expected.links[1][14]=127;
    require(project(slots.state())==project(expected),"Link update changed opaque fields");
    const auto actor=slots.find(2000);
    slots.writeBossDamage(2000,9,2,{31,7,0x34,0x12});
    expected.actors[actor][36]=9;expected.actors[actor][2]=2;expected.actors[actor][20]=9;
    auto& row=expected.visuals[expected.actors[actor][1]];
    row[4]=31;row[5]=7;row[6]=0x34;row[7]=0x12;
    require(project(slots.state())==project(expected),"Boss damage changed opaque fields");
    slots.enterBossDebris(2000,81);
    expected.actors[actor][0]=14;expected.actors[actor][2]=81;
    expected.actors[actor][21]=2;expected.actors[actor][27]=0;
    require(project(slots.state())==project(expected),"Boss debris conversion changed opaque fields");
}
}
int main(int argc,char** argv) {
    try {
        require(argc==3,"Expected GRAN original fixture and source root");
        const std::string root=argv[2];
        const auto gran=read(root+"/GRAN.MST"),exe=read(root+"/LEZAC.EXE");
        gameplay::GranGroup group(gran);
        Reader sprites{read(root+"/PROVA.SPR")};
        const auto count=sprites.number(1);
        std::vector<gameplay::ActorStorage::Descriptor> descriptors(1);
        uint32_t offset=0;
        for (uint32_t i=0;i<count;++i) {
            const auto width=sprites.number(1),height=sprites.number(1);
            descriptors.push_back({static_cast<uint8_t>(width),static_cast<uint8_t>(height),
                static_cast<uint8_t>(offset),static_cast<uint8_t>(offset>>8)});
            const size_t pixelCount=static_cast<size_t>(width)*height;
            require(pixelCount<=sprites.bytes.size()-sprites.at,"Truncated boss sprite");
            sprites.at+=pixelCount;offset+=static_cast<uint32_t>(pixelCount);
        }
        require(sprites.at==sprites.bytes.size() && offset<65536,"Boss sprite bank shape differs");
        const auto descriptor=[&](uint8_t index) { return descriptors.at(index); };
        const auto animation=[&](uint8_t index) {
            const size_t at=0x770+0xaa20+0x58+index*2u;
            require(at+1<exe.size(),"Animation table exceeds original executable");
            return std::array<uint8_t,2>{exe[at],exe[at+1]};
        };
        Reader input{read(argv[1])};
        for (char c : std::string("LZGRAN01")) require(input.number(1)==static_cast<uint8_t>(c),"GRAN fixture magic differs");
        require(input.number(4)==24,"GRAN fixture case count differs");
        uint64_t bytes=0;
        for (unsigned index=0;index<24;++index) {
            require(input.number(4)==index,"GRAN fixture index differs");
            const auto actors=input.number(2),links=input.number(2);
            const auto x=static_cast<uint16_t>(input.number(2)),y=static_cast<uint16_t>(input.number(2));
            auto actual=input.state();
            const auto before=actual;
            const auto expected=input.state();
            if (index==0) rejectionControls(gran,group,before,descriptor,animation);
            require(actual.count==actors && actual.links[0][15]==links,"GRAN initial counts differ");
            group.append(actual,std::bit_cast<int16_t>(x),std::bit_cast<int16_t>(y),descriptor,animation);
            const auto left=project(actual),right=project(expected);
            if (left!=right) {
                const auto at=static_cast<size_t>(std::mismatch(left.begin(),left.end(),right.begin()).first-left.begin());
                std::cerr << "case=" << index << " byte=" << at << " actual=" << unsigned{left[at]} << " expected=" << unsigned{right[at]} << '\n';
                throw std::runtime_error("Physical GRAN loader differs from original");
            }
            bytes+=left.size();
            gameplay::ActorSlots slots;
            std::array<uint64_t,gameplay::ActorStorage::capacity+1> orders{};
            for (size_t slot=1;slot<=actors;++slot) orders[slot]=100+slot;
            slots.restoreForFixture(before,orders);
            const uint64_t firstOrder=1000+index*10;
            slots.appendGranGroup(firstOrder,group,std::bit_cast<int16_t>(x),std::bit_cast<int16_t>(y),descriptor,animation);
            require(project(slots.state())==right,"Production GRAN owner wrapper differs from original");
            for (size_t slot=1;slot<=actors;++slot) require(slots.order(slot)==orders[slot],"GRAN changed old actor identity");
            for (size_t i=0;i<group.actorCount();++i)
                require(slots.order(actors+i+1)==firstOrder+i && slots.find(firstOrder+i)==actors+i+1,"GRAN identity binding differs");
            bytes+=right.size();
        }
        require(input.at==input.bytes.size(),"GRAN fixture has trailing bytes");
        std::cout << "gran_group_original=ok cases=24 complete_storage_bytes=" << bytes
            << " preserved_inactive_tail=1 owner_bindings=24 original_DOS_device_modeled=1 actual_App_integration=0 whole_game_parity=0\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "gran_group=failed " << error.what() << '\n';
        return 1;
    }
}
