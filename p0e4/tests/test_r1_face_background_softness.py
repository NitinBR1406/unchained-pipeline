import json,tempfile,unittest
from pathlib import Path
from multitake.r1_face_background_softness import new_transform,write_cube,validate_contract
class FaceBackgroundSoftnessTest(unittest.TestCase):
 def test_contract(self):validate_contract(json.loads(Path('p0e4/evidence/r1_highlight_refinement_v02_execution/R1_FACE_BACKGROUND_SOFTNESS_CONTRACT_V02.json').read_text()))
 def test_deterministic_lut(self):
  with tempfile.TemporaryDirectory() as d:
   a=write_cube(Path(d)/'a.cube',9);b=write_cube(Path(d)/'b.cube',9);self.assertEqual(a['sha256'],b['sha256'])
 def test_skin_highlight_softens_without_hue_shift(self):
  src=(.88,.60,.42);out=new_transform(src);self.assertTrue(all(0<=x<=1 for x in out));self.assertLess(sum(out),sum(src));self.assertEqual(max(range(3),key=src.__getitem__),max(range(3),key=out.__getitem__))
 def test_dark_detail_not_crushed_and_neutral_background_calms(self):
  dark=(.10,.09,.08);d=new_transform(dark);self.assertGreater(min(d),0);self.assertLess(max(abs(a-b) for a,b in zip(d,dark)),.03)
  neutral=(.68,.66,.65);n=new_transform(neutral);self.assertLess(sum(n),sum(neutral))
if __name__=='__main__':unittest.main()
