#include "rendering/game_renderer.hpp"
#include "rendering/presentation_state.hpp"
#include "resources/asset_catalog.hpp"

#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <vector>

using namespace lezac;
namespace {
void require(bool value,const char* message){if(!value)throw std::runtime_error(message);}
struct Reader {
    std::vector<uint8_t> bytes;
    size_t at=0;
    uint32_t number(unsigned n) {
        require(n<=4 && at+n<=bytes.size(),"Ammunition renderer corpus truncated");
        uint32_t value=0;for(unsigned i=0;i<n;++i)value|=uint32_t{bytes[at++]}<<(i*8);return value;
    }
    void skip(size_t n){require(at+n<=bytes.size(),"Ammunition renderer corpus truncated");at+=n;}
};
void rgb(std::ofstream& out,uint32_t color){out.put(static_cast<char>(color>>16));out.put(static_cast<char>(color>>8));out.put(static_cast<char>(color));}
}
int main(int argc,char** argv) {
    try {
        require(argc==2 || argc==3,"Expected ammunition corpus and optional pixel dump");
        std::ifstream input(argv[1],std::ios::binary);require(input.good(),"Ammunition renderer corpus missing");
        Reader reader{{std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()}};
        for(char c:std::string("LZAMMO02"))require(reader.number(1)==static_cast<uint8_t>(c),"Ammunition renderer magic differs");
        require(reader.number(4)==2226,"Ammunition renderer domain differs");
        const auto assets=resources::AssetCatalog::load(resources::AssetFormat::Original);
        std::ofstream dump;
        if(argc==3){dump.open(argv[2],std::ios::binary);require(dump.good(),"Cannot write ammunition pixels");dump.write("LZAMPX01",8);
            for(const auto& color:assets.palette()){dump.put(static_cast<char>(color.r));dump.put(static_cast<char>(color.g));dump.put(static_cast<char>(color.b));}}
        unsigned cases=0,compared=0,spriteCases=0,spritePixels=0;
        for(unsigned index=0;index<2226;++index) {
            require(reader.number(4)==index,"Ammunition renderer index differs");const auto error=reader.number(4);
            std::array<uint16_t,13> entry{};for(auto& r:entry)r=static_cast<uint16_t>(reader.number(2));reader.skip(4+30);
            std::vector<uint8_t> memory(1048576);
            const auto seeds=reader.number(4);require(seeds<300,"Ammunition renderer seed count differs");
            for(unsigned seed=0;seed<seeds;++seed) {
                const auto at=reader.number(4),length=reader.number(4);
                require(uint64_t{at}+length<=memory.size() && reader.at+length<=reader.bytes.size(),"Ammunition seed exceeds memory");
                std::copy_n(reader.bytes.begin()+static_cast<std::ptrdiff_t>(reader.at),length,memory.begin()+at);reader.skip(length);
            }
            const auto states=reader.number(4);require(states<2000000,"Ammunition renderer trace count differs");reader.skip(size_t{states}*30);
            const auto writes=reader.number(4);require(writes<200000,"Ammunition renderer write count differs");
            for(unsigned write=0;write<writes;++write) {
                const auto at=reader.number(4),size=reader.number(1),value=reader.number(2);
                require((size==1 || size==2) && uint64_t{at}+size<=memory.size(),"Ammunition renderer write exceeds memory");
                memory[at]=static_cast<uint8_t>(value);if(size==2)memory[at+1]=static_cast<uint8_t>(value>>8);
            }
            if(index>=2186 && index<2218) {
                const auto descriptor=0x1aa20+0xc322+57*4;
                resources::Sprite sprite;sprite.width=memory[descriptor];sprite.height=memory[descriptor+1];
                const auto source=static_cast<uint16_t>(memory[descriptor+2]|(uint16_t{memory[descriptor+3]}<<8));
                for(unsigned offset=0;offset<static_cast<unsigned>(sprite.width*sprite.height);++offset)
                    sprite.pixels.push_back(memory[0x40000+static_cast<uint16_t>(source+offset)]);
                const auto background=memory[0x1aa20+0x79a3],ink=memory[0x1aa20+0x661e];
                rendering::Canvas canvas;canvas.indexedRect(64,64,sprite.width,sprite.height,17,0xff000000u);
                rendering::TextRenderer text(canvas,assets.palette(),assets.fontSprites());
                if(background==0 && ink==1)text.drawSprite(sprite,64,64);
                else text.drawSprite(sprite,64,64,background,ink);
                for(int y=0;y<sprite.height;++y)for(int x=0;x<sprite.width;++x) {
                    const auto at=static_cast<size_t>((64+y)*320+64+x);
                    require(canvas.indexedPixels()[at]==1 && canvas.paletteIndices()[at]==memory[0xa0000+at],
                        "Production sprite background/ink substitution differs from original");++spritePixels;
                }
                ++spriteCases;
            }
            if(index>=2048)continue;
            const auto player=index/1024,selected=index/256%4,ammo=index%256;
            const auto dirty=std::array<uint8_t,4>{0,1,2,255}[(ammo+player+1+selected)%4];
            if(dirty<=1)continue;
            require(error==0 && entry[12]==0x326e,"Normal ammunition entry differs");
            const auto spriteId=57+selected;
            const auto& sprite=assets.sprites().sprites.at(spriteId);
            require(std::equal(sprite.pixels.begin(),sprite.pixels.end(),memory.begin()+0x42000),"Original ammunition sprite input differs");
            require(std::find(sprite.pixels.begin(),sprite.pixels.end(),1)==sprite.pixels.end(),"Shipped ammunition sprite acquired ink-one pixels");
            for(unsigned digit=0;digit<10;++digit) {
                const auto* tile=assets.tiles().tile(121+static_cast<int>(digit));
                require(tile && std::equal(tile,tile+64,memory.begin()+0x23a20+digit*64),"Original ammunition digit input differs");
            }
            rendering::PresentationState presentation;presentation.setPalette(assets.palette());
            gameplay::BombInventory inventory;inventory.selected=static_cast<gameplay::BombType>(selected);
            inventory.counts.at(selected)=static_cast<int>(ammo);inventory.hudDirty=dirty;
            presentation.sampleHudInventory(player,inventory,1);
            const auto& panels=presentation.hudAmmoPanels();
            require(inventory.hudDirty==0 && panels[player].count==std::min(ammo,99u) &&
                panels[player].icon==inventory.selected && memory[0x1aa20+0x1b76+player]==0,"Original ammunition dirty/count state differs");
            rendering::Canvas canvas;rendering::TextRenderer text(canvas,presentation.palette(),assets.fontSprites());
            rendering::GameRenderer renderer(canvas,text,assets,presentation);
            rendering::HudView view{static_cast<int>(player+1),{{{{},0,0,panels[0]},{{},0,0,panels[1]}}},108,1,50,0,0,false,false};
            view.columnReady[player]=true;view.spriteInk=memory[0x1aa20+0x661e];renderer.drawHud(view);
            const unsigned x=121+player*180,y=163;
            std::vector<size_t> positions;
            for(unsigned row=0;row<16;++row)for(unsigned column=0;column<16;++column)positions.push_back((y+row)*320+x+column);
            for(unsigned digit=0;digit<2;++digit)for(unsigned row=0;row<8;++row)for(unsigned column=0;column<8;++column)
                positions.push_back((y+19+row)*320+x-1+digit*9+column);
            for(auto at:positions) {
                if(canvas.indexedPixels()[at]!=1 || canvas.paletteIndices()[at]!=memory[0xa0000+at]) {
                    std::cerr<<"case="<<index<<" pixel="<<at<<" actual="<<unsigned(canvas.paletteIndices()[at])
                        <<" expected="<<unsigned(memory[0xa0000+at])<<'\n';
                    throw std::runtime_error("Production ammunition HUD differs from original call");
                }
                ++compared;
            }
            if(dump.is_open() && (ammo==0 || ammo==1 || ammo==99 || ammo==255)) {
                dump.put(static_cast<char>(player));dump.put(static_cast<char>(selected));dump.put(static_cast<char>(ammo));
                for(auto at:positions)dump.put(static_cast<char>(memory[0xa0000+at]));
                for(auto at:positions)rgb(dump,canvas.pixels()[at]);
            }
            ++cases;
        }
        require(reader.at==reader.bytes.size(),"Ammunition renderer corpus tail differs");
        if(dump.is_open()){dump.flush();require(dump.good(),"Ammunition pixel dump failed");}
        std::cout<<"ammo_hud_renderer=ok cases="<<cases<<" indexed_pixels="<<compared
            <<" sprite_cases="<<spriteCases<<" sprite_pixels="<<spritePixels<<" original_call_timing=0 whole_game_parity=0\n";
        return 0;
    } catch(const std::exception& error){std::cerr<<"ammo_hud_renderer=failed "<<error.what()<<'\n';return 1;}
}
