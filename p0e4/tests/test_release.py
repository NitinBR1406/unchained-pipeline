import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import release as r
import handoff as h


def media():
    return {'assets':[{'file_id':r.MASTER_ID,'drive_id':r.DRIVE,
        'name':'AKI_SHOTSTACK_PRESENTATION_MASTER_V01.mp4','sha256':'a'*64,
        'size_bytes':10,'probe':{'duration':208.6},'technical_decode_pass':True,
        'bytes_unchanged':True,'full_av_decode_exit_code':0}]}


class ReleaseTests(unittest.TestCase):
    def test_real_governance_not_changed_by_verified_bytes(self):
        p=r.build(media())
        self.assertFalse(p['publish_ready']); self.assertEqual(p['status'],'BLOCKED')
        self.assertEqual(len(p['packages']),7)
        self.assertTrue(all(x['caption'] and x['title'] for x in p['packages']))
        self.assertTrue(all(x['selected_asset'] is None for x in p['packages']))
        self.assertIn('FINAL_VIDEO_APPROVAL_BINDING_REQUIRED',p['blockers'])
        self.assertEqual(p['rights_request']['status'],'RIGHTS_HOLD')
        self.assertFalse(p['approval_binding_request']['approval_created'])

    def test_asset_forgery_rejected(self):
        for k,v in [('drive_id','other'),('technical_decode_pass','true'),('bytes_unchanged',False),
                    ('size_bytes',True),('sha256','placeholder'),('file_id','other'),
                    ('full_av_decode_exit_code',1),('name','wrong.mp4')]:
            m=media(); m['assets'][0][k]=v
            with self.subTest(k=k), self.assertRaises(ValueError): r.build(m)

    def test_missing_duplicate_master_rejected(self):
        with self.assertRaises(ValueError): r.build({'assets':[]})
        m=media(); m['assets'].append(copy.deepcopy(m['assets'][0]))
        with self.assertRaises(ValueError): r.build(m)

    def test_retry_conflict_unknown_task_and_input_binding(self):
        p=r.build(media()); ih=h.digest(h.canonical(p))
        with tempfile.TemporaryDirectory() as d:
            executor=r.ReleaseExecutor(d,p); t=h.task('AKI_PACKAGE_DRAFT',1,ih)
            a=executor(t,'job',1); f=Path(d)/'AKI_PACKAGE_DRAFT.json'; stamp=f.stat().st_mtime_ns
            self.assertEqual(a,executor(t,'job',2)); self.assertEqual(stamp,f.stat().st_mtime_ns)
            with self.assertRaises(ValueError): executor(t,'different-job',3)
            with self.assertRaises(PermissionError): executor(h.task('AKI_RELEASE',1,ih),'job',1)
            with self.assertRaises(ValueError): executor(h.task('AKI_PACKAGE_DRAFT',1,'drift'),'job',1)

    def test_actual_loop_completes_all_safe_work_and_replays(self):
        p=r.build(media())
        with tempfile.TemporaryDirectory() as d:
            loop=h.DurableControlLoop(d,keyring={},executor=r.ReleaseExecutor(Path(d)/'effects',p))
            r.seed(loop,p); loop.run()
            self.assertEqual(loop.backlog.summary()['completed'],4)
            self.assertEqual(loop.backlog.by_id('AKI_RELEASE')['status'],'BLOCKED')
            self.assertEqual(loop.master_state()['approvals'],{})
            self.assertTrue(h.verify_replay(loop.ledger,loop.persisted_state(),keyring={})[0])
            prior=loop.ledger.read_all(); loop.run(); self.assertEqual(prior,loop.ledger.read_all())
            changed=copy.deepcopy(p); changed['status']='different'
            with self.assertRaises(ValueError): r.seed(loop,changed)

if __name__=='__main__': unittest.main()
