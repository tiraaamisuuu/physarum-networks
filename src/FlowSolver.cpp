#include "physarum/FlowSolver.hpp"
#include <Eigen/Dense>
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace physarum {
FlowResult solve_flow(const Graph& graph, const std::vector<double>& d,
                      std::size_t source, std::size_t sink, double current) {
    const auto n = graph.node_count();
    if (d.size() != graph.edges().size() || source >= n || sink >= n || source == sink ||
        !std::isfinite(current) || current <= 0)
        throw std::invalid_argument("Invalid conductivity vector, terminals, or current");
    std::vector<double> weights(d.size());
    std::vector<std::vector<std::size_t>> adjacency(n);
    for (std::size_t k=0; k<d.size(); ++k) {
        if (!std::isfinite(d[k]) || d[k] < 0)
            throw std::invalid_argument("Conductivities must be finite and nonnegative");
        const auto& e=graph.edges()[k];
        weights[k]=d[k]/e.length;
        if (!std::isfinite(weights[k]) || (d[k]>0 && weights[k]==0))
            throw std::runtime_error("Conductance overflow/underflow; rescale the problem");
        if (weights[k]>0) { adjacency[e.from].push_back(e.to); adjacency[e.to].push_back(e.from); }
    }
    // Component detection uses exact zero only. No numerical pruning or artificial leakage.
    std::vector<int> component(n,-1);
    std::vector<std::size_t> grounds;
    for (std::size_t i=0; i<n; ++i) {
        if (component[i]>=0) continue;
        const int id=static_cast<int>(grounds.size());
        grounds.push_back(i);
        std::vector<std::size_t> stack{i}; component[i]=id;
        while (!stack.empty()) {
            const auto u=stack.back(); stack.pop_back();
            for (auto v:adjacency[u]) if (component[v]<0) { component[v]=id; stack.push_back(v); }
        }
    }
    if (component[source]!=component[sink])
        throw std::runtime_error("Source and sink are disconnected by zero conductivities");
    grounds[static_cast<std::size_t>(component[sink])]=sink;
    std::vector<int> index(n,-1);
    int m=0;
    for (std::size_t i=0; i<n; ++i)
        if (grounds[static_cast<std::size_t>(component[i])]!=i) index[i]=m++;
    Eigen::MatrixXd a=Eigen::MatrixXd::Zero(m,m);
    Eigen::VectorXd b=Eigen::VectorXd::Zero(m);
    b[index[source]]=current; // sink is grounded
    for (std::size_t k=0; k<d.size(); ++k) {
        const auto& e=graph.edges()[k]; const auto u=index[e.from], v=index[e.to]; const double w=weights[k];
        if (u>=0) a(u,u)+=w;
        if (v>=0) a(v,v)+=w;
        if (u>=0 && v>=0) { a(u,v)-=w; a(v,u)-=w; }
    }
    if (!a.allFinite() || (a.diagonal().array()<=0).any())
        throw std::runtime_error("Invalid grounded Laplacian; rescale the problem");
    // A = S^-1 H S^-1, solve H y = S b, p = S y. Reduces scale disparities.
    const Eigen::VectorXd scale=a.diagonal().array().sqrt().inverse();
    const Eigen::MatrixXd h=scale.asDiagonal()*a*scale.asDiagonal();
    Eigen::LDLT<Eigen::MatrixXd> factor(h);
    FlowResult result;
    result.scaled_rcond=factor.rcond();
    if (factor.info()!=Eigen::Success || !factor.isPositive() || !std::isfinite(result.scaled_rcond) ||
        result.scaled_rcond<1e-14)
        throw std::runtime_error("Grounded pressure system is numerically ill-conditioned (rcond < 1e-14)");
    const Eigen::VectorXd p=scale.asDiagonal()*factor.solve(scale.asDiagonal()*b);
    if (factor.info()!=Eigen::Success || !p.allFinite()) throw std::runtime_error("Pressure solve failed");
    const double residual=(a*p-b).lpNorm<Eigen::Infinity>();
    const double denominator=a.cwiseAbs().rowwise().sum().maxCoeff()*p.lpNorm<Eigen::Infinity>()+current;
    if (!std::isfinite(denominator)) throw std::runtime_error("Residual scaling overflow; rescale the problem");
    result.backward_error=residual/denominator;
    result.pressures.assign(n,0);
    for (std::size_t i=0; i<n; ++i) if (index[i]>=0) result.pressures[i]=p[index[i]];
    std::vector<double> balance(n,0);
    for (std::size_t k=0; k<d.size(); ++k) {
        const auto& e=graph.edges()[k];
        const double q=weights[k]*(result.pressures[e.from]-result.pressures[e.to]);
        if (!std::isfinite(q)) throw std::runtime_error("Nonfinite edge flow");
        result.flows.push_back(q); balance[e.from]+=q; balance[e.to]-=q;
    }
    balance[source]-=current; balance[sink]+=current;
    for (double r:balance) result.conservation_inf=std::max(result.conservation_inf,std::abs(r));
    if (result.conservation_inf>1e-12+1e-10*current || result.backward_error>1e-12)
        throw std::runtime_error("Pressure solution failed conservation/residual tolerances");
    return result;
}
}
