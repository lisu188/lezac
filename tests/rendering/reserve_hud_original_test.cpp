#include "rendering/game_renderer.hpp"
#include "rendering/presentation_state.hpp"
#include "resources/asset_catalog.hpp"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

using namespace lezac;
namespace {
void require(bool value,const char* message) { if(!value)throw std::runtime_error(message); }
struct Reader {
    std::vector<uint8_t> bytes;
    size_t at=0;
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Reserve renderer corpus truncated");
        uint32_t result=0;for(unsigned i=0;i<n;++i)result|=uint32_t{bytes[at++]}<<(8*i);return result;
    }
    void skip(size_t n) {require(at+n<=bytes.size(),"Reserve renderer corpus truncated");at+=n;}
};
void putColor(std::ofstream& out,uint32_t color) {
    out.put(static_cast<char>(color>>16));out.put(static_cast<char>(color>>8));out.put(static_cast<char>(color));
}
}
int main(int argc,char** argv) {
    try {
        require(argc==2 || argc==3,"Expected reserve corpus and optional pixel dump");
        std::ifstream input(argv[1],std::ios::binary);require(input.good(),"Reserve corpus missing");
        Reader reader{{std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()}};
        for(char c:std::string("LZRSHD01"))require(reader.number(1)==static_cast<uint8_t>(c),"Reserve corpus magic differs");
        require(reader.number(4)==756,"Reserve corpus domain differs");
        const auto assets=resources::AssetCatalog::load(resources::AssetFormat::Original);
        std::ofstream dump;
        if(argc==3) {
            dump.open(argv[2],std::ios::binary);require(dump.good(),"Cannot write reserve pixel dump");
            dump.write("LZRHPIX1",8);
        }
        unsigned cases=0,compared=0,clearPixels=0,sentinelCases=0,sentinelPixels=0;
        for(unsigned index=0;index<756;++index) {
            require(reader.number(4)==index,"Reserve renderer case index differs");
            const auto error=reader.number(4);reader.skip(60);
            std::vector<uint8_t> memory(1048576);
            const auto seeds=reader.number(4);require(seeds<300,"Reserve renderer seed count differs");
            for(unsigned seed=0;seed<seeds;++seed) {
                const auto at=reader.number(4),length=reader.number(4);
                require(uint64_t{at}+length<=memory.size() && reader.at+length<=reader.bytes.size(),"Reserve seed exceeds memory");
                std::copy_n(reader.bytes.begin()+static_cast<std::ptrdiff_t>(reader.at),length,memory.begin()+at);reader.skip(length);
            }
            const auto word=[&](size_t at){return static_cast<uint16_t>(memory[at]|(uint16_t{memory[at+1]}<<8));};
            if(index<512) {
                const auto base=word(0x1aa20+0xc208);
                for(unsigned tile:{0u,115u}) {
                    const auto* pixels=assets.tiles().tile(static_cast<int>(tile));
                    require(pixels && std::equal(pixels,pixels+64,memory.begin()+0x1aa20+base+tile*64),
                        "Live reserve glyphs differ from original input atlas");
                }
            }
            const auto states=reader.number(4);require(states<10000,"Reserve renderer trace count differs");reader.skip(size_t{states}*30);
            const auto writes=reader.number(4);require(writes<1000,"Reserve renderer write count differs");
            for(unsigned write=0;write<writes;++write) {
                const auto at=reader.number(4),size=reader.number(1),value=reader.number(2);
                require((size==1 || size==2) && uint64_t{at}+size<=memory.size(),"Reserve renderer write exceeds memory");
                memory[at]=static_cast<uint8_t>(value);if(size==2)memory[at+1]=static_cast<uint8_t>(value>>8);
            }
            if(index>=512)continue;
            require(error==0,"Normal reserve case reached runtime error");
            const auto player=index/256,reserve=index%256;
            const int xoff=player==0?0:180;
            require(word(0x1aa20+0x79f4+player*2)==xoff,"Original reserve column differs");
            rendering::PresentationState presentation;presentation.setPalette(assets.palette());
            rendering::Canvas canvas;
            rendering::TextRenderer text(canvas,presentation.palette(),assets.fontSprites());
            rendering::GameRenderer renderer(canvas,text,assets,presentation);
            const rendering::HudAmmoPanel ammo;
            rendering::HudView view{static_cast<int>(player+1),{{{{},0,0,ammo},{{},0,0,ammo}}},108,1,50,0,0,false,false};
            view.players[player].lives=static_cast<int>(reserve);
            renderer.drawHud(view);
            for(unsigned slot=0;slot<3;++slot)for(unsigned row=0;row<8;++row)for(unsigned x=0;x<8;++x) {
                const auto at=(192+row)*320+static_cast<unsigned>(xoff)+slot*9+x;
                if(canvas.indexedPixels()[at]!=1 || canvas.paletteIndices()[at]!=memory[0xa0000+at]) {
                    std::cerr<<"case="<<index<<" slot="<<slot<<" row="<<row<<" x="<<x<<'\n';
                    throw std::runtime_error("Production reserve slot differs from original opaque blit");
                }
                ++compared;
            }
            for(unsigned row=0;row<8;++row)for(unsigned x=27;x<54;++x) {
                require(canvas.pixels()[(192+row)*320+static_cast<unsigned>(xoff)+x]==0xff000000u,
                    "Production HUD painted a fourth reserve slot");++clearPixels;
            }
            if(dump.is_open() && (reserve<4 || reserve==6 || reserve==255)) {
                dump.put(static_cast<char>(player));dump.put(static_cast<char>(reserve));
                for(unsigned row=0;row<8;++row)for(unsigned x=0;x<54;++x) {
                    const auto at=(192+row)*320+static_cast<unsigned>(xoff)+x;
                    const auto color=presentation.palette()[memory[0xa0000+at]];
                    putColor(dump,0xff000000u|(uint32_t{color.r}<<16)|(uint32_t{color.g}<<8)|color.b);
                }
                for(unsigned row=0;row<8;++row)for(unsigned x=0;x<54;++x)
                    putColor(dump,canvas.pixels()[(192+row)*320+static_cast<unsigned>(xoff)+x]);
            }
            if(reserve==255) {
                view.players[player].lives=-1;
                renderer.drawHud(view);
                for(unsigned slot=0;slot<3;++slot)for(unsigned row=0;row<8;++row)for(unsigned x=0;x<8;++x) {
                    const auto at=(192+row)*320+static_cast<unsigned>(xoff)+slot*9+x;
                    require(canvas.indexedPixels()[at]==1 && canvas.paletteIndices()[at]==memory[0xa0000+at],
                        "Production eliminated-player sentinel differs from original reserve byte 255");
                    ++sentinelPixels;
                }
                ++sentinelCases;
            }
            ++cases;
        }
        require(reader.at==reader.bytes.size(),"Reserve renderer corpus tail differs");
        require(sentinelCases==2 && sentinelPixels==384,"Reserve sentinel coverage differs");
        if(dump.is_open()){dump.flush();require(dump.good(),"Reserve pixel dump failed");}
        std::cout<<"reserve_hud_renderer=ok cases="<<cases<<" indexed_pixels="<<compared
            <<" no_extra_slot_pixels="<<clearPixels<<" original_call_timing=0 whole_game_parity=0"
            <<" sentinel_cases="<<sentinelCases<<" sentinel_pixels="<<sentinelPixels<<'\n';
        return 0;
    } catch(const std::exception& error) {
        std::cerr<<"reserve_hud_renderer=failed "<<error.what()<<'\n';return 1;
    }
}
