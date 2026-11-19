#include "physarum/BiologyModel.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
namespace physarum {
namespace { using V=Eigen::VectorXd;using T=Eigen::Triplet<double>;
void valid(const V& x,const char* name){if(!x.allFinite())throw std::runtime_error(std::string("Non-finite biological field: ")+name);}
}
double BiologyModel::free_calcium(double c,double phi){
 return (1+.17*(c-7.5))*(.349353-.0454567*phi+1.15905*phi*phi+1.823858*phi*phi*phi);
}
Eigen::Vector2d BiologyModel::oscillator(double c,double phi,double hill){
 const double nc=free_calcium(c,phi),z=1.75*nc/(1+1.75*nc);
 const double activation=hill==1?z:z*z*z*z;
 return {-.12*nc+.004*(25-c),activation*(1-phi)-.1*phi};
}
BiologyModel::BiologyModel(std::vector<BioNode> nodes,std::vector<BioEdge> edges,BioParameters p)
 :nodes_(std::move(nodes)),edges_(std::move(edges)),parameters_(p){
 if((p.integrator!="legacy"&&p.integrator!="midpoint")||nodes_.size()<2||edges_.empty()||!(p.dt>0&&p.dt<=.04)||!(p.hill==1||p.hill==4)||!(p.feedback>=0&&p.feedback<=.1)||!(p.tau_front>=2&&p.tau_front<=40))throw std::invalid_argument("Invalid biology configuration");
 const auto n=static_cast<Eigen::Index>(nodes_.size()),e=static_cast<Eigen::Index>(edges_.size());
 state_={V::Zero(n),V::Zero(n),V::Constant(n,3),V::Zero(n),V::Zero(n),V::Zero(n),V::Zero(e),V::Zero(e)};
 bool seed=false;
 for(Eigen::Index i=0;i<n;++i){const auto& a=nodes_[static_cast<std::size_t>(i)];
  if(!std::isfinite(a.x)||!std::isfinite(a.y)||!std::isfinite(a.mass)||a.mass<=0)throw std::invalid_argument("Invalid biological node");
  if(a.inoculum){state_.c[i]=state_.v[i]=1;seed=true;}
 }
 if(!seed)throw std::invalid_argument("No inoculum");
 for(Eigen::Index j=0;j<e;++j){const auto& a=edges_[static_cast<std::size_t>(j)];
  if(a.from<0||a.to<0||a.from>=n||a.to>=n||a.from==a.to||!std::isfinite(a.length)||a.length<=0||!std::isfinite(a.weight)||a.weight<0)throw std::invalid_argument("Invalid biological edge");
  if(nodes_[static_cast<std::size_t>(a.from)].inoculum||nodes_[static_cast<std::size_t>(a.to)].inoculum)state_.d[j]=.1;
 }
 // (M tau + dt D K) z_new = M tau z_old, zero normal flux.
 // Positive cotangent weights give an M-matrix; no field clipping is used.
 for(int field=0;field<4;++field){
  auto d=std::make_unique<Diffusion>();d->mass.resize(n);std::vector<T> entries;
  const double coefficient=field==0?.2:field==1?.012:field==2?.2:.02;
  for(Eigen::Index i=0;i<n;++i){d->mass[i]=nodes_[static_cast<std::size_t>(i)].mass*(field<2?(.0072/(nodes_[static_cast<std::size_t>(i)].inoculum?3:1)):p.tau_front);entries.emplace_back(i,i,d->mass[i]);}
  for(const auto& a:edges_){const double k=p.dt*(p.integrator=="midpoint"?.5:1)*coefficient*a.weight;entries.emplace_back(a.from,a.from,k);entries.emplace_back(a.to,a.to,k);entries.emplace_back(a.from,a.to,-k);entries.emplace_back(a.to,a.from,-k);}
  Sparse matrix(n,n);matrix.setFromTriplets(entries.begin(),entries.end());d->factor.compute(matrix);
  if(p.integrator=="midpoint"){d->rhs=-matrix;for(Eigen::Index i=0;i<n;++i)d->rhs.coeffRef(i,i)+=2*d->mass[i];d->rhs.makeCompressed();}
  if(d->factor.info()!=Eigen::Success)throw std::runtime_error("Biological diffusion factorization failed");diffusion_.push_back(std::move(d));
 }
}
void BiologyModel::react(double duration,const V& conductivity){
 const auto n=state_.c.size();const int steps=std::max(1,static_cast<int>(std::ceil(duration/.005)));const double h=duration/steps;
 V incident=V::Zero(n);for(Eigen::Index j=0;j<state_.d.size();++j){const auto& e=edges_[static_cast<std::size_t>(j)];incident[e.from]+=conductivity[j];incident[e.to]+=conductivity[j];}
 for(int sub=0;sub<steps;++sub)for(Eigen::Index i=0;i<n;++i){
  const double tau=.0072/(nodes_[static_cast<std::size_t>(i)].inoculum?3:1);
  Eigen::Vector<double,5> y{state_.c[i],state_.phi[i],state_.u[i],state_.v[i],state_.w[i]};
  auto rhs=[&](const Eigen::Vector<double,5>& a)->Eigen::Vector<double,5>{
   const Eigen::Vector2d ca=oscillator(a[0],a[1],parameters_.hill)/tau;const double uvv=a[2]*a[3]*a[3],band=(a[4]>=.1&&a[4]<=.9)?1:0;
   return {ca[0],ca[1],-uvv/parameters_.tau_front,(uvv-.01*a[3])/parameters_.tau_front+parameters_.feedback*band*incident[i],.1*a[3]/parameters_.tau_front};
  };
  const auto k1=rhs(y),k2=rhs(y+h*.5*k1),k3=rhs(y+h*.5*k2),k4=rhs(y+h*k3);y+=h/6*(k1+2*k2+2*k3+k4);
  state_.c[i]=y[0];state_.phi[i]=y[1];state_.u[i]=y[2];state_.v[i]=y[3];state_.w[i]=y[4];
 }
}
void BiologyModel::diffuse(){
 V* fields[]{&state_.c,&state_.phi,&state_.u,&state_.v};
 for(int j=0;j<4;++j){
  auto& d=*diffusion_[static_cast<std::size_t>(j)];
  const bool midpoint=parameters_.integrator=="midpoint";
  if(midpoint&&completed_steps_>=2){*fields[j]=d.factor.solve(d.rhs*(*fields[j]));}
  else {
   // Rannacher startup: two backward-Euler half steps use the same CN factor.
   const int repeats=midpoint?2:1;
   for(int k=0;k<repeats;++k)*fields[j]=d.factor.solve((d.mass.array()*fields[j]->array()).matrix());
  }
  if(d.factor.info()!=Eigen::Success)throw std::runtime_error("Biological diffusion solve failed");
 }
}
void BiologyModel::fluid_step(const V& previous_c,const V& conductivity,const V& activator,const V& body){
 const auto n=state_.p.size(),e=state_.q.size();const double dt=parameters_.dt;
 V a(e),b(e),resistance(e),inertia(e),compliance(e),rhs=state_.p-dt*((previous_c+state_.c)*.5-V::Constant(n,7));
 std::vector<T> entries;entries.reserve(static_cast<std::size_t>(n+4*e));for(Eigen::Index i=0;i<n;++i)entries.emplace_back(i,i,1);
 for(Eigen::Index j=0;j<e;++j){const auto& edge=edges_[static_cast<std::size_t>(j)];const double d=conductivity[j],v=.5*(activator[edge.from]+activator[edge.to]);
  inertia[j]=edge.length/(10+5*std::sqrt(d));resistance[j]=edge.length/(2.5+13.5*d);
  compliance[j]=(.1+.03*std::pow(d,.75))/edge.length*(1+.01*v);
  a[j]=(inertia[j]-.5*dt*resistance[j])/(inertia[j]+.5*dt*resistance[j]);b[j]=.5*dt/(inertia[j]+.5*dt*resistance[j]);
  const double k=.5*dt*b[j]/compliance[j],oldflux=.5*dt/compliance[j]*((1+a[j])*state_.q[j]+b[j]*(state_.p[edge.from]-state_.p[edge.to]));
  rhs[edge.from]-=oldflux;rhs[edge.to]+=oldflux;
  entries.emplace_back(edge.from,edge.from,k);entries.emplace_back(edge.to,edge.to,k);entries.emplace_back(edge.from,edge.to,-k);entries.emplace_back(edge.to,edge.from,-k);
 }
 Sparse matrix(n,n);matrix.setFromTriplets(entries.begin(),entries.end());if(!fluid_analyzed_){fluid_.analyzePattern(matrix);fluid_analyzed_=true;}fluid_.factorize(matrix);
 if(fluid_.info()!=Eigen::Success)throw std::runtime_error("Biological pressure factorization failed");
 const V pn=fluid_.solve(rhs);V qn(e),balance=(pn-state_.p)/dt+((previous_c+state_.c)*.5-V::Constant(n,7));
 double residual=0,energy=0,dissipation=0;
 for(Eigen::Index j=0;j<e;++j){const auto& edge=edges_[static_cast<std::size_t>(j)];qn[j]=a[j]*state_.q[j]+b[j]*(pn[edge.from]+state_.p[edge.from]-pn[edge.to]-state_.p[edge.to]);
  const double qm=.5*(qn[j]+state_.q[j]),pm=.5*(pn[edge.from]+state_.p[edge.from]-pn[edge.to]-state_.p[edge.to]);
  residual=std::max(residual,std::abs(inertia[j]*(qn[j]-state_.q[j])/dt+resistance[j]*qm-pm));
  balance[edge.from]+=qm/compliance[j];balance[edge.to]-=qm/compliance[j];
  energy+=.5*inertia[j]/compliance[j]*((qn[j]-state_.q[j])*(qn[j]+state_.q[j]));dissipation+=resistance[j]/compliance[j]*qm*qm;
  const double occupied=.5*(body[edge.from]+body[edge.to])>1?1:0;
  const double f=std::pow(std::abs(qm),1.3);state_.d[j]=std::exp(-.15*dt)*state_.d[j]-std::expm1(-.15*dt)/.15*occupied*f/(1+.01*f);
 }
 energy+=(pn-state_.p).dot((pn+state_.p)*.5);
 const double forcing=((pn+state_.p)*.5).dot((previous_c+state_.c)*.5-V::Constant(n,7));
 diagnostics_.fluid_residual=std::max(residual,balance.cwiseAbs().maxCoeff());
 diagnostics_.energy_defect=std::abs(energy+dt*(dissipation+forcing))/(1+std::abs(energy)+dt*(dissipation+std::abs(forcing)));
 state_.p=pn;state_.q=qn;
}
void BiologyModel::step(){
 const V previous_c=state_.c;
 if(parameters_.integrator=="legacy"){
  react(parameters_.dt*.5,state_.d);diffuse();react(parameters_.dt*.5,state_.d);
  fluid_step(previous_c,state_.d,state_.v,state_.w);
 }else {
  // A positive half-step predictor supplies midpoint coupling coefficients.
  // It leaves the accepted conductivity untouched until the final update.
  const V previous_v=state_.v,previous_w=state_.w;
  V midpoint_d(state_.d.size());
  const double decay=std::exp(-.15*parameters_.dt*.5),gain=-std::expm1(-.15*parameters_.dt*.5)/.15;
  for(Eigen::Index j=0;j<state_.d.size();++j){
   const auto& edge=edges_[static_cast<std::size_t>(j)];
   const double occupied=.5*(previous_w[edge.from]+previous_w[edge.to])>1?1:0;
   const double power=std::pow(std::abs(state_.q[j]),1.3);
   midpoint_d[j]=decay*state_.d[j]+gain*occupied*power/(1+.01*power);
  }
  react(parameters_.dt*.5,midpoint_d);diffuse();react(parameters_.dt*.5,midpoint_d);
  const V midpoint_v=.5*(previous_v+state_.v),midpoint_w=.5*(previous_w+state_.w);
  fluid_step(previous_c,midpoint_d,midpoint_v,midpoint_w);
 }
 ++completed_steps_;
 for(const auto* a:{&state_.c,&state_.phi,&state_.u,&state_.v,&state_.w,&state_.p,&state_.q,&state_.d})valid(*a,"state");
 if(state_.u.minCoeff()< -1e-10||state_.v.minCoeff()< -1e-10||state_.w.minCoeff()< -1e-10||state_.d.minCoeff()<0)throw std::runtime_error("Biological positivity failure; reduce time step");
}
}
