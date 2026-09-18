from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from integration.fixtures import chain, AT
from integration.ingest import inspect_inbox

class IngestTests(unittest.TestCase):
    def test_hash_bound_drop_folder_and_changed_source(self):
        c,p,q,blobs,receipts=chain()
        manifest={'schema_version':1,'content_id':c['content_id'],'received_at':AT,'assets':c['inputs']}
        with tempfile.TemporaryDirectory() as d:
            for uri,data in blobs.items():
                path=Path(d)/uri;path.parent.mkdir(exist_ok=True);path.write_bytes(data)
            result=inspect_inbox(manifest,d)
            self.assertEqual(result['status'],'INGEST_VERIFIED_BYTES')
            self.assertEqual(result['technical_decode'],'NOT_PERFORMED')
            (Path(d)/'fixture/audio').write_bytes(b'wrong audio')
            with self.assertRaises(ValueError):inspect_inbox(manifest,d)
    def test_master_cannot_replace_raw(self):
        c,p,q,blobs,receipts=chain();c['inputs'][0]['role']='master'
        with tempfile.TemporaryDirectory() as d:
            for uri,data in blobs.items():
                path=Path(d)/uri;path.parent.mkdir(exist_ok=True);path.write_bytes(data)
            with self.assertRaises(ValueError):inspect_inbox({'schema_version':1,'content_id':c['content_id'],'received_at':AT,'assets':c['inputs']},d)
if __name__=='__main__':unittest.main()
