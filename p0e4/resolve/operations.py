"""Exact plan-only operation supplement; no Resolve API or arbitrary code.

Coordinates use integer millionths of output width/height. Scale is millionths
of unity. Time is integer frames in the base plan's output frame rate. Missing
capability/license evidence blocks execution even when parameter validation passes.
"""
from copy import deepcopy
from integration.contracts import canonical,digest,keys,require,sha,text


def integer(x,lo,hi):require(type(x) is int and lo<=x<=hi,'integer parameter out of range')


def binding(ref):
 keys(ref,'uri sha256');text(ref['uri']);sha(ref['sha256'])


def point(p):
 keys(p,'x_millionths y_millionths');integer(p['x_millionths'],0,1000000);integer(p['y_millionths'],0,1000000)


def compile_operations(base,spec):
 keys(spec,'schema schema_version base_plan_sha256 operations')
 require(spec['schema']=='RESOLVE_OPERATION_DETAILS' and type(spec['schema_version']) is int and spec['schema_version']==1,'operation schema')
 require(spec['base_plan_sha256']==digest(canonical(base)),'base plan SHA mismatch')
 require(base['schema']=='RESOLVE_EXECUTION_PLAN' and base['status']=='PLAN_ONLY_EXECUTION_BLOCKED' and base['resolve_execution_proven'] is False,'base scope')
 require(base['production_deployment_authorized'] is False and base['publication_authorized'] is False and base['first_real_poster']=='PAUSED_BY_NITIN','base governance')
 require(type(spec['operations']) is list,'operations list')
 jobs={j['package_id']:j for j in base['jobs']};seen=set();out=[]
 for op in spec['operations']:
  keys(op,'operation_id package_id kind start_frame end_frame_exclusive performer_obscured parameters evidence_ref')
  text(op['operation_id']);require(op['operation_id'] not in seen,'duplicate operation ID');seen.add(op['operation_id'])
  require(op['package_id'] in jobs,'unknown package');job=jobs[op['package_id']]
  performance=job['performance'];require(performance['visible_ms']*5>=performance['duration_ms']*4,'80_PERCENT_PERFORMANCE_RULE')
  end=job['cuts'][-1]['end_frame_exclusive'];start,stop=op['start_frame'],op['end_frame_exclusive']
  integer(start,0,end-1);integer(stop,start+1,end)
  require(op['performer_obscured'] is False,'obscuring operations forbidden')
  binding(op['evidence_ref']);kind=op['kind'];p=op['parameters'];blockers=['INSTALLATION_AND_OPERATION_CAPABILITY_SMOKE_REQUIRED','AUTHENTICATED_VISIBILITY_QC_REQUIRED']
  if kind=='cut':
   keys(p,'cut_frames');require(type(p['cut_frames']) is list and bool(p['cut_frames']),'cut points required')
   require(p['cut_frames']==sorted(set(p['cut_frames'])),'duplicate/unsorted cuts')
   for f in p['cut_frames']:integer(f,start+1,stop-1)
  elif kind=='reframe':
   keys(p,'left_millionths top_millionths right_millionths bottom_millionths')
   for v in p.values():integer(v,0,1000000)
   require(p['left_millionths']<p['right_millionths'] and p['top_millionths']<p['bottom_millionths'],'empty crop')
  elif kind in ('zoom','push_in','shake'):
   keys(p,'keyframes interpolation');require(p['interpolation'] in ('LINEAR','HOLD'),'unsupported interpolation')
   require(type(p['keyframes']) is list and len(p['keyframes'])>=2,'explicit trajectory required')
   frames=[];scales=[]
   for k in p['keyframes']:
    keys(k,'frame scale_millionths center');integer(k['frame'],start,stop-1);integer(k['scale_millionths'],1000000,4000000);point(k['center']);frames.append(k['frame']);scales.append(k['scale_millionths'])
   require(frames==sorted(set(frames)) and frames[0]==start and frames[-1]==stop-1,'trajectory bounds/order')
   if kind=='push_in':require(scales==sorted(scales) and scales[-1]>scales[0],'push-in must increase scale')
   # Shake is an explicit deterministic trajectory, never a random amplitude knob.
  elif kind in ('caption','text'):
   keys(p,'text style_ref position');text(p['text']);binding(p['style_ref']);point(p['position'])
   blockers.append('STYLE_BYTES_AND_SAFE_AREA_CAPABILITY_REQUIRED')
  elif kind=='transition':
   keys(p,'type duration_frames outgoing_handle_frames incoming_handle_frames')
   require(p['type'] in ('DISSOLVE','WIPE'),'unknown transition')
   integer(p['duration_frames'],1,stop-start);require(p['duration_frames']==stop-start,'transition duration drift')
   integer(p['outgoing_handle_frames'],p['duration_frames'],end);integer(p['incoming_handle_frames'],p['duration_frames'],end)
   blockers.append('SOURCE_HANDLES_AND_TRANSITION_VISIBILITY_NOT_PROVEN')
  elif kind=='effect':
   keys(p,'plugin_id template_ref license_status intent');text(p['plugin_id']);binding(p['template_ref'])
   require(p['license_status'] in ('UNKNOWN','VERIFIED_AVAILABLE'),'license status')
   require(p['intent']=='VISUAL_OVERLAY_NO_BASELINE_CHANGE','baseline-changing effects forbidden')
   blockers.append('PLUGIN_TEMPLATE_INSPECTION_AND_LICENSE_EVIDENCE_REQUIRED')
  else:raise ValueError('UNSUPPORTED_OPERATION_OR_LOCKED_COLOR_AUDIO_CHANGE')
  out.append(dict(operation=deepcopy(op),execution_enabled=False,blockers=blockers))
 return dict(schema='RESOLVE_OPERATION_SUPPLEMENT',schema_version=1,base_plan_sha256=spec['base_plan_sha256'],spec_sha256=digest(canonical(spec)),operations=out,status='VALIDATED_PARAMETERS_EXECUTION_BLOCKED',resolve_execution_proven=False,production_deployment_authorized=False,publication_authorized=False,first_real_poster='PAUSED_BY_NITIN')
