import tempfile,unittest,wave
from pathlib import Path
import numpy as np
from multitake.kick_snare_discovery import robust_z,sha256,peak_indices
class DiscoveryTest(unittest.TestCase):
 def test_robust_z_and_hash(self):
  z=robust_z(np.array([1.,1.,1.,10.]));self.assertGreater(z[-1],1)
  self.assertEqual(peak_indices(np.array([0.,3.,0.,2.,0.]),1,2).tolist(),[1,3])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x';p.write_bytes(b'x');self.assertEqual(len(sha256(p)),64)
if __name__=='__main__':unittest.main()
