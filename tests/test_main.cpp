#include "physarum/PhysarumModel.hpp"
#include <algorithm>
#include <cmath>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
using namespace physarum;
namespace {
void require(bool ok,const std::string& message) { if (!ok) throw std::runtime_error(message); }
void near(double got,double expected,double tolerance=1e-12) {
    require(std::isfinite(got) && std::abs(got-expected)<=tolerance,"Expected "+std::to_string(expected)+", got "+std::to_string(got));
}
template<class F> void throws(F f) { bool caught=false; try { f(); } catch (const std::exception&) { caught=true; } require(caught,"Expected exception"); }
std::vector<double> integrate(double dt,double duration) {
    PhysarumModel model(two_routes(),{.5,.5,.5,.5},{dt,1.8,2,0,3});
    for (int k=0;k<static_cast<int>(std::lround(duration/dt));++k) model.step();
    return model.conductivities();
}
double distance(const std::vector<double>& a,const std::vector<double>& b) {
    double err=0; for (std::size_t k=0;k<a.size();++k) err=std::max(err,std::abs(a[k]-b[k])); return err;
}
}
int main(int argc,char** argv) {
    const std::map<std::string,std::function<void()>> tests={
        {"series",[]{
            // Resistances 2/4 and 3/2; total 2, I=2 gives source pressure 4.
            auto r=solve_flow(Graph(3,{{0,1,2},{1,2,3}}),{4,2},0,2,2);
            near(r.pressures[0],4); near(r.pressures[1],3); near(r.pressures[2],0);
            near(r.flows[0],2); near(r.flows[1],2); require(r.conservation_inf<1e-12,"Conservation");
        }},
        {"parallel",[]{
            auto r=solve_flow(Graph(2,{{0,1,1},{0,1,3}}),{1,1},0,1,4);
            near(r.pressures[0],3); near(r.flows[0],3); near(r.flows[1],1);
        }},
        {"diamond",[]{
            // Route resistance 4 vs 8. Equivalent resistance 8/3; Delta p=16/3.
            auto r=solve_flow(two_routes(),{.5,.5,.5,.5},0,3,2);
            near(r.pressures[0],16.0/3); near(r.pressures[1],8.0/3); near(r.pressures[2],8.0/3);
            near(r.flows[0],4.0/3); near(r.flows[2],2.0/3);
        }},
        {"reverse",[]{
            auto a=solve_flow(Graph(2,{{0,1,2}}),{.5},0,1,2);
            auto b=solve_flow(Graph(2,{{1,0,2}}),{.5},0,1,2);
            near(a.flows[0],-b.flows[0]);
            PhysarumModel x(two_routes(),{.5,.5,.5,.5},{.05,1.8,2,0,3});
            PhysarumModel y(two_routes(),{.5,.5,.5,.5},{.05,1.8,2,3,0});
            for (int k=0;k<50;++k) { x.step(); y.step(); }
            require(distance(x.conductivities(),y.conductivities())<1e-12,"Terminal reversal symmetry");
        }},
        {"zero",[]{
            auto r=solve_flow(Graph(3,{{0,1,1},{1,2,1},{0,2,1}}),{1,1,0},0,2,1);
            near(r.flows[2],0); near(r.flows[0],1); near(r.pressures[0],2);
            PhysarumModel m(Graph(3,{{0,1,1},{1,2,1},{0,2,1}}),{1,1,0},{.1,1.8,1,0,2});
            m.step(); near(m.conductivities()[2],0);
        }},
        {"components",[]{
            auto r=solve_flow(Graph(5,{{0,1,1},{2,3,2}}),{1,1},0,1,1);
            near(r.flows[1],0); near(r.pressures[2],0); near(r.pressures[3],0); near(r.pressures[4],0);
        }},
        {"disconnected",[]{ throws([]{solve_flow(Graph(3,{{0,1,1},{1,2,1}}),{1,0},0,2,1);}); }},
        {"near_zero",[]{
            auto r=solve_flow(Graph(2,{{0,1,2}}),{1e-200},0,1,1);
            near(r.flows[0],1); require(std::abs(r.pressures[0]/2e200-1)<1e-12,"Small D is not pruned");
            throws([]{solve_flow(Graph(2,{{0,1,1e200}}),{1e-200},0,1,1);});
        }},
        {"invalid",[]{
            const double nan=std::numeric_limits<double>::quiet_NaN();
            throws([]{Graph(1,{});}); throws([]{Graph(2,{{0,0,1}});});
            throws([]{Graph(2,{{0,2,1}});}); throws([]{Graph(2,{{0,1,0}});});
            throws([=]{Graph(2,{{0,1,nan}});});
            throws([]{solve_flow(two_routes(),{1},0,3,2);});
            throws([]{solve_flow(two_routes(),{-1,1,1,1},0,3,2);});
            throws([]{solve_flow(two_routes(),{1,1,1,1},0,0,2);});
            throws([]{solve_flow(two_routes(),{1,1,1,1},0,3,0);});
            throws([=]{solve_flow(two_routes(),{1,1,nan,1},0,3,2);});
            for (double dt:{0.,-1.,1.01,nan}) throws([=]{PhysarumModel(two_routes(),{1,1,1,1},{dt,1.8,2,0,3});});
            throws([]{reinforcement(1,0);}); throws([=]{reinforcement(nan,1);});
        }},
        {"euler",[]{
            // One edge has exactly prescribed flow, so recurrence is independently known.
            PhysarumModel m(Graph(2,{{0,1,3}}),{.2},{.1,2,2,0,1});
            m.step(); near(m.conductivities()[0],.26);
            for (int k=1;k<20;++k) m.step();
            near(m.conductivities()[0],.8+(.2-.8)*std::pow(.9,20));
            near(reinforcement(-2,2),.8); near(reinforcement(0,2),0);
            near(reinforcement(1e300,100),1);
            // Flow-free leaf decays without thresholding.
            PhysarumModel leaf(Graph(3,{{0,1,1},{0,2,1}}),{.5,.5},{.1,2,2,0,1});
            for(int k=0;k<10;++k) leaf.step();
            near(leaf.conductivities()[1],.5*std::pow(.9,10));
        }},
        {"positivity",[]{
            for (double dt:{.01,.1,.5,1.}) {
                PhysarumModel m(two_routes(),{.5,.5,.5,.5},{dt,1.8,2,0,3});
                for (int k=0;k<100;++k) { m.step(); for (double d:m.conductivities()) require(d>=0 && d<=1,"Invariant [0,1]"); }
            }
            // At dt=1 a zero-flow leaf becomes exactly zero, as Euler specifies.
            PhysarumModel m(Graph(3,{{0,1,1},{0,2,1}}),{.5,.5},{1,2,2,0,1}); m.step(); near(m.conductivities()[1],0);
        }},
        {"timestep",[]{
            const auto ref=integrate(.000625,4);
            const double e1=distance(integrate(.1,4),ref),e2=distance(integrate(.05,4),ref),e3=distance(integrate(.025,4),ref);
            require(e1/e2>1.8 && e1/e2<2.3 && e2/e3>1.8 && e2/e3<2.3,"Euler first order refinement");
            const auto final=integrate(.05,30);
            near(final[0],reinforcement(2,1.8),1e-9); require(final[2]<1e-9,"Shorter route dominates fixture");
        }},
        {"conditioning",[]{
            // Strongly connected upstream nodes with a tiny bottleneck to grounded sink.
            throws([]{solve_flow(Graph(3,{{0,1,1},{1,2,1}}),{1,1e-18},0,2,1);});
        }}
    };
    try {
        if (argc!=2 || !tests.contains(argv[1])) throw std::invalid_argument("Specify test case name");
        tests.at(argv[1])(); std::cout<<"PASS "<<argv[1]<<'\n';
    } catch(const std::exception& e) { std::cerr<<"FAIL: "<<e.what()<<'\n'; return 1; }
}
