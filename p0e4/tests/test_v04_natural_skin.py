import unittest
from multitake.v04_natural_skin import new_transform,v03_transform
class V04NaturalSkinTest(unittest.TestCase):
 def test_bounded_chroma_only(self):
  x=(.72,.42,.30);base=v03_transform(x);y=new_transform(x);lum=lambda v:.2627*v[0]+.6780*v[1]+.0593*v[2]
  self.assertAlmostEqual(lum(base),lum(y),places=6);self.assertLess(max(y)-min(y),max(base)-min(base));self.assertTrue(all(0<=v<=1 for v in y))
if __name__=='__main__':unittest.main()
