import unittest
from multitake.v06_softness import new_transform
from multitake.v05_soft_skin_lighting import new_transform as v05
class V06SoftnessTest(unittest.TestCase):
 def test_bright_skin_is_slightly_softer(self):
  x=(.92,.72,.62);a=v05(x);b=new_transform(x);lum=lambda v:.2627*v[0]+.678*v[1]+.0593*v[2]
  self.assertLess(lum(b),lum(a));self.assertLessEqual(lum(a)-lum(b),.013);self.assertTrue(all(0<=q<=1 for q in b))
 def test_neutral_and_dark_are_unchanged(self):
  for x in ((.3,.3,.3),(.18,.10,.08)):self.assertEqual(new_transform(x),v05(x))
if __name__=='__main__':unittest.main()
