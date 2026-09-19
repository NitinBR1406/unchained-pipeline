"""Independent metadata review priorities; never infer musical readiness."""
from catalog.engine import compile_catalog,stable
from integration.contracts import canonical,digest

def technical_review(inventory):
    catalog=compile_catalog(inventory)['MASTER_CATALOG_V01']
    tasks=[]
    for row in catalog['records']:
        assets=[a for a in row['assets'] if a['kind']!='DIRECTORY_OBSERVED']
        masters=[a['asset_id'] for a in assets if 'master' in a['candidate_role_hints']]
        archives=[a['asset_id'] for a in assets if a['relative_path'].lower().endswith('.zip')]
        for reason,ids,gate in [('VERIFY_MEDIA_BYTES',[a['asset_id'] for a in assets if a['sha256'] is None],'WAITING_FOR_FILE_READ_SETUP'),('REVIEW_MASTER_VERSION_CANDIDATES',masters if len(masters)>1 else [],'WAITING_FOR_NITIN'),('INSPECT_ARCHIVE_WITHOUT_EXECUTION',archives,'WAITING_FOR_FILE_READ_SETUP')]:
            if ids:tasks.append(dict(task_id=stable('catalog_review',[row['catalog_source_id'],reason]),catalog_source_id=row['catalog_source_id'],reason=reason,asset_ids=ids,status=gate,source_ref=row['source_ref'],candidate_hints_only=True))
    return dict(schema='CATALOG_TECHNICAL_REVIEW_QUEUE',schema_version=1,inventory_sha256=digest(canonical(inventory)),tasks=tasks,production_status_changed=False,source_assets_mutated=False,publication_authorized=False)
