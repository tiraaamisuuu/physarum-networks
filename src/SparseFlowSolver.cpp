#include "physarum/SparseFlowSolver.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace physarum {
SparseFlowSolver::SparseFlowSolver(const Graph& graph):graph_(graph) {
    std::vector<std::vector<std::size_t>> neighbours(graph.node_count());
    for(const auto& e:graph.edges()){neighbours[e.from].push_back(e.to);neighbours[e.to].push_back(e.from);}
    std::vector<bool> seen(graph.node_count(),false);seen[0]=true;std::vector<std::size_t> stack{0};
    while(!stack.empty()){const auto u=stack.back();stack.pop_back();for(auto v:neighbours[u])if(!seen[v]){seen[v]=true;stack.push_back(v);}}
    if(std::find(seen.begin(),seen.end(),false)!=seen.end())throw std::invalid_argument("Sparse mesh topology must be connected");
}
FlowResult SparseFlowSolver::solve(const std::vector<double>& d,std::size_t source,std::size_t sink,double current) {
    const auto n=graph_.node_count();const auto m=static_cast<Eigen::Index>(n-1);
    if(d.size()!=graph_.edges().size() || source>=n || sink>=n || source==sink || !std::isfinite(current) || current<=0)
        throw std::invalid_argument("Invalid sparse flow state or demand");
    Eigen::VectorXd diagonal=Eigen::VectorXd::Zero(m),norm_rows=Eigen::VectorXd::Zero(m),b=Eigen::VectorXd::Zero(m);
    if(source)b[static_cast<Eigen::Index>(source-1)]=current;
    if(sink)b[static_cast<Eigen::Index>(sink-1)]=-current;
    std::vector<double> weights(d.size());
    for(std::size_t k=0;k<d.size();++k) {
        if(!std::isfinite(d[k]) || d[k]<=0)throw std::invalid_argument("Sparse tube model requires strictly positive conductivities; no floor is applied");
        const auto& e=graph_.edges()[k];const double w=d[k]/e.length;
        if(!std::isfinite(w) || w<=0)throw std::runtime_error("Conductance overflow or underflow");
        weights[k]=w;
        if(e.from)diagonal[static_cast<Eigen::Index>(e.from-1)]+=w;
        if(e.to)diagonal[static_cast<Eigen::Index>(e.to-1)]+=w;
    }
    if(!diagonal.allFinite() || (diagonal.array()<=0).any())throw std::runtime_error("Invalid sparse Laplacian diagonal");
    const Eigen::VectorXd scale=diagonal.array().sqrt().inverse();
    norm_rows=diagonal;
    Eigen::VectorXd h_rows=Eigen::VectorXd::Ones(m);
    std::vector<Eigen::Triplet<double>> entries;entries.reserve(static_cast<std::size_t>(m)+2*d.size());
    for(Eigen::Index i=0;i<m;++i)entries.emplace_back(i,i,1.);
    for(std::size_t k=0;k<d.size();++k) {
        const auto& e=graph_.edges()[k];
        if(e.from && e.to) {
            const auto u=static_cast<Eigen::Index>(e.from-1),v=static_cast<Eigen::Index>(e.to-1);
            const double w=weights[k]*scale[u]*scale[v];
            entries.emplace_back(u,v,-w);entries.emplace_back(v,u,-w);
            h_rows[u]+=w;h_rows[v]+=w;norm_rows[u]+=weights[k];norm_rows[v]+=weights[k];
        }
    }
    Eigen::SparseMatrix<double> h(m,m);h.setFromTriplets(entries.begin(),entries.end());h.makeCompressed();
    if(!analysed_){factor_.analyzePattern(h);analysed_=true;}
    factor_.factorize(h);
    if(factor_.info()!=Eigen::Success || !factor_.vectorD().allFinite() || (factor_.vectorD().array()<=0).any())
        throw std::runtime_error("Sparse pressure factorization failed or is not positive definite");
    // Hager-style inverse 1-norm estimate. It is a diagnostic estimate, not a bound.
    Eigen::VectorXd x=Eigen::VectorXd::Constant(m,1./static_cast<double>(m));double inverse_norm=0;Eigen::Index previous=-1;
    for(int iteration=0;iteration<6;++iteration) {
        const Eigen::VectorXd y=factor_.solve(x);
        if(!y.allFinite())throw std::runtime_error("Nonfinite sparse condition estimate");
        inverse_norm=std::max(inverse_norm,y.lpNorm<1>());
        const Eigen::VectorXd signs=y.unaryExpr([](double value){return value>=0?1.:-1.;});
        const Eigen::VectorXd z=factor_.solve(signs);Eigen::Index index=0;const double largest=z.cwiseAbs().maxCoeff(&index);
        if(!z.allFinite())throw std::runtime_error("Nonfinite sparse condition estimate");
        if(index==previous || largest<=z.dot(x)+1e-14)break;
        x.setZero();x[index]=1;previous=index;
    }
    FlowResult result;result.scaled_rcond=1/(h_rows.maxCoeff()*inverse_norm);
    if(!std::isfinite(result.scaled_rcond) || result.scaled_rcond<1e-14)
        throw std::runtime_error("Sparse scaled reciprocal condition estimate below 1e-14");
    Eigen::VectorXd p=scale.asDiagonal()*factor_.solve(scale.asDiagonal()*b);
    result.pressures.assign(n,0);result.flows.resize(d.size());
    Eigen::VectorXd residual(m);const double tolerance=1e-12+1e-10*current;
    for(int refinement=0;refinement<3;++refinement) {
        if(!p.allFinite())throw std::runtime_error("Nonfinite sparse pressure");
        for(std::size_t i=1;i<n;++i)result.pressures[i]=p[static_cast<Eigen::Index>(i-1)];
        std::vector<double> balance(n,0);
        for(std::size_t k=0;k<d.size();++k) {
            const auto& e=graph_.edges()[k];const double q=weights[k]*(result.pressures[e.from]-result.pressures[e.to]);
            if(!std::isfinite(q))throw std::runtime_error("Nonfinite mesh flow");
            result.flows[k]=q;balance[e.from]+=q;balance[e.to]-=q;
        }
        balance[source]-=current;balance[sink]+=current;result.conservation_inf=0;
        for(double value:balance)result.conservation_inf=std::max(result.conservation_inf,std::abs(value));
        for(std::size_t i=1;i<n;++i)residual[static_cast<Eigen::Index>(i-1)]=balance[i];
        const double denominator=norm_rows.maxCoeff()*p.lpNorm<Eigen::Infinity>()+current;
        if(!std::isfinite(denominator))throw std::runtime_error("Sparse residual scaling overflow");
        result.backward_error=residual.lpNorm<Eigen::Infinity>()/denominator;
        if(result.conservation_inf<=tolerance && result.backward_error<=1e-12)return result;
        p-=scale.asDiagonal()*factor_.solve(scale.asDiagonal()*residual);
    }
    throw std::runtime_error("Sparse pressure solution failed conservation/backward-error checks");
}
}
