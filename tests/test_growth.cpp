#include "physarum/GrowthModel.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <string>

namespace {
void require(bool condition,const std::string& message) { if(!condition)throw std::runtime_error(message); }
void near(double value,double expected,double tolerance=1e-6) { require(std::isfinite(value) && std::abs(value-expected)<=tolerance,"Numerical mismatch"); }
template<class F>void throws(F action) { bool caught=false;try{action();}catch(const std::exception&){caught=true;}require(caught,"Expected rejection"); }
physarum::GrowthParameters parameters() {
    physarum::GrowthParameters p;p.width=64;p.height=64;p.initial_x=16;p.initial_y=32;p.seed_radius=6;p.seed_count=25;p.max_agents=300;return p;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=2)throw std::invalid_argument("Specify growth test");
        const std::string name=argv[1];
        if(name=="diffusion") {
            std::vector<float> input(25,0),out;std::vector<std::uint8_t> mask(25,0);input[12]=9;
            physarum::diffuse_growth_trail(input,out,mask,5,5,0);
            for(int y=0;y<5;++y)for(int x=0;x<5;++x)near(out[static_cast<std::size_t>(y*5+x)],(x>=1&&x<=3&&y>=1&&y<=3)?1:0);
            // Reflecting corner: mass is preserved before decay, not lost off-grid.
            input.assign(25,0);input[0]=9;physarum::diffuse_growth_trail(input,out,mask,5,5,.1);
            near(std::accumulate(out.begin(),out.end(),0.),8.1);
            near(out[0],5.4);near(out[1],.9);near(out[5],.9);near(out[6],.9);
            throws([&]{physarum::diffuse_growth_trail(input,input,mask,5,5,.1);});
        } else if(name=="determinism") {
            const auto p=parameters();const std::vector<physarum::FoodSite> foods{{16,32},{50,32}};
            physarum::GrowthModel a(p,foods),b(p,foods);
            require(a.first_contact()[0]==0 && a.first_contact()[1]==-1,"Only initial local food contacted");
            require(a.agents().size()==25,"Exact inoculum size");
            for(const auto& particle:a.agents())require(std::hypot(particle.x-p.initial_x,particle.y-p.initial_y)<=6,"Local inoculum");
            for(int step=0;step<120;++step){a.step();b.step();}
            require(a.trail()==b.trail() && a.occupancy()==b.occupancy() && a.first_contact()==b.first_contact(),"Repeat seeded evolution");
            require(a.agents().size()==p.seed_count+a.births()-a.deaths(),"Population accounting");
            auto changed=p;++changed.seed;physarum::GrowthModel c(changed,foods);
            require(c.trail()!=physarum::GrowthModel(p,foods).trail(),"Seed changes initial state");
        } else if(name=="barrier") {
            const auto p=parameters();std::vector<std::uint8_t> mask(64*64,0);
            for(int y=0;y<64;++y)mask[static_cast<std::size_t>(y*64+32)]=1;
            physarum::GrowthModel model(p,{{16,32},{50,32}},mask);
            for(int step=0;step<180;++step) {
                model.step();
                require(model.agents().size()<=300,"Population cap");
                require(std::accumulate(model.occupancy().begin(),model.occupancy().end(),0)==static_cast<int>(model.agents().size()),"No duplicate occupancy");
                for(const auto& a:model.agents())require(a.x>=0 && a.x<32 && a.y>=0 && a.y<64,"Cannot cross barrier or arena");
                for(int y=0;y<64;++y)for(int x=32;x<64;++x)near(model.trail()[static_cast<std::size_t>(y*64+x)],0,0);
            }
            require(model.first_contact()[1]==-1,"Food cue cannot count as contact or teleport an agent");
        } else if(name=="food_recovery") {
            auto p=parameters();p.seed_count=1;p.max_agents=1;p.seed_radius=2;p.food_strength=0;
            physarum::GrowthModel model(p,{{16,32},{50,32}});
            require(model.first_contact()[0]==0,"Starting food visited");
            near(model.food_weights()[0],.05,1e-7);
            bool left=false;
            for(int step=0;step<150;++step) {
                model.step();
                if(model.iteration()%10==0) {
                    const bool covered=model.food_activity()[0]>0;
                    near(model.food_weights()[0],covered?.05:1.,1e-7);
                    if(!covered) {
                        left=true;require(model.first_contact()[0]==0,"History remains visited while cue recovers");
                    }
                }
            }
            require(left,"Particle left its starting food; recovery was exercised");
        } else if(name=="invalid") {
            auto p=parameters();p.decay=std::numeric_limits<double>::quiet_NaN();throws([&]{physarum::GrowthModel m(p,{{16,32}});});
            p=parameters();p.initial_x=-1;throws([&]{physarum::GrowthModel m(p,{{16,32}});});
            p=parameters();std::vector<float> bad(4096,-1);throws([&]{physarum::GrowthModel m(p,{{16,32}},{},bad);});
            p.max_agents=1;throws([&]{physarum::GrowthModel m(p,{{16,32}});});
        } else throw std::invalid_argument("Unknown growth test");
        std::cout<<"PASS growth_"<<name<<'\n';
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
