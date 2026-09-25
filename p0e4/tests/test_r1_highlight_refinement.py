import json,tempfile,unittest
from pathlib import Path
from multitake.r1_highlight_refinement import revised_transform,validate_contract,write_cube


class HighlightRefinementTest(unittest.TestCase):
    def test_contract(self):
        validate_contract(json.loads(Path('p0e4/evidence/r1_highlight_refinement_v01_execution/R1_HIGHLIGHT_BACKGROUND_REFINEMENT_CONTRACT_V01.json').read_text()))
    def test_shadows_stable_highlights_softened_and_bounded(self):
        shadow=(.18,.14,.11); highlight=(.96,.82,.72)
        so=revised_transform(shadow); hi=revised_transform(highlight)
        ys=lambda x:.2627*x[0]+.678*x[1]+.0593*x[2]
        self.assertLess(abs(ys(so)-ys(shadow)),.001)
        self.assertLess(ys(hi),ys(highlight)); self.assertLessEqual(ys(highlight)-ys(hi),.021)
        self.assertTrue(all(0<=x<=1 for x in so+hi))
    def test_lut_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            a=write_cube(Path(d)/'a.cube',17);b=write_cube(Path(d)/'b.cube',17);self.assertEqual(a['sha256'],b['sha256'])

if __name__=='__main__':unittest.main()
