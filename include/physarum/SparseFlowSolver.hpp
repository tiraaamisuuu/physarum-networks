#pragma once
#include "physarum/FlowSolver.hpp"
#include <Eigen/SparseCholesky>

namespace physarum {
// Fixed connected topology, strictly positive D. Node 0 is the pressure reference.
// scaled_rcond is an inverse-1-norm estimate, not Eigen's dense rcond diagnostic.
class SparseFlowSolver {
public:
    explicit SparseFlowSolver(const Graph& graph);
    FlowResult solve(const std::vector<double>& conductivity,std::size_t source,std::size_t sink,double current);
private:
    // Own the immutable topology: temporaries and later caller assignments are safe.
    const Graph graph_;
    Eigen::SimplicialLDLT<Eigen::SparseMatrix<double>> factor_;
    bool analysed_=false;
};
}
