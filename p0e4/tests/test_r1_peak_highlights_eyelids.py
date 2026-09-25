import json,tempfile,unittest
from pathlib import Path
from multitake.r1_peak_highlights_eyelids import new_transform,write_cube,validate_contract
class PeakHighlightsEyelidsTest(unittest.TestCase):
 def test_contract(self):validate_contract(json.loads(Path('p0e4/evidence/r1_highlight_refinement_v03_execution/R1_PEAK_HIGHLIGHTS_EYELIDS_CONTRACT_V03.json').read_text()))
 def test_deterministic_lut(self):
  with tempfile.TemporaryDirectory() as d:
   a=write_cube(Path(d)/'a.cube',9);b=write_cube(Path(d)/'b.cube',9);self.assertEqual(a['sha256'],b['sha256'])
 def test_peak_skin_softens_more_than_midtone(self):
  mid=(.60,.41,.30);peak=(.92,.67,.48);m=new_transform(mid);p=new_transform(peak)
  self.assertTrue(all(0<=x<=1 for x in m+p));self.assertGreater(sum(peak)-sum(p),sum(mid)-sum(m));self.assertEqual(max(range(3),key=peak.__getitem__),max(range(3),key=p.__getitem__))
 def test_dark_detail_and_neutral_background_remain_stable(self):
  for src in ((.10,.09,.08),(.62,.61,.60)):
   out=new_transform(src);self.assertLess(max(abs(a-b) for a,b in zip(out,src)),.08)
if __name__=='__main__':unittest.main()
