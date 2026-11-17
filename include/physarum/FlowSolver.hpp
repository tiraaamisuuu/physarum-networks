#pragma once
#include "physarum/Graph.hpp"
#include <vector>

namespace physarum {
struct FlowResult {
    std::vector<double> pressures, flows;
    double conservation_inf = 0; // max_i |sum_j Q_ij - b_i|, includes grounded nodes
    double backward_error = 0;  // ||Ap-b||inf / (||A||inf ||p||inf + ||b||inf)
    double scaled_rcond = 1;    // reciprocal condition estimate after diagonal scaling
};
// Grounds the sink in its component, and one node in every demand-free component.
// Zero conductivities are allowed; positive conductivities are never thresholded.
FlowResult solve_flow(const Graph& graph, const std::vector<double>& conductivity,
                      std::size_t source, std::size_t sink, double current);
}
