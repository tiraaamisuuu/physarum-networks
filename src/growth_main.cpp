#include "physarum/GrowthModel.hpp"
#include <algorithm>
#include <bit>
#include <charconv>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {
template<class T>T number(const std::string& s) {
    T value{};const auto [end,error]=std::from_chars(s.data(),s.data()+s.size(),value);
    if(error!=std::errc{} || end!=s.data()+s.size())throw std::invalid_argument("Invalid growth number: "+s);
    return value;
}
std::map<std::string,std::string> config(const std::filesystem::path& path) {
    std::ifstream in(path);if(!in)throw std::invalid_argument("Cannot read growth config");
    std::map<std::string,std::string> values;std::string line;
    while(std::getline(in,line)) {
        const auto equal=line.find('=');
        if(equal==std::string::npos || !values.emplace(line.substr(0,equal),line.substr(equal+1)).second)
            throw std::invalid_argument("Growth config requires unique key=value lines");
    }
    return values;
}
template<class T>std::vector<T> binary(const std::filesystem::path& path,std::size_t count) {
    std::ifstream in(path,std::ios::binary|std::ios::ate);
    if(!in || in.tellg()!=static_cast<std::streamoff>(count*sizeof(T)))throw std::invalid_argument("Invalid growth mask size: "+path.string());
    in.seekg(0);std::vector<T> values(count);in.read(reinterpret_cast<char*>(values.data()),static_cast<std::streamsize>(count*sizeof(T)));
    if(!in)throw std::invalid_argument("Cannot read growth mask");return values;
}
std::ofstream output(const std::filesystem::path& path,bool binary=false) {
    std::ofstream out(path,binary?(std::ios::out|std::ios::binary):std::ios::out);
    out.exceptions(std::ios::failbit|std::ios::badbit);out<<std::setprecision(17);return out;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=4)throw std::invalid_argument("Usage: physarum_growth CONFIG INPUT_DIRECTORY OUTPUT_DIRECTORY");
        static_assert(std::endian::native==std::endian::little && sizeof(float)==4);
        auto c=config(argv[1]);physarum::GrowthParameters p;
        if(c.size()!=19)throw std::invalid_argument("Growth config requires exactly 19 keys");
        p.width=number<int>(c.at("width"));p.height=number<int>(c.at("height"));
        p.seed_count=number<int>(c.at("seed_count"));p.max_agents=number<int>(c.at("max_agents"));
        p.division_interval=number<int>(c.at("division_interval"));p.seed=number<std::uint32_t>(c.at("seed"));
        p.initial_x=number<double>(c.at("initial_x"));p.initial_y=number<double>(c.at("initial_y"));
        p.seed_radius=number<double>(c.at("seed_radius"));p.sensor_distance=number<double>(c.at("sensor_distance"));
        p.sensor_angle=number<double>(c.at("sensor_angle"));p.turn_angle=number<double>(c.at("turn_angle"));
        p.decay=number<double>(c.at("decay"));p.food_strength=number<double>(c.at("food_strength"));p.food_range=number<double>(c.at("food_range"));
        p.river_aversion=number<double>(c.at("river_aversion"));
        const int steps=number<int>(c.at("steps")),every=number<int>(c.at("frame_every"));
        if(c.at("schema_version")!="1" || steps<1 || steps>4000 || every<1 || every>100 || steps%every!=0)
            throw std::invalid_argument("Require 1..4000 steps divisible by frame_every (1..100), schema 1");
        if(p.width<32 || p.width>800 || p.height<32 || p.height>600)throw std::invalid_argument("Growth grid outside supported bounds");
        const std::filesystem::path input=argv[2],dir=argv[3];
        const auto count=static_cast<std::size_t>(p.width*p.height);
        auto mask=binary<std::uint8_t>(input/"blocked.bin",count);auto river=binary<float>(input/"river.bin",count);
        std::ifstream foods(input/"food.csv");std::string line;
        if(!std::getline(foods,line) || line!="food,x,y")throw std::invalid_argument("Expected food,x,y CSV header");
        std::vector<physarum::FoodSite> sites;
        while(std::getline(foods,line)) {
            std::istringstream row(line);std::string id,x,y,extra;
            if(!std::getline(row,id,',') || !std::getline(row,x,',') || !std::getline(row,y,',') || std::getline(row,extra,',') || number<std::size_t>(id)!=sites.size())
                throw std::invalid_argument("Invalid food CSV row");
            sites.push_back({number<double>(x),number<double>(y)});
        }
        physarum::GrowthModel model(p,std::move(sites),std::move(mask),std::move(river));
        std::filesystem::create_directories(dir);
        auto trail=output(dir/"trail.f32",true),occupied=output(dir/"occupied.u8",true),stats=output(dir/"stats.csv");
        stats<<"frame,step,agents,food_reached,occupied_cells,trail_mass,births,deaths\n";
        for(int step=0;step<=steps;++step) {
            if(step%every==0) {
                const auto& field=model.trail();
                trail.write(reinterpret_cast<const char*>(field.data()),static_cast<std::streamsize>(field.size()*sizeof(float)));
                std::vector<std::uint8_t> density;density.reserve(count);
                for(int cell:model.occupancy())density.push_back(static_cast<std::uint8_t>(cell));
                occupied.write(reinterpret_cast<const char*>(density.data()),static_cast<std::streamsize>(density.size()));
                const auto reached=std::count_if(model.first_contact().begin(),model.first_contact().end(),[](int value){return value>=0;});
                stats<<step/every<<','<<step<<','<<model.agents().size()<<','<<reached<<','<<std::accumulate(density.begin(),density.end(),0)<<','
                     <<std::accumulate(field.begin(),field.end(),0.)<<','<<model.births()<<','<<model.deaths()<<'\n';
            }
            if(step<steps)model.step();
        }
        auto contacts=output(dir/"food.csv");contacts<<"food,first_contact_step\n";
        for(std::size_t i=0;i<model.first_contact().size();++i)contacts<<i<<','<<model.first_contact()[i]<<'\n';
        auto meta=output(dir/"metadata.txt");meta<<"model=chemotactic_particles_with_growth_v1\ncompiler="<<__VERSION__
            <<"\nrandom=xorshift32\nfloat_layout=IEEE754_float32_little_endian\nboundary=reflecting\nflow_solver=not_used\n";
        trail.close();occupied.close();stats.close();contacts.close();meta.close();
        std::cout<<"Completed "<<steps<<" updates; "<<model.agents().size()<<" live particles\n";
    } catch(const std::exception& error) { std::cerr<<"Error: "<<error.what()<<'\n';return 1; }
}
