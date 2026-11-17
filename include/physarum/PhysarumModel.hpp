#pragma once
#include "physarum/FlowSolver.hpp"

namespace physarum {
struct Parameters { double dt=0.05, gamma=1.8, current=2; std::size_t source=0, sink=3; };
double reinforcement(double flow, double gamma);
class PhysarumModel {
public:
    PhysarumModel(Graph graph, std::vector<double> initial, Parameters parameters);
    [[nodiscard]] const Graph& graph() const { return graph_; }
    [[nodiscard]] const std::vector<double>& conductivities() const { return d_; }
    [[nodiscard]] FlowResult flow() const;
    // Explicit Euler, with simultaneous updates from a single pre-update flow solution.
    void step();
private:
    Graph graph_;
    std::vector<double> d_;
    Parameters parameters_;
};
}
