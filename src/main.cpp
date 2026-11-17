#include "physarum/PhysarumModel.hpp"
#include <Eigen/Core>
#include <charconv>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {
std::string trim(const std::string& s) {
    const auto a=s.find_first_not_of(" \t\r\n");
    return a==std::string::npos ? "" : s.substr(a,s.find_last_not_of(" \t\r\n")-a+1);
}
template<class T> T number(const std::string& text) {
    T value{};
    auto [end,error]=std::from_chars(text.data(),text.data()+text.size(),value);
    if (error!=std::errc{} || end!=text.data()+text.size()) throw std::invalid_argument("Invalid number: "+text);
    return value;
}
std::map<std::string,std::string> read_config(const std::filesystem::path& path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("Cannot open config: "+path.string());
    std::map<std::string,std::string> c;
    std::string line;
    while (std::getline(in,line)) {
        line=trim(line.substr(0,line.find('#')));
        if (line.empty()) continue;
        const auto pos=line.find('=');
        if (pos==std::string::npos) throw std::invalid_argument("Expected key=value: "+line);
        auto key=trim(line.substr(0,pos)), value=trim(line.substr(pos+1));
        if (key.empty() || value.empty() || !c.emplace(key,value).second)
            throw std::invalid_argument("Empty or duplicate config entry: "+line);
    }
    for (auto key:{"dt","steps","gamma","current","initial_conductivity","source","sink"})
        if (!c.contains(key)) throw std::invalid_argument(std::string("Missing config key: ")+key);
    if (c.size()!=7) throw std::invalid_argument("Unknown config key");
    return c;
}
std::ofstream output(const std::filesystem::path& path) {
    std::ofstream f(path); f.exceptions(std::ios::failbit|std::ios::badbit); f<<std::setprecision(17); return f;
}
}
int main(int argc,char** argv) {
    try {
        if (argc==2 && std::string(argv[1])=="--help") {
            std::cout<<"Usage: physarum_run CONFIG OUTPUT_DIRECTORY\nFixed four-node, two-route Phase 1 experiment.\n"; return 0;
        }
        if (argc!=3) throw std::invalid_argument("Usage: physarum_run CONFIG OUTPUT_DIRECTORY");
        const auto c=read_config(argv[1]);
        physarum::Parameters p;
        p.dt=number<double>(c.at("dt")); p.gamma=number<double>(c.at("gamma"));
        p.current=number<double>(c.at("current")); p.source=number<std::size_t>(c.at("source"));
        p.sink=number<std::size_t>(c.at("sink"));
        const auto steps=number<std::size_t>(c.at("steps"));
        if (steps==0 || steps>10000000 || !std::isfinite(static_cast<double>(steps)*p.dt))
            throw std::invalid_argument("Require 1..10000000 steps and finite duration");
        const double initial=number<double>(c.at("initial_conductivity"));
        physarum::PhysarumModel model(physarum::two_routes(),std::vector<double>(4,initial),p);
        const std::filesystem::path dir=argv[2];
        const auto config_path=std::filesystem::absolute(argv[1]).lexically_normal();
        if (config_path==std::filesystem::absolute(dir/"config.cfg").lexically_normal())
            throw std::invalid_argument("Use a separate output directory to preserve the input config");
        std::filesystem::create_directories(dir);
        auto config=output(dir/"config.cfg");
        for (const auto& [key,value]:c) config<<key<<"="<<value<<"\n";
        auto metadata=output(dir/"metadata.txt");
        metadata<<"project_version=0.1.0\ncompiler="<<__VERSION__<<"\ncplusplus="<<__cplusplus
                <<"\ncmake="<<PHYSARUM_CMAKE_VERSION<<"\neigen=";
#ifdef EIGEN_VERSION_STRING
        metadata<<EIGEN_VERSION_STRING;
#else
        metadata<<EIGEN_WORLD_VERSION<<'.'<<EIGEN_MAJOR_VERSION<<'.'<<EIGEN_MINOR_VERSION;
#endif
        metadata<<"\nsolver=dense_diagonally_scaled_LDLT\nterminal_selection=fixed\nrandomness=none\n"
                <<"integration=explicit_Euler\npruning=none\nconductivity_floor=none\n";
        auto edges=output(dir/"edges.csv"); edges<<"edge,from,to,length\n";
        for (std::size_t k=0;k<4;++k) {
            const auto& e=model.graph().edges()[k]; edges<<k<<','<<e.from<<','<<e.to<<','<<e.length<<'\n';
        }
        auto history=output(dir/"history.csv");
        history<<"step,time,edge,conductivity,flow,pressure_from,pressure_to,conservation_inf,backward_error,scaled_rcond\n";
        double max_conservation=0, max_backward=0, min_rcond=1;
        for (std::size_t step=0;step<=steps;++step) {
            const auto state=model.flow();
            max_conservation=std::max(max_conservation,state.conservation_inf);
            max_backward=std::max(max_backward,state.backward_error);
            min_rcond=std::min(min_rcond,state.scaled_rcond);
            for (std::size_t k=0;k<4;++k) {
                const auto& e=model.graph().edges()[k];
                history<<step<<','<<static_cast<double>(step)*p.dt<<','<<k<<','<<model.conductivities()[k]<<','
                       <<state.flows[k]<<','<<state.pressures[e.from]<<','<<state.pressures[e.to]<<','
                       <<state.conservation_inf<<','<<state.backward_error<<','<<state.scaled_rcond<<'\n';
            }
            if (step<steps) model.step();
        }
        auto summary=output(dir/"summary.txt");
        summary<<"max_conservation_inf="<<max_conservation<<"\nmax_backward_error="<<max_backward
               <<"\nmin_scaled_rcond="<<min_rcond<<'\n';
        for (std::size_t k=0;k<4;++k) summary<<"final_D_"<<k<<'='<<model.conductivities()[k]<<'\n';
        // Explicit closes surface late write failures before reporting success.
        history.close(); edges.close(); config.close(); metadata.close(); summary.close();
        std::cout<<std::setprecision(10)<<"Wrote "<<steps+1<<" states to "<<dir<<"\nmax conservation residual: "
                 <<max_conservation<<"\nmax backward error: "<<max_backward<<'\n';
    } catch (const std::exception& e) { std::cerr<<"Error: "<<e.what()<<'\n'; return 1; }
}
