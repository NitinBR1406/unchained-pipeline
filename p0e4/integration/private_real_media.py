"""Private real-media acceptance is a bounded local test authority, never deployment."""
from copy import deepcopy
from .contracts import keys, require, sha, text


def authorize_private_real_media(reconciliation, event):
    require(reconciliation['schema']=='RAW_INGEST_RECONCILIATION_V01','reconciliation schema')
    require(reconciliation['full_ingest_status']=='RAW_AUDIO_PAIR_IDENTITY_BOUND_BYTES_HASHED','bound pair required')
    require(reconciliation['source_mutations']==0 and reconciliation['audio_source_mutations']==0,'source mutation')
    require(reconciliation['production_deployment_authorized'] is False,'production authority drift')
    require(reconciliation['publication_authorized'] is False,'publication authority drift')
    keys(event,'event_id event_type scope output_class allowed_surfaces forbidden_operations '
               'production_deployment_authorized publication_authorized first_real_poster source_statement')
    require(event['event_type']=='NITIN_PRIVATE_REAL_MEDIA_ACCEPTANCE_AUTHORIZATION','event type')
    require(event['scope']=='AAKHRI_ISHQ_BOUND_RAW_AUDIO_PRIVATE_E2E','scope')
    require(event['output_class']=='PRIVATE_LOCAL_REVIEW_ONLY','output class')
    require(event['allowed_surfaces']==['LOCAL_DAVINCI_RESOLVE','GEMINI_PRIVATE_QC','CLAUDE_PRIVATE_TRANSLATION'],'surface drift')
    required={'PUBLICATION','PRODUCTION_DEPLOYMENT','LIVE_MAKE_CUTOVER','SHARED_DRIVE_MUTATION','INFER_NITIN_APPROVAL'}
    require(set(event['forbidden_operations'])==required,'forbidden operations drift')
    require(event['production_deployment_authorized'] is False,'production authority cannot be inferred')
    require(event['publication_authorized'] is False,'publication authority cannot be inferred')
    require(event['first_real_poster']=='PAUSED_BY_NITIN','poster gate drift')
    raw=deepcopy(reconciliation['raw']); audio=deepcopy(reconciliation['authoritative_audio'])
    sha(raw['sha256']);sha(audio['sha256']);text(raw['path']);text(audio['uri'])
    return {'schema':'PRIVATE_REAL_MEDIA_ACCEPTANCE_V01','schema_version':1,
            'content_id':reconciliation['content_id'],'authorization_event_id':event['event_id'],
            'scope':event['scope'],'mode':'PRIVATE_NON_PUBLISHING_REAL_MEDIA_E2E',
            'inputs':[{'role':'raw_video','uri':raw['path'],'sha256':raw['sha256'],'bytes':raw['bytes']},audio],
            'allowed_surfaces':deepcopy(event['allowed_surfaces']),
            'forbidden_operations':sorted(required),'output_class':event['output_class'],
            'acceptance_checks':['INPUT_BYTES_REHASH_MATCH','PRIVATE_RESOLVE_PROJECT_NEW_NO_OVERWRITE',
              'BOUND_AUDIO_REPLACES_CAMERA_AUDIO','PRIVATE_RENDER_COMPLETE','OUTPUT_BYTES_HASHED',
              'OUTPUT_TECHNICAL_DECODE','GEMINI_INDEPENDENT_QC_OR_EXPLICIT_UNAVAILABLE',
              'CLAUDE_TRANSLATION_OR_EXPLICIT_UNAVAILABLE','SOURCE_BYTES_UNCHANGED'],
            'status':'READY_FOR_PRIVATE_REAL_MEDIA_EXECUTION',
            'production_deployment_authorized':False,'publication_authorized':False,
            'first_real_poster':'PAUSED_BY_NITIN','source_mutations':0}


def validate_private_execution(contract, receipt):
    require(contract['schema']=='PRIVATE_REAL_MEDIA_ACCEPTANCE_V01','contract schema')
    require(contract['status']=='READY_FOR_PRIVATE_REAL_MEDIA_EXECUTION','contract not ready')
    require(contract['production_deployment_authorized'] is False and contract['publication_authorized'] is False,'authority drift')
    keys(receipt,'schema schema_version run_id mode project_name input_hashes output '
                 'camera_audio_included authoritative_audio_included source_mutations '
                 'production_deployment_authorized publication_authorized first_real_poster render_status')
    require(receipt['schema']=='PRIVATE_REAL_MEDIA_EXECUTION_RECEIPT_V01' and receipt['schema_version']==1,'receipt schema')
    require(receipt['mode']=='PRIVATE_LOCAL_REVIEW_ONLY','execution mode')
    expected={x['role']:x['sha256'] for x in contract['inputs']}
    require(receipt['input_hashes']==expected,'input lineage drift')
    require(receipt['camera_audio_included'] is False,'camera audio must be excluded')
    require(receipt['authoritative_audio_included'] is True,'authoritative audio missing')
    require(receipt['source_mutations']==0,'source mutation')
    require(receipt['production_deployment_authorized'] is False and receipt['publication_authorized'] is False,'authority escalation')
    require(receipt['first_real_poster']=='PAUSED_BY_NITIN','poster gate drift')
    require(receipt['render_status']=='COMPLETE','render incomplete')
    keys(receipt['output'],'uri sha256 bytes classification');sha(receipt['output']['sha256'])
    require(receipt['output']['bytes']>0 and receipt['output']['classification']=='PRIVATE_LOCAL_REVIEW_ONLY','output class')
    require('/.local/private-real-media-v01/' in receipt['output']['uri'],'non-private output path')
    return {'schema':'PRIVATE_REAL_MEDIA_TECHNICAL_ACCEPTANCE_V01','schema_version':1,
            'contract_event_id':contract['authorization_event_id'],'run_id':receipt['run_id'],
            'output':deepcopy(receipt['output']),'status':'TECHNICAL_GREEN_EXTERNAL_QC_PENDING',
            'production_deployment_authorized':False,'publication_authorized':False,
            'first_real_poster':'PAUSED_BY_NITIN'}
