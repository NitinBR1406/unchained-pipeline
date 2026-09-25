import unittest
from multitake.v05_soft_skin_lighting import new_transform
from multitake.v04_natural_skin import new_transform as v04
class V05SoftLightingTest(unittest.TestCase):
 def test_bright_skin_softened_bounded(self):
  x=(.92,.72,.62);a=v04(x);b=new_transform(x);lum=lambda v:.2627*v[0]+.678*v[1]+.0593*v[2]
  self.assertLess(lum(b),lum(a));self.assertLessEqual(lum(a)-lum(b),.021)
  self.assertLess(max(b)-min(b),max(a)-min(a));self.assertTrue(all(0<=v<=1 for v in b))
 def test_neutral_and_dark_are_unchanged(self):
  for x in ((.3,.3,.3),(.18,.10,.08)):
   self.assertEqual(new_transform(x),v04(x))
if __name__=='__main__':unittest.main()
