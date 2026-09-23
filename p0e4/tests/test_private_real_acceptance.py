import tempfile,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resolve.private_real_acceptance import check_inputs
class PrivateHarness(unittest.TestCase):
 def test_refuses_non_private_root_and_bad_project(self):
  with self.assertRaises(ValueError):check_inputs('/x/a','/x/b','/tmp/out','UNCHAINED_AKI_PRIVATE_V01_RUN')
  with self.assertRaises(ValueError):check_inputs('/x/a','/x/b','/tmp/.local/private-real-media-v01','bad')
if __name__=='__main__':unittest.main()
