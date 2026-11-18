#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>

namespace physarum {
// A separate chemotactic particle model; these fields are not Tero conductivities.
struct GrowthParameters {
    int width=480, height=300, seed_count=220, max_agents=14000, division_interval=4;
    std::uint32_t seed=42;
    double initial_x=0, initial_y=0, seed_radius=11;
    double sensor_distance=9, sensor_angle=45, turn_angle=45;
    double decay=.08, food_strength=8, food_range=30, river_aversion=0;
    bool persistent_food=true;
};
struct FoodSite { double x,y; };
struct GrowthAgent { double x,y,angle; };
// Simultaneous 3x3 mean with reflecting arena/blocked faces, followed by decay.
void diffuse_growth_trail(const std::vector<float>& input,std::vector<float>& output,
                          const std::vector<std::uint8_t>& blocked,int width,int height,double decay);
class GrowthModel {
public:
    GrowthModel(GrowthParameters parameters,std::vector<FoodSite> food,
                std::vector<std::uint8_t> blocked={},std::vector<float> river={});
    void step();
    [[nodiscard]] int iteration() const { return iteration_; }
    [[nodiscard]] const std::vector<float>& trail() const { return trail_; }
    [[nodiscard]] const std::vector<int>& occupancy() const { return occupancy_; }
    [[nodiscard]] const std::vector<GrowthAgent>& agents() const { return agents_; }
    [[nodiscard]] const std::vector<int>& first_contact() const { return first_contact_; }
    [[nodiscard]] const std::vector<int>& food_activity() const { return food_activity_; }
    [[nodiscard]] const std::vector<float>& food_weights() const { return food_weights_; }
    [[nodiscard]] std::size_t births() const { return births_; }
    [[nodiscard]] std::size_t deaths() const { return deaths_; }
private:
    GrowthParameters p_;
    std::vector<FoodSite> food_;
    std::vector<std::uint8_t> blocked_;
    std::vector<float> river_,trail_,next_,cue_;
    std::vector<float> food_kernels_,food_weights_;
    std::vector<int> food_activity_;
    std::vector<int> occupancy_,first_contact_;
    std::vector<GrowthAgent> agents_;
    std::uint32_t random_state_;
    int iteration_=0;
    std::size_t births_=0,deaths_=0;
    double random();
    int cell(double x,double y) const;
    double sense(const GrowthAgent& agent,double offset) const;
    int neighbours(int x,int y,int radius) const;
    void rebuild_occupancy();
    void update_food();
    void rebuild_cue();
};
}
