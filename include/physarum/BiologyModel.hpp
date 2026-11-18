#pragma once
#include <Eigen/Sparse>
#include <Eigen/SparseCholesky>
#include <vector>
#include <memory>
namespace physarum {
struct BioNode { double x,y,mass; bool inoculum; };
struct BioEdge { int from,to; double length,weight; };
struct BioParameters {
 double dt=.02, hill=4, feedback=.01, tau_front=20;
};
struct BioState { Eigen::VectorXd c,phi,u,v,w,p,q,d; };
struct BioDiagnostics { double fluid_residual=0,energy_defect=0; };
// Schenz et al. (2017) fields on a lumped linear finite-element mesh.
// Hill=4 is an explicitly named cooperative variant, not an exact reproduction.
class BiologyModel {
 public:
 BiologyModel(std::vector<BioNode> nodes,std::vector<BioEdge> edges,BioParameters parameters={});
 void step();
 const BioState& state() const {return state_;}
 const BioDiagnostics& diagnostics() const {return diagnostics_;}
 const std::vector<BioNode>& nodes() const{return nodes_;}
 const std::vector<BioEdge>& edges() const{return edges_;}
 static double free_calcium(double c,double phi);
 static Eigen::Vector2d oscillator(double c,double phi,double hill);
 private:
 using Sparse=Eigen::SparseMatrix<double>;
 struct Diffusion { Eigen::VectorXd mass; Eigen::SimplicialLDLT<Sparse> factor; };
 std::vector<BioNode> nodes_;std::vector<BioEdge> edges_;BioParameters parameters_;
 BioState state_;BioDiagnostics diagnostics_;
 std::vector<std::unique_ptr<Diffusion>> diffusion_;
 Eigen::SimplicialLDLT<Sparse> fluid_;bool fluid_analyzed_=false;
 void react(double duration);
 void diffuse();
 void fluid_step(const Eigen::VectorXd& previous_c);
};
}
