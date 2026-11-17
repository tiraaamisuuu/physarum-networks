#pragma once
#include <cstddef>
#include <vector>

namespace physarum {
// An undirected edge with an arbitrary orientation used to report signed flow.
struct Edge { std::size_t from, to; double length; };
class Graph {
public:
    Graph(std::size_t node_count, std::vector<Edge> edges);
    [[nodiscard]] std::size_t node_count() const { return node_count_; }
    [[nodiscard]] const std::vector<Edge>& edges() const { return edges_; }
private:
    std::size_t node_count_;
    std::vector<Edge> edges_;
};
Graph two_routes();
}
