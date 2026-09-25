import json
import tempfile
import unittest
from pathlib import Path

from multitake.r1_framed_color_study import VARIANTS, transform, validate_contract, write_cube


class R1FramedColorStudyTest(unittest.TestCase):
    def test_contract_and_fail_closed(self):
        p = Path("p0e4/evidence/r1_framed_study_v164_execution/R1_FRAMED_HLG_EXECUTION_CONTRACT_V01.json")
        validate_contract(json.loads(p.read_text()))

    def test_luma_is_preserved_and_output_is_bounded(self):
        samples = [(0,0,0), (.12,.09,.07), (.72,.46,.31), (.4,.4,.4), (.9,.7,.2), (1,1,1)]
        for v in VARIANTS:
            for rgb in samples:
                out = transform(rgb, v)
                self.assertTrue(all(0 <= x <= 1 for x in out))
                y0 = sum(a*b for a,b in zip((.2627,.6780,.0593),rgb))
                y1 = sum(a*b for a,b in zip((.2627,.6780,.0593),out))
                self.assertAlmostEqual(y0,y1,places=7)

    def test_deterministic_lut(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/"a.cube"; b=Path(d)/"b.cube"
            ra=write_cube(a,VARIANTS[-1],17); rb=write_cube(b,VARIANTS[-1],17)
            self.assertEqual(ra["sha256"],rb["sha256"])


if __name__ == "__main__": unittest.main()
