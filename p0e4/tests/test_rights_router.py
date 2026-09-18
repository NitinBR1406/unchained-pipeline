import base64
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from integration import contracts as c, rights as r
from integration.fixtures import chain, AT
from integration.pipeline import prepare_release
import handoff as h


class RightsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Path(self.tmp.name)/'rights.json'
        self.key=Ed25519PrivateKey.generate() # ephemeral TEST_ONLY reviewer, never Nitin
        self.keys={'TEST_ONLY':self.key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()}
        self.creative,self.production,self.qc,self.blobs,self.receipts=chain()
        self.req={'content_id':'TEST_ONLY_GOLDEN','asset_sha256':self.production['payload']['outputs'][0]['sha256'],
                  'platform':'youtube_hero','territories':['NL'],'account_id':'TEST_ONLY','use':'organic','monetized':False,'at':AT}
        self.review={'schema_version':1,'grant_id':'TEST_ONLY','content_id':self.req['content_id'],
            'asset_sha256':self.req['asset_sha256'],'platforms':['youtube_hero'],'territories':['NL'],
            'account_ids':['TEST_ONLY'],'uses':['organic'],'monetized':False,
            'rights':{k:'CLEARED' for k in r.RIGHTS},'valid_from':'2026-09-18T00:00:00Z',
            'valid_until':'2026-09-19T00:00:00Z','revoked':False,'evidence_refs':self.creative['evidence_refs'],
            'reviewed_at':'2026-09-18T00:00:00Z'}
        self.save()

    def signed(self):
        return {'review':self.review,'key_id':'TEST_ONLY','signature':base64.b64encode(self.key.sign(c.canonical(self.review))).decode()}

    def save(self):self.store.write_text(json.dumps([self.signed()]))
    def evaluate(self):return r.evaluate(self.req,self.store,self.keys,self.blobs.__getitem__)
    def release(self, verifier=None):
        return prepare_release(self.creative,self.production,self.qc,resolver=self.blobs.__getitem__,
            authenticated_receipts=self.receipts,rights_store=self.store,reviewer_keys=self.keys,
            scope={k:self.req[k] for k in ('territories','account_id','use','monetized')},at=AT,
            final_review_verifier=verifier)

    def test_signed_scoped_rights_do_not_authorize_publish(self):
        result=self.evaluate();self.assertTrue(result['pass']);self.assertFalse(result['publish_authorized'])
        self.assertEqual(self.release()['status'],'BLOCKED')

    def test_revocation_reload_and_expiry(self):
        self.assertTrue(self.evaluate()['pass'])
        self.review['revoked']=True;self.save();self.assertFalse(self.evaluate()['pass'])
        self.review['revoked']=False;self.save();self.assertTrue(self.evaluate()['pass'])
        self.req['at']=self.review['valid_until'];self.assertFalse(self.evaluate()['pass'])

    def test_no_implicit_scope_or_boolean_coercion(self):
        for k,v in [('content_id','other'),('asset_sha256','a'*64),('platform','x'),('territories',['US']),
                    ('account_id','other'),('use','paid'),('monetized',True),('monetized','false'),
                    ('at','2026-09-17T00:00:00Z'),('platform','unknown'),('territories',[])]:
            old=copy.deepcopy(self.req);self.req[k]=v
            with self.subTest(k=k,v=v):self.assertFalse(self.evaluate()['pass'])
            self.req=old

    def test_malformed_forged_duplicate_or_missing_fail_closed(self):
        for records in ({'status':'RIGHTS_PASS'},[],[{'pass':True}], [self.signed(),self.signed()]):
            self.store.write_text(json.dumps(records));self.assertFalse(self.evaluate()['pass'])
        record=self.signed();record['review']['platforms'].append('x')
        self.store.write_text(json.dumps([record]));self.assertFalse(self.evaluate()['pass'])
        self.store.write_text('broken');self.assertFalse(self.evaluate()['pass'])
        self.store.unlink();self.assertFalse(self.evaluate()['pass'])

    def test_unknown_reviewer_tampered_evidence_incomplete_rights(self):
        self.keys={};self.assertFalse(self.evaluate()['pass'])
        self.setUp();self.blobs['fixture/evidence']=b'changed';self.assertFalse(self.evaluate()['pass'])
        self.setUp();self.review['rights']['composition']='NOT_APPLICABLE';self.save();self.assertFalse(self.evaluate()['pass'])
        self.review['rights']['composition']='UNKNOWN';self.save();self.assertFalse(self.evaluate()['pass'])

    def test_positive_test_only_chain_stops_at_human_gate(self):
        # Explicit isolated verifier double; never persisted as real approval.
        result=self.release(lambda content,sha:content=='TEST_ONLY_GOLDEN' and sha==c.digest(c.canonical(self.production)))
        self.assertEqual(result['status'],'WAITING_FOR_NITIN_PUBLISH_APPROVAL')
        self.assertTrue(result['publish_ready']);self.assertTrue(result['hard_stop'])
        self.assertFalse(result['publication_authorized']);self.assertEqual(result['external_side_effect_count'],0)
        with tempfile.TemporaryDirectory() as directory:
            calls=[]
            def executor(task,job,now):
                calls.append(task['task_id']);return {'status':'OK','evidence':['TEST_ONLY']}
            loop=h.DurableControlLoop(directory,keyring={},executor=executor)
            loop.backlog.tasks=[h.task('TEST_ONLY_RELEASE',1,c.digest(c.canonical(result)),'NITIN_PUBLISH_APPROVAL'),
                                h.task('TEST_ONLY_INDEPENDENT_READY',2,'test')]
            loop.backlog.save();loop.run()
            self.assertEqual(loop.backlog.by_id('TEST_ONLY_RELEASE')['status'],'WAITING_FOR_NITIN')
            self.assertEqual(calls,['TEST_ONLY_INDEPENDENT_READY'])
            self.assertEqual(loop.master_state()['approvals'],{})
            first=loop.master_state();loop.run();self.assertEqual(first,loop.master_state())

    def test_failure_cannot_become_publish_ready(self):
        self.review['revoked']=True;self.save()
        self.assertFalse(self.release(lambda *args:True)['publish_ready'])
        self.receipts={};self.assertFalse(self.release(lambda *args:True)['publish_ready'])

if __name__=='__main__':unittest.main()
