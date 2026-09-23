import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from integration.private_real_media import authorize_private_real_media,validate_private_execution
ROOT=Path(__file__).resolve().parents[2]
REC=json.loads((ROOT/'p0e4/evidence/post_ready_v01/RAW_INGEST_RECONCILIATION_V01.json').read_text())
EVENT={'event_id':'PRIVATE_REAL_MEDIA_ACCEPTANCE_GO_V01','event_type':'NITIN_PRIVATE_REAL_MEDIA_ACCEPTANCE_AUTHORIZATION',
'scope':'AAKHRI_ISHQ_BOUND_RAW_AUDIO_PRIVATE_E2E','output_class':'PRIVATE_LOCAL_REVIEW_ONLY',
'allowed_surfaces':['LOCAL_DAVINCI_RESOLVE','GEMINI_PRIVATE_QC','CLAUDE_PRIVATE_TRANSLATION'],
'forbidden_operations':['PUBLICATION','PRODUCTION_DEPLOYMENT','LIVE_MAKE_CUTOVER','SHARED_DRIVE_MUTATION','INFER_NITIN_APPROVAL'],
'production_deployment_authorized':False,'publication_authorized':False,'first_real_poster':'PAUSED_BY_NITIN','source_statement':'explicit'}

class PrivateRealMedia(unittest.TestCase):
 def test_private_authority_is_distinct_from_deployment(self):
  c=authorize_private_real_media(REC,EVENT)
  self.assertEqual(c['status'],'READY_FOR_PRIVATE_REAL_MEDIA_EXECUTION')
  self.assertFalse(c['production_deployment_authorized']);self.assertFalse(c['publication_authorized'])
 def test_every_authority_drift_fails_closed(self):
  for key,value in [('production_deployment_authorized',True),('publication_authorized',True),('first_real_poster','ACTIVE'),('scope','PRODUCTION')]:
   e=copy.deepcopy(EVENT);e[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):authorize_private_real_media(REC,e)
 def test_bound_pair_required(self):
  r=copy.deepcopy(REC);r['authoritative_audio']=None
  with self.assertRaises((ValueError,TypeError)):authorize_private_real_media(r,EVENT)
 def test_execution_validation(self):
  c=authorize_private_real_media(REC,EVENT); hashes={x['role']:x['sha256'] for x in c['inputs']}
  receipt={'schema':'PRIVATE_REAL_MEDIA_EXECUTION_RECEIPT_V01','schema_version':1,'run_id':'r','mode':'PRIVATE_LOCAL_REVIEW_ONLY','project_name':'P','input_hashes':hashes,
   'output':{'uri':'/x/.local/private-real-media-v01/a.mp4','sha256':'a'*64,'bytes':1,'classification':'PRIVATE_LOCAL_REVIEW_ONLY'},
   'camera_audio_included':False,'authoritative_audio_included':True,'source_mutations':0,'production_deployment_authorized':False,'publication_authorized':False,'first_real_poster':'PAUSED_BY_NITIN','render_status':'COMPLETE'}
  self.assertEqual(validate_private_execution(c,receipt)['status'],'TECHNICAL_GREEN_EXTERNAL_QC_PENDING')
  for path,value in [('camera_audio_included',True),('production_deployment_authorized',True),('render_status','FAILED')]:
   x=copy.deepcopy(receipt);x[path]=value
   with self.subTest(path=path),self.assertRaises(ValueError):validate_private_execution(c,x)

if __name__=='__main__':unittest.main()
