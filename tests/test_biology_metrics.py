import unittest
import numpy as np
from desktop.biology_metrics import vein_metrics

class VeinMetrics(unittest.TestCase):
    def setUp(self):
        self.xy=np.array([[10.,2.5],[20.,2.5],[30.,2.5],[10.,.1],[20.,.1]])
        self.edges=np.array([[0,1,10,1],[1,2,10,1],[3,4,10,1]],float);self.seed=np.array([True,False,False,False,False])
    def test_disconnected_tubes_are_not_source_connections(self):
        r=vein_metrics(self.xy,self.edges,np.ones(3),self.seed,'straight');self.assertEqual(r['components'],2);self.assertAlmostEqual(r['inoculum_attached_fraction'],2/3);self.assertEqual(r['inoculum_attached_length'],20);self.assertAlmostEqual(r['mean_wall_clearance'],1.7);self.assertAlmostEqual(r['near_wall_length_fraction'],1/3)
    def test_threshold_changes_measured_topology_without_changing_data(self):
        d=np.array([1.,.5,1.]);r=vein_metrics(self.xy,self.edges,d,self.seed,'straight',1.);self.assertEqual(r['components'],2);self.assertEqual(r['length'],20);self.assertEqual(r['inoculum_attached_fraction'],.5);np.testing.assert_array_equal(d,[1,.5,1])
    def test_no_veins_has_no_connectivity_or_wall_score(self):
        r=vein_metrics(self.xy,self.edges,np.zeros(3),self.seed,'straight');self.assertEqual(r['components'],0);self.assertIsNone(r['inoculum_attached_fraction']);self.assertIsNone(r['mean_wall_clearance'])
    def test_inoculum_free_network(self):
        r=vein_metrics(self.xy,self.edges,np.ones(3),np.zeros(5,dtype=bool),'straight');self.assertEqual(r['inoculum_attached_fraction'],0)
if __name__=='__main__':unittest.main()
