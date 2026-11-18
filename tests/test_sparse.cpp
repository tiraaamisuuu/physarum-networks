#include "physarum/SparseFlowSolver.hpp"
#include "physarum/PhysarumModel.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
using namespace physarum;
void require(bool yes,const char* message){if(!yes)throw std::runtime_error(message);}
void near(double a,double b,double tol=1e-10){require(std::isfinite(a)&&std::abs(a-b)<=tol,"Numerical mismatch");}
template<class F>void throws(F f){bool caught=false;try{f();}catch(const std::exception&){caught=true;}require(caught,"Expected rejection");}
int main(int argc,char** argv){try{
 if(argc!=2)throw std::runtime_error("Choose sparse test");const std::string name=argv[1];
 if(name=="analytic"){
  Graph g(3,{{1,0,2},{1,2,3}});SparseFlowSolver s(g);const auto r=s.solve({4,2},0,2,2);
  near(r.pressures[0],0);near(r.pressures[1],-1);near(r.pressures[2],-4);near(r.flows[0],-2);near(r.flows[1],2);
 }else if(name=="dense"){
  Graph g(6,{{0,1,.7},{0,2,2},{1,3,1.2},{2,3,.5},{3,4,.8},{4,5,1.3},{2,5,2.4},{1,5,3}});SparseFlowSolver s(g);
  std::vector<double>d{.1,.3,.5,.7,.9,.4,.2,.8};
  for(std::size_t a=0;a<6;++a)for(std::size_t b=0;b<6;++b)if(a!=b){
   const auto x=s.solve(d,a,b,2),y=solve_flow(g,d,a,b,2);
   for(std::size_t i=0;i<6;++i)near(x.pressures[i],y.pressures[i]-y.pressures[0]);
   for(std::size_t i=0;i<d.size();++i)near(x.flows[i],y.flows[i]);
  }
 }else if(name=="history"){
  auto g=two_routes();SparseFlowSolver s(g);std::vector<double>d{.45,.55,.51,.48};
  PhysarumModel dense(g,d,{.05,1.8,2,0,3});
  for(int step=0;step<300;++step){
   const auto a=static_cast<std::size_t>((step/7)%4),b=(a+1+static_cast<std::size_t>(step%3))%4;
   dense.set_terminals(a,b);const auto flow=s.solve(d,a,b,2);
   for(std::size_t k=0;k<d.size();++k)d[k]=.95*d[k]+.05*reinforcement(flow.flows[k],1.8);
   dense.step();for(std::size_t k=0;k<d.size();++k)near(d[k],dense.conductivities()[k],2e-11);
  }
 }else if(name=="scale"){
  Graph g(2,{{0,1,2}});SparseFlowSolver s(g);const auto r=s.solve({1e-200},0,1,1);
  near(r.flows[0],1);near(r.pressures[1]/-2e200,1);require(r.scaled_rcond>.99,"Uniform scale should not harm conditioning");
 }else if(name=="invalid"){
  SparseFlowSolver owned(two_routes());near(owned.solve({.5,.5,.5,.5},0,3,2).flows[0],4./3);
  throws([]{Graph g(3,{{0,1,1}});SparseFlowSolver s(g);});
  auto g=two_routes();SparseFlowSolver s(g);
  throws([&]{s.solve({0,1,1,1},0,3,2);});throws([&]{s.solve({-1,1,1,1},0,3,2);});
  throws([&]{s.solve({1,1,1,1},0,0,2);});throws([&]{s.solve({1,1,1,1},0,4,2);});throws([&]{s.solve({1,1,1,1},0,3,0);});
 }else if(name=="conditioning"){
  Graph g(4,{{0,1,1},{1,2,1},{2,3,1}});SparseFlowSolver s(g);
  throws([&]{s.solve({1,1e-16,1},0,3,1);});
 }else if(name=="timestep"){
  Graph g(2,{{0,1,3}});SparseFlowSolver s(g);double errors[3];int i=0;
  for(double dt:{.1,.05,.025}){double d=.2;for(int k=0;k<std::lround(1/dt);++k){auto r=s.solve({d},0,1,2);d+=dt*(reinforcement(r.flows[0],2)-d);}errors[i++]=std::abs(d-(.8-.6*std::exp(-1.)));}
  require(errors[0]/errors[1]>1.9&&errors[1]/errors[2]>1.9,"Euler convergence against continuous analytic solution");
 }else throw std::runtime_error("Unknown sparse test");
 std::cout<<name<<" passed\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
