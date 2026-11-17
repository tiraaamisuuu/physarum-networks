#include "physarum/PhysarumModel.hpp"
#include <cmath>
#include <stdexcept>
#include <utility>

namespace physarum {
double reinforcement(double flow, double gamma) {
    if (!std::isfinite(flow) || !std::isfinite(gamma) || gamma<=0)
        throw std::invalid_argument("Reinforcement requires finite flow and positive finite gamma");
    const double q=std::abs(flow);
    if (q==0) return 0;
    // Algebraically identical sigmoid, avoiding overflow in pow(q,gamma).
    if (q<=1) { const double x=std::pow(q,gamma); return x/(1+x); }
    return 1/(1+std::pow(1/q,gamma));
}
PhysarumModel::PhysarumModel(Graph graph, std::vector<double> initial, Parameters p)
    : graph_(std::move(graph)), d_(std::move(initial)), parameters_(p) {
    if (!std::isfinite(p.dt) || p.dt<=0 || p.dt>1 || !std::isfinite(p.gamma) || p.gamma<=0)
        throw std::invalid_argument("Require 0 < dt <= 1 and gamma > 0 (finite)");
    (void)flow(); // validate terminals, current, conductivities and solvability
}
FlowResult PhysarumModel::flow() const {
    return solve_flow(graph_,d_,parameters_.source,parameters_.sink,parameters_.current);
}
void PhysarumModel::step() {
    const auto state=flow();
    auto next=d_;
    for (std::size_t k=0; k<d_.size(); ++k) {
        next[k]=(1-parameters_.dt)*d_[k]+parameters_.dt*reinforcement(state.flows[k],parameters_.gamma);
        if (!std::isfinite(next[k]) || next[k]<0 || (parameters_.dt<1 && d_[k]>0 && next[k]==0))
            throw std::runtime_error("Conductivity overflow/underflow; stop or rescale (no clamping is applied)");
    }
    d_=std::move(next);
}
}
