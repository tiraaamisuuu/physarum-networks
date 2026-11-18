#include "physarum/BiologyModel.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
using namespace physarum;
void require(bool b,const char* s){if(!b)throw std::runtime_error(s);}
void near(double a,double b,double tol){require(std::isfinite(a)&&std::abs(a-b)<=tol,"Biology numerical mismatch");}
Eigen::Vector2d cycle(double hill,double& low,double& high){
 Eigen::Vector2d y{1,0};const double h=.02;low=100;high=-100;
 for(int i=0;i<50000;++i){auto rhs=[&](const Eigen::Vector2d& a){return BiologyModel::oscillator(a[0],a[1],hill);};const Eigen::Vector2d k1=rhs(y),k2=rhs(y+h*.5*k1),k3=rhs(y+h*.5*k2),k4=rhs(y+h*k3);y+=h/6*(k1+2*k2+2*k3+k4);require(y.allFinite(),"Oscillator diverged");if(i>40000){low=std::min(low,y[0]);high=std::max(high,y[0]);}}
 return y;
}
int main(int argc,char** argv){try{
 if(argc!=2)throw std::runtime_error("Choose biology test");const std::string test=argv[1];
 if(test=="oscillator"){
  double low,high;const auto stable=cycle(1,low,high);require(high-low<1e-8,"Printed Hill-1 control should settle at the published coefficients");near(stable[0],3.488469696,1e-7);
  cycle(4,low,high);require(low>5.7&&low<6.1&&high>7.7&&high<8.,"Cooperative variant must sustain calcium cycles");
 }else if(test=="symmetry"){
  BiologyModel model({{0,0,1,true},{1,0,1,true}},{{0,1,1,2}},{.02,4,.01,20});
  for(int i=0;i<100;++i)model.step();const auto& s=model.state();near(s.q[0],0,1e-13);near(s.p[0],s.p[1],1e-12);near(s.d[0],.1*std::exp(-.15*2),1e-13);near(s.c[0],s.c[1],1e-12);
 }else if(test=="mass"){
  BiologyModel model({{0,0,.2,true},{.7,0,.7,false},{2,0,1.1,false}},{{0,1,.7,.7},{1,2,1.3,.3}},{.02,4,0,20});
  const Eigen::Vector3d masses{.2,.7,1.1};
  for(int i=0;i<500;++i){model.step();const auto& a=model.state();near(masses.dot(a.u+a.v+.1*a.w),6.2,3e-11);}
 }else if(test=="fluid"){
  BiologyModel model({{0,0,.5,true},{.7,0,1,false},{2,0,.5,false}},{{0,1,.7,1},{1,2,1.3,1}},{.01,4,.01,20});
  for(int step=0;step<200;++step){const auto before=model.state();model.step();const auto& s=model.state();Eigen::Vector3d balance=(s.p-before.p)/.01+(s.c+before.c)*.5-Eigen::Vector3d::Constant(7);
   for(int j=0;j<2;++j){const double length=j==0?.7:1.3,d=before.d[j],inertia=length/(10+5*std::sqrt(d)),resistance=length/(2.5+13.5*d),compliance=(.1+.03*std::pow(d,.75))/length*(1+.005*(s.v[j]+s.v[j+1]));const double qm=.5*(before.q[j]+s.q[j]),pd=.5*(s.p[j]+before.p[j]-s.p[j+1]-before.p[j+1]);near(inertia*(s.q[j]-before.q[j])/.01+resistance*qm,pd,1e-10);balance[j]+=qm/compliance;balance[j+1]-=qm/compliance;}
   require(balance.cwiseAbs().maxCoeff()<1e-10,"Compliant fluid storage balance failed");require(model.diagnostics().energy_defect<1e-10,"Frozen-coefficient energy balance failed");near(s.d[1],0,0);
  }
  require(model.state().q.cwiseAbs().maxCoeff()>1e-5,"Nonuniform calcium must drive flow");
 }else if(test=="refinement"){
  Eigen::VectorXd result[3];int k=0;for(double dt:{.04,.02,.01}){BiologyModel model({{0,0,.5,true},{1,0,1,false},{2,0,.5,false}},{{0,1,1,1},{1,2,1,1}},{dt,4,0,20});for(int i=0;i<std::lround(4/dt);++i)model.step();result[k++]=model.state().c;}
  require((result[1]-result[2]).norm()<(result[0]-result[1]).norm(),"Time refinement should reduce the smooth short-case discrepancy");
 }else if(test=="invalid"){
  bool caught=false;try{BiologyModel m({{0,0,1,true},{1,0,1,false}},{{0,1,1,-.1}});}catch(const std::invalid_argument&){caught=true;}require(caught,"Reject negative diffusion weights instead of clipping them");
 }else throw std::runtime_error("Unknown biology test");
 std::cout<<test<<" passed\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
