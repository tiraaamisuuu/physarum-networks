#include "physarum/GrowthModel.hpp"
#include <algorithm>
#include <cmath>
#include <numbers>
#include <stdexcept>

namespace physarum {
namespace { constexpr double pi=std::numbers::pi; }
void diffuse_growth_trail(const std::vector<float>& input,std::vector<float>& output,
                          const std::vector<std::uint8_t>& blocked,int width,int height,double decay) {
    if(width<1 || height<1 || input.size()!=static_cast<std::size_t>(width*height) || blocked.size()!=input.size() ||
       &input==&output || !std::isfinite(decay) || decay<0 || decay>=1)
        throw std::invalid_argument("Invalid growth diffusion arguments");
    output.resize(input.size());
    for(int y=0;y<height;++y)for(int x=0;x<width;++x) {
        const auto i=static_cast<std::size_t>(y*width+x);
        if(blocked[i]) { output[i]=0;continue; }
        double sum=0;
        for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx) {
            const int xx=x+dx,yy=y+dy;
            if(xx<0 || yy<0 || xx>=width || yy>=height || blocked[static_cast<std::size_t>(yy*width+xx)])sum+=input[i];
            else sum+=input[static_cast<std::size_t>(yy*width+xx)];
        }
        output[i]=static_cast<float>((1-decay)*sum/9);
        if(!std::isfinite(output[i]) || output[i]<0)throw std::runtime_error("Invalid growth trail after diffusion");
    }
}
GrowthModel::GrowthModel(GrowthParameters p,std::vector<FoodSite> food,
                        std::vector<std::uint8_t> blocked,std::vector<float> river)
    :p_(p),food_(std::move(food)),blocked_(std::move(blocked)),river_(std::move(river)),random_state_(p.seed?p.seed:0x9e3779b9U) {
    if(p.width<32 || p.height<32 || p.width>800 || p.height>600 || p.seed_count<1 || p.max_agents<p.seed_count || p.max_agents>50000 ||
       p.division_interval<1 || p.division_interval>100 || food_.empty() || food_.size()>100)
        throw std::invalid_argument("Invalid growth dimensions, population, division interval or food count");
    for(double value:{p.initial_x,p.initial_y,p.seed_radius,p.sensor_distance,p.sensor_angle,p.turn_angle,p.decay,p.food_strength,p.food_range,p.river_aversion})
        if(!std::isfinite(value))throw std::invalid_argument("Growth parameters must be finite");
    if(p.seed_radius<2 || p.seed_radius>40 || p.sensor_distance<1 || p.sensor_distance>30 || p.sensor_angle<1 || p.sensor_angle>90 ||
       p.turn_angle<1 || p.turn_angle>90 || p.decay<=0 || p.decay>=1 || p.food_strength<0 || p.food_strength>100 || p.food_range<1 || p.food_range>100 ||
       p.river_aversion<0 || p.river_aversion>100 || cell(p.initial_x,p.initial_y)<0)
        throw std::invalid_argument("Growth parameter outside supported bounds");
    const auto n=static_cast<std::size_t>(p.width*p.height);
    if(blocked_.empty())blocked_.assign(n,0);
    if(river_.empty())river_.assign(n,0);
    if(blocked_.size()!=n || river_.size()!=n)throw std::invalid_argument("Growth masks have wrong dimensions");
    for(float r:river_)if(!std::isfinite(r) || r<0 || r>1)throw std::invalid_argument("River mask must be in [0,1]");
    for(const auto& f:food_)if(!std::isfinite(f.x) || !std::isfinite(f.y) || cell(f.x,f.y)<0 || blocked_[static_cast<std::size_t>(cell(f.x,f.y))])
        throw std::invalid_argument("Food must be inside accessible arena");
    trail_.assign(n,0);next_=trail_;cue_=trail_;occupancy_.assign(n,0);first_contact_.assign(food_.size(),-1);
    food_activity_.assign(food_.size(),0);food_weights_.assign(food_.size(),1);
    // Cache the documented analytic cue; coverage can change without recomputing exponentials.
    food_kernels_.resize(n*food_.size());
    for(std::size_t f=0;f<food_.size();++f)for(int y=0;y<p.height;++y)for(int x=0;x<p.width;++x) {
        const double dx=x+.5-food_[f].x,dy=y+.5-food_[f].y;
        food_kernels_[f*n+static_cast<std::size_t>(y*p.width+x)]=static_cast<float>(std::exp(-(dx*dx+dy*dy)/(2*p.food_range*p.food_range)));
    }
    agents_.reserve(static_cast<std::size_t>(p.max_agents));
    // Random unoccupied positions, all within the recorded inoculum disk.
    for(int attempt=0;static_cast<int>(agents_.size())<p.seed_count && attempt<100000;++attempt) {
        const double angle=2*pi*random(),radius=p.seed_radius*std::sqrt(random());
        GrowthAgent a{p.initial_x+radius*std::cos(angle),p.initial_y+radius*std::sin(angle),2*pi*random()};
        const int index=cell(a.x,a.y);
        if(index<0 || blocked_[static_cast<std::size_t>(index)] || occupancy_[static_cast<std::size_t>(index)])continue;
        agents_.push_back(a);occupancy_[static_cast<std::size_t>(index)]=1;trail_[static_cast<std::size_t>(index)]=5;
    }
    if(static_cast<int>(agents_.size())!=p.seed_count)throw std::invalid_argument("Inoculum cannot fit the requested initial population");
    update_food();rebuild_cue();
}
double GrowthModel::random() {
    // Recorded xorshift32, with specified integer-to-real mapping (no library distribution).
    auto x=random_state_;x^=x<<13U;x^=x>>17U;x^=x<<5U;random_state_=x;
    return static_cast<double>(x)/4294967296.;
}
int GrowthModel::cell(double x,double y) const {
    if(x<0 || y<0 || x>=p_.width || y>=p_.height)return -1;
    return static_cast<int>(y)*p_.width+static_cast<int>(x);
}
double GrowthModel::sense(const GrowthAgent& a,double offset) const {
    const double angle=a.angle+offset;
    const int i=cell(a.x+p_.sensor_distance*std::cos(angle),a.y+p_.sensor_distance*std::sin(angle));
    if(i<0 || blocked_[static_cast<std::size_t>(i)])return -1e9;
    const auto j=static_cast<std::size_t>(i);
    return trail_[j]+cue_[j]-p_.river_aversion*river_[j];
}
int GrowthModel::neighbours(int x,int y,int radius) const {
    int total=0;
    for(int yy=std::max(0,y-radius);yy<=std::min(p_.height-1,y+radius);++yy)
        for(int xx=std::max(0,x-radius);xx<=std::min(p_.width-1,x+radius);++xx)
            total+=occupancy_[static_cast<std::size_t>(yy*p_.width+xx)];
    return total;
}
void GrowthModel::rebuild_occupancy() {
    std::fill(occupancy_.begin(),occupancy_.end(),0);
    for(const auto& a:agents_)occupancy_[static_cast<std::size_t>(cell(a.x,a.y))]=1;
}
void GrowthModel::rebuild_cue() {
    // Smooth food cues are an explicit extension; not a physical diffusion calibration.
    if(!p_.persistent_food) {
        // Preserve the old arithmetic as well as the v1 depletion rule for replay.
        for(int y=0;y<p_.height;++y)for(int x=0;x<p_.width;++x) {
            double cue=0;
            for(std::size_t f=0;f<food_.size();++f) {
                const double dx=x+.5-food_[f].x,dy=y+.5-food_[f].y;
                const double weight=first_contact_[f]>=0?.05:1.;
                cue=std::max(cue,weight*std::exp(-(dx*dx+dy*dy)/(2*p_.food_range*p_.food_range)));
            }
            cue_[static_cast<std::size_t>(y*p_.width+x)]=static_cast<float>(p_.food_strength*cue);
        }
        return;
    }
    std::fill(cue_.begin(),cue_.end(),0);
    for(std::size_t f=0;f<food_.size();++f)for(std::size_t i=0;i<cue_.size();++i)
        cue_[i]=std::max(cue_[i],static_cast<float>(p_.food_strength)*food_weights_[f]*food_kernels_[f*cue_.size()+i]);
}
void GrowthModel::update_food() {
    bool changed=false;
    for(std::size_t f=0;f<food_.size();++f) {
        const auto& food=food_[f];int count=0;
        for(int y=std::max(0,static_cast<int>(food.y)-5);y<=std::min(p_.height-1,static_cast<int>(food.y)+5);++y)
            for(int x=std::max(0,static_cast<int>(food.x)-5);x<=std::min(p_.width-1,static_cast<int>(food.x)+5);++x) {
                const double dx=x+.5-food.x,dy=y+.5-food.y;
                if(dx*dx+dy*dy<=16)count+=occupancy_[static_cast<std::size_t>(y*p_.width+x)];
            }
        food_activity_[f]=count;
        if(first_contact_[f]>=0)continue;
        // First contact requires a live particle, never the diffused signal alone.
        for(const auto& a:agents_) {
            const double dx=a.x-food_[f].x,dy=a.y-food_[f].y;
            if(dx*dx+dy*dy<=16) { first_contact_[f]=iteration_;changed=true;break; }
        }
    }
    if(p_.persistent_food) {
        // A site emits again when uncovered; a historical visit never exhausts it.
        // Refresh every 10 updates to avoid per-particle cue flicker.
        if(iteration_%10!=0)return;
        for(std::size_t f=0;f<food_.size();++f) {
            const float weight=food_activity_[f]>0?.05F:1.F;
            if(weight!=food_weights_[f])changed=true;
            food_weights_[f]=weight;
        }
    }
    if(changed)rebuild_cue();
}
void GrowthModel::step() {
    ++iteration_;
    // Shuffle update order to avoid privileging an agent index.
    for(std::size_t i=agents_.size();i>1;--i)std::swap(agents_[i-1],agents_[static_cast<std::size_t>(random()*static_cast<double>(i))]);
    const double sa=p_.sensor_angle*pi/180,ra=p_.turn_angle*pi/180;
    const std::size_t existing=agents_.size();
    for(std::size_t j=0;j<existing;++j) {
        auto& a=agents_[j];
        const double forward=sense(a,0),left=sense(a,sa),right=sense(a,-sa);
        if(forward<left && forward<right)a.angle+=(random()<.5?ra:-ra);
        else if(left>right && forward<left)a.angle+=ra;
        else if(right>left && forward<right)a.angle-=ra;
        const double nx=a.x+std::cos(a.angle),ny=a.y+std::sin(a.angle);
        const int old=cell(a.x,a.y),target=cell(nx,ny);
        bool moved=false;
        if(target>=0 && !blocked_[static_cast<std::size_t>(target)] &&
           (!occupancy_[static_cast<std::size_t>(target)] || target==old)) {
            occupancy_[static_cast<std::size_t>(old)]=0;a.x=nx;a.y=ny;occupancy_[static_cast<std::size_t>(target)]=1;
            trail_[static_cast<std::size_t>(target)]+=5;moved=true;
        } else a.angle=2*pi*random();
        if(moved && iteration_%p_.division_interval==0 && static_cast<int>(agents_.size())<p_.max_agents) {
            const int count=neighbours(static_cast<int>(a.x),static_cast<int>(a.y),4);
            if(count>=1 && count<=20) {
                const int dx=static_cast<int>(3*random())-1,dy=static_cast<int>(3*random())-1;
                GrowthAgent child{std::floor(a.x)+dx+.5,std::floor(a.y)+dy+.5,2*pi*random()};
                const int where=cell(child.x,child.y);
                if(where>=0 && !blocked_[static_cast<std::size_t>(where)] && !occupancy_[static_cast<std::size_t>(where)]) {
                    occupancy_[static_cast<std::size_t>(where)]=1;agents_.push_back(child);++births_;
                    // New particles join movement on the next update.
                }
            }
        }
    }
    // Compression removes particles from completely full 5x5 neighbourhoods.
    if(iteration_%p_.division_interval==0) {
        const auto before=agents_.size();
        std::erase_if(agents_,[&](const auto& a){return neighbours(static_cast<int>(a.x),static_cast<int>(a.y),2)>24;});
        deaths_+=before-agents_.size();rebuild_occupancy();
    }
    update_food();
    // Simultaneous 3x3 mean diffusion; reflecting arena/obstacle faces conserve
    // trail mass before the explicit per-step decay. No periodic wrap-around.
    diffuse_growth_trail(trail_,next_,blocked_,p_.width,p_.height,p_.decay);
    trail_.swap(next_);
}
}
