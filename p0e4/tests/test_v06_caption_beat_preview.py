import unittest
from resolve.aakhri_v06_caption_beat_preview_v01 import START,END,BEATS,V06_SHA
class PreviewContractTest(unittest.TestCase):
 def test_scope(self):
  self.assertEqual((START,END),(72000,96000));self.assertEqual(BEATS,(72760,78760,92760));self.assertEqual(len(V06_SHA),64)
if __name__=='__main__':unittest.main()
