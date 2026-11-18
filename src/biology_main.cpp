#include "physarum/BiologyModel.hpp"
#include <filesystem>
#include <bit>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <cmath>
#include <limits>
namespace fs=std::filesystem;
using namespace physarum;
namespace {
std::vector<std::vector<double>> csv(const fs::path& p,std::size_t columns){
 std::ifstream in(p);if(!in)throw std::runtime_error("Cannot read mesh CSV");std::string line;std::getline(in,line);std::vector<std::vector<double>> rows;
 while(std::getline(in,line)){if(!line.empty()&&line.back()=='\r')line.pop_back();std::stringstream stream(line);std::string cell;std::vector<double> row;
  while(std::getline(stream,cell,',')){std::size_t used=0;double v=std::stod(cell,&used);if(used!=cell.size()||!std::isfinite(v))throw std::runtime_error("Invalid CSV number");row.push_back(v);}
  if(row.size()!=columns||(!line.empty()&&line.back()==','))throw std::runtime_error("Invalid CSV row");rows.push_back(row);if(rows.size()>30000)throw std::runtime_error("Mesh too large");}
 return rows;
}
double number(const char* s){std::size_t used=0;const std::string str(s);double v=std::stod(str,&used);if(used!=str.size()||!std::isfinite(v))throw std::runtime_error("Invalid argument");return v;}
void write(std::ofstream& f,const Eigen::VectorXd& v){f.write(reinterpret_cast<const char*>(v.data()),static_cast<std::streamsize>(v.size()*sizeof(double)));if(!f)throw std::runtime_error("Cannot save biology state");}
}
int main(int argc,char** argv){try{
 static_assert(std::endian::native==std::endian::little,"Biology records require little-endian float64");
 if(argc!=11)throw std::runtime_error("Usage: physarum_biology NODES EDGES DURATION DT HILL FEEDBACK TAU_FRONT SAVE_INTERVAL PROBE OUTPUT");
 const double duration=number(argv[3]),dt=number(argv[4]),hill=number(argv[5]),feedback=number(argv[6]),tau=number(argv[7]),interval=number(argv[8]);
 // argv[9] is the probe index, explicitly recorded by the caller.
 const double probe_value=number(argv[9]);
 if(!(duration>0&&duration<=1600&&dt>=.005&&dt<=.04&&interval>=dt&&interval<=duration&&duration/dt<=160000))throw std::runtime_error("Biology duration/dt limits exceeded");
 const auto steps=static_cast<int>(std::llround(duration/dt)),stride=static_cast<int>(std::llround(interval/dt));
 if(std::abs(steps*dt-duration)>1e-8||std::abs(stride*dt-interval)>1e-8)throw std::runtime_error("Duration and save interval must be multiples of dt");
 std::vector<BioNode> nodes;std::vector<BioEdge> edges;
 for(const auto& r:csv(argv[1],5)){if(r[0]!=static_cast<double>(nodes.size())||!(r[4]==0||r[4]==1))throw std::runtime_error("Node IDs/inoculum invalid");nodes.push_back({r[1],r[2],r[3],r[4]==1});}
 for(const auto& r:csv(argv[2],5)){if(r[0]!=static_cast<double>(edges.size())||r[1]!=std::floor(r[1])||r[2]!=std::floor(r[2])||r[1]<0||r[2]<0||r[1]>=static_cast<double>(nodes.size())||r[2]>=static_cast<double>(nodes.size()))throw std::runtime_error("Edge IDs invalid");edges.push_back({static_cast<int>(r[1]),static_cast<int>(r[2]),r[3],r[4]});}
 if(probe_value!=std::floor(probe_value)||probe_value<0||probe_value>=static_cast<double>(nodes.size()))throw std::runtime_error("Probe index invalid");const int probe=static_cast<int>(probe_value);
 int probe_edge=-1;for(std::size_t j=0;j<edges.size();++j)if(edges[j].from==probe||edges[j].to==probe){probe_edge=static_cast<int>(j);break;}if(probe_edge<0)throw std::runtime_error("Probe has no incident edge");
 if(nodes.size()>10000||edges.size()>30000||static_cast<double>(steps/stride+2)*(6*nodes.size()+2*edges.size())>40000000)throw std::runtime_error("Biology storage budget exceeded");
 const fs::path output(argv[10]);if(fs::exists(output)&&!fs::is_empty(output))throw std::runtime_error("Output must be new/empty");fs::create_directories(output);
 BiologyModel model(nodes,edges,{dt,hill,feedback,tau});
 const char* names[]{"c","phi","u","v","w","p","q","d"};std::ofstream files[8];for(int k=0;k<8;++k)files[k].open(output/(std::string(names[k])+".f64"),std::ios::binary);
 std::ofstream history(output/"history.csv"),probe_file(output/"probe.csv");history<<std::setprecision(17);probe_file<<std::setprecision(17);
 history<<"time,body_area,front_area,vein_length,vein_volume,min_c,max_c,min_phi,max_phi,fluid_residual,energy_defect\n";
 probe_file<<"time,c,phi,p,q,fluid_residual,energy_defect\n";
 int frame_count=0;double max_residual=0,max_energy=0;
 auto record=[&](double t){const auto& s=model.state();const Eigen::VectorXd* fields[]{&s.c,&s.phi,&s.u,&s.v,&s.w,&s.p,&s.q,&s.d};for(int k=0;k<8;++k)write(files[k],*fields[k]);
  double area=0,front=0,length=0,volume=0;for(std::size_t i=0;i<nodes.size();++i){if(s.w[static_cast<Eigen::Index>(i)]>1)area+=nodes[i].mass;if(s.w[static_cast<Eigen::Index>(i)]>=.1&&s.w[static_cast<Eigen::Index>(i)]<=.9)front+=nodes[i].mass;}
  for(std::size_t j=0;j<edges.size();++j){if(s.d[static_cast<Eigen::Index>(j)]>=1)length+=edges[j].length;volume+=edges[j].length*std::sqrt(s.d[static_cast<Eigen::Index>(j)]);}
  history<<t<<','<<area<<','<<front<<','<<length<<','<<volume<<','<<s.c.minCoeff()<<','<<s.c.maxCoeff()<<','<<s.phi.minCoeff()<<','<<s.phi.maxCoeff()<<','<<max_residual<<','<<max_energy<<'\n';++frame_count;
 };
 record(0);probe_file<<"0,"<<model.state().c[probe]<<","<<model.state().phi[probe]<<",0,0,0,0\n";
 for(int k=1;k<=steps;++k){model.step();const auto& d=model.diagnostics();max_residual=std::max(max_residual,d.fluid_residual);max_energy=std::max(max_energy,d.energy_defect);const auto& s=model.state();probe_file<<k*dt<<','<<s.c[probe]<<','<<s.phi[probe]<<','<<s.p[probe]<<','<<s.q[probe_edge]<<','<<d.fluid_residual<<','<<d.energy_defect<<'\n';
  if(k%stride==0||k==steps)record(k*dt);if(k%std::max(1,steps/20)==0)std::cout<<"PROGRESS "<<k*dt<<' '<<duration<<std::endl;
 }
 std::ofstream meta(output/"engine.json");meta<<std::setprecision(17)<<"{\"schema\":1,\"model\":\"schenz2017-"<<(hill==4?"cooperative4":"printed1")<<"\",\"nodes\":"<<nodes.size()<<",\"edges\":"<<edges.size()<<",\"frames\":"<<frame_count<<",\"steps\":"<<steps<<",\"dt\":"<<dt<<",\"hill\":"<<hill<<",\"feedback\":"<<feedback<<",\"tau_front\":"<<tau<<",\"probe\":"<<probe<<",\"probe_edge\":"<<probe_edge<<",\"max_fluid_residual\":"<<max_residual<<",\"max_energy_defect\":"<<max_energy<<",\"source_fingerprint\":\""<<PHYSARUM_SOURCE_FINGERPRINT<<"\",\"compiler\":\""<<__VERSION__<<"\"}\n";
 if(!meta||!history||!probe_file)throw std::runtime_error("Failed to save biology diagnostics");
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
