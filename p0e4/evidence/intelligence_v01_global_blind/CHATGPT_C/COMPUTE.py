import json, csv, hashlib
from pathlib import Path
from collections import Counter
p=Path(__file__).resolve().parent
d=json.loads((p/'RAW_DATASET.json').read_text())
s=json.loads((p/'SOURCES_PROVENANCE.json').read_text())
source_ids={x['source_id'] for x in s}
ids={x['song_id'] for x in d['songs']}
assert len(ids)==len(d['songs'])
assert len({x['observation_id'] for x in d['observations']})==len(d['observations'])
for o in d['observations']:
    assert o['song_id'] in ids and o['source_id'] in source_ids
for row in d['songs']:
    for field,value in row['musical_features'].items():
        if value is not None:
            prov=row['feature_provenance'][field]
            assert prov['source_id'] in source_ids and prov['url'] and prov['version']
with (p/'RAW_DATASET.csv').open('w',newline='') as f:
    rows=[]
    for row in d['songs']:
        flat={k:v for k,v in row.items() if k not in ['musical_features','feature_provenance']}
        flat.update(row['musical_features'])
        flat['feature_provenance_json']=json.dumps(row['feature_provenance'],ensure_ascii=False)
        rows.append(flat)
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
with (p/'SUCCESS_OBSERVATIONS.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=d['observations'][0].keys());w.writeheader();w.writerows(d['observations'])
fields=list(d['songs'][0]['musical_features'])
summary={'unique_songs':len(ids),'success_observations':len(d['observations']),'cohorts':{},'feature_coverage_unique_entities':{},'own_data_n':len(d['UNCHAINED_NITIN_OWN_DATA'])}
for field in fields:
    n=sum(x['musical_features'][field] is not None for x in d['songs'])
    summary['feature_coverage_unique_entities'][field]={'known_n':n,'missing_n':len(ids)-n,'total_n':len(ids)}
for cohort in sorted({o['cohort'] for o in d['observations']}):
    obs=[o for o in d['observations'] if o['cohort']==cohort]
    cids={o['song_id'] for o in obs}; rows=[x for x in d['songs'] if x['song_id'] in cids]
    summary['cohorts'][cohort]={'observations_n':len(obs),'unique_songs_n':len(cids),'period_counts':dict(Counter(o['period'] for o in obs)),'feature_known_n':{f:sum(x['musical_features'][f] is not None for x in rows) for f in fields},'film_known_true_n':sum(x['film_status'] is True for x in rows),'film_unknown_n':sum(x['film_status'] is None for x in rows)}
(p/'COMPUTED_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))

