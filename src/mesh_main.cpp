#include "physarum/SparseFlowSolver.hpp"
#include "physarum/PhysarumModel.hpp"
#include <bit>
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
template<class T>T number(const std::string& s){T value{};const auto [end,error]=std::from_chars(s.data(),s.data()+s.size(),value);if(error!=std::errc{} || end!=s.data()+s.size())throw std::invalid_argument("Invalid mesh number: "+s);return value;}
std::vector<std::string> row(const std::string& line){std::vector<std::string> values;std::istringstream stream(line);std::string value;while(std::getline(stream,value,','))values.push_back(value);return values;}
std::ifstream input(const std::filesystem::path& path,const std::string& header){std::ifstream f(path);std::string line;if(!std::getline(f,line) || line!=header)throw std::invalid_argument("Invalid mesh CSV header: "+path.string());return f;}
std::ofstream output(const std::filesystem::path& path,bool binary=false){std::ofstream f(path,binary?(std::ios::out|std::ios::binary):std::ios::out);f.exceptions(std::ios::failbit|std::ios::badbit);f<<std::setprecision(17);return f;}
void write(std::ofstream& out,const std::vector<double>& values){out.write(reinterpret_cast<const char*>(values.data()),static_cast<std::streamsize>(values.size()*sizeof(double)));}
}
int main(int argc,char** argv){try{
    if(argc!=7)throw std::invalid_argument("Usage: physarum_mesh CONFIG EDGES_CSV NODE_COUNT INITIAL_D_CSV DEMANDS_CSV OUTPUT_DIRECTORY");
    static_assert(std::endian::native==std::endian::little && sizeof(double)==8);
    std::ifstream config(argv[1]);std::string line;std::map<std::string,std::string> c;
    if(!config)throw std::invalid_argument("Cannot read mesh config");
    while(std::getline(config,line)){const auto at=line.find('=');if(at==std::string::npos || !c.emplace(line.substr(0,at),line.substr(at+1)).second)throw std::invalid_argument("Mesh config needs unique key=value lines");}
    if(c.size()!=4)throw std::invalid_argument("Mesh config needs dt, steps, gamma, current");
    const double dt=number<double>(c.at("dt")),gamma=number<double>(c.at("gamma")),current=number<double>(c.at("current"));
    const auto steps=number<std::size_t>(c.at("steps")),nodes=number<std::size_t>(argv[3]);
    if(!std::isfinite(dt) || dt<=0 || dt>.25 || !std::isfinite(gamma) || gamma<=0 || !std::isfinite(current) || current<=0 || steps<1 || steps>6000 || nodes<2 || nodes>8000)throw std::invalid_argument("Unsupported mesh dimensions or parameters");
    std::vector<physarum::Edge> edges;auto graph_csv=input(argv[2],"edge,from,to,length");
    while(std::getline(graph_csv,line)){auto r=row(line);if(r.size()!=4 || number<std::size_t>(r[0])!=edges.size())throw std::invalid_argument("Invalid mesh edge ordering");edges.push_back({number<std::size_t>(r[1]),number<std::size_t>(r[2]),number<double>(r[3])});}
    if(edges.empty() || edges.size()>25000 || edges.size()*(steps+1)>25000000)throw std::invalid_argument("Mesh output size exceeds supported bound");
    physarum::Graph graph(nodes,std::move(edges));std::vector<double> d;
    auto initial=input(argv[4],"edge,conductivity");
    while(std::getline(initial,line)){auto r=row(line);if(r.size()!=2 || number<std::size_t>(r[0])!=d.size())throw std::invalid_argument("Invalid initial mesh conductivities");const double value=number<double>(r[1]);if(!std::isfinite(value) || value<=0)throw std::invalid_argument("Initial mesh D must be positive");d.push_back(value);}
    if(d.size()!=graph.edges().size())throw std::invalid_argument("Initial mesh D count mismatch");
    std::vector<std::pair<std::size_t,std::size_t>> pairs;auto demand=input(argv[5],"step,source,sink");
    while(std::getline(demand,line)){auto r=row(line);if(r.size()!=3 || number<std::size_t>(r[0])!=pairs.size())throw std::invalid_argument("Invalid demand ordering");const auto a=number<std::size_t>(r[1]),b=number<std::size_t>(r[2]);if(a>=nodes || b>=nodes || a==b)throw std::invalid_argument("Invalid mesh terminal pair");pairs.emplace_back(a,b);}
    if(pairs.size()!=steps+1)throw std::invalid_argument("Mesh demands require steps+1 states");
    physarum::SparseFlowSolver solver(graph);const std::filesystem::path folder=argv[6];std::filesystem::create_directories(folder);
    auto ds=output(folder/"D.f64",true),qs=output(folder/"Q.f64",true),ps=output(folder/"P.f64",true),diagnostics=output(folder/"diagnostics.csv");
    diagnostics<<"step,time,source,sink,conservation_inf,backward_error,scaled_rcond_estimate\n";
    for(std::size_t step=0;step<=steps;++step){
        const auto state=solver.solve(d,pairs[step].first,pairs[step].second,current);
        write(ds,d);write(qs,state.flows);write(ps,state.pressures);
        diagnostics<<step<<','<<static_cast<double>(step)*dt<<','<<pairs[step].first<<','<<pairs[step].second<<','<<state.conservation_inf<<','<<state.backward_error<<','<<state.scaled_rcond<<'\n';
        if(step<steps)for(std::size_t k=0;k<d.size();++k){const double next=(1-dt)*d[k]+dt*physarum::reinforcement(state.flows[k],gamma);if(!std::isfinite(next) || next<=0)throw std::runtime_error("Mesh conductivity underflow/overflow; no floor is applied");d[k]=next;}
    }
    auto meta=output(folder/"metadata.txt");meta<<"model=Tero_2010_sigmoid_mesh_v1\nsolver=Eigen_SimplicialLDLT_diagonally_scaled\npressure_reference=node_0\ncondition_diagnostic=Hager_inverse_1_norm_estimate_6_iterations\ncompiler="<<__VERSION__<<"\neigen="<<EIGEN_WORLD_VERSION<<'.'<<EIGEN_MAJOR_VERSION<<'.'<<EIGEN_MINOR_VERSION<<"\npruning=none\nconductivity_floor=none\nformat=IEEE754_float64_little_endian\n";
    ds.close();qs.close();ps.close();diagnostics.close();meta.close();std::cout<<"Completed "<<steps<<" updates, "<<nodes<<" nodes, "<<graph.edges().size()<<" edges\n";
}catch(const std::exception& error){std::cerr<<"Error: "<<error.what()<<'\n';return 1;}}
