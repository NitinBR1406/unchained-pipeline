import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resolve.local_acceptance import check_root,cut_specs,VERSION

class LocalAcceptanceTests(unittest.TestCase):
    def test_exclusive_cut_bounds(self):
        specs=cut_specs('synthetic',90000)
        self.assertEqual([(x['startFrame'],x['endFrame'],x['recordFrame']) for x in specs],[(0,50,90000),(50,100,90050)])
        self.assertEqual(VERSION,[21,1,0,17,''])
    def test_production_name_rejected_before_connect(self):
        with self.assertRaisesRegex(ValueError,'SYNTHETIC_PROJECT_NAME_REQUIRED'):
            check_root('/tmp/.local/resolve-v163','Aakhri Ishq')
    def test_output_scope_rejected(self):
        with self.assertRaisesRegex(ValueError,'PRIVATE_STAGING_ONLY'):
            check_root('/tmp/public','UNCHAINED_V163_SYNTHETIC_TEST')
    def test_changed_fixture_rejected_before_connect(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'.local/resolve-v163';root.mkdir(parents=True)
            (root/'synthetic.mov').write_bytes(b'private or substituted media')
            with self.assertRaisesRegex(ValueError,'SYNTHETIC_FIXTURE_SHA_MISMATCH'):
                check_root(root,'UNCHAINED_V163_SYNTHETIC_TEST')

if __name__=='__main__':unittest.main()
