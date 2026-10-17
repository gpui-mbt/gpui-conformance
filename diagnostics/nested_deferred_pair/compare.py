#!/usr/bin/env python3
"""Actual Rust callback-to-box projection versus actual core scene emission.

Tree records establish geometry and lineage only, never callback execution.
Input observations are retained diagnostic differences, not a parity pass.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('nested_deferred_rust_verify', ROOT / 'diagnostics/nested_deferred/verify.py')
baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(baseline)
require = baseline.require
LAYER = 'supplemental-two-level-nested-deferred-native-pair'
CANDIDATE_LAYER = 'compiled-moonbit-nested-deferred'
TOLERANCE = 0
GRID_TOLERANCE = 0
POLICY_SHA256 = '4829c034b9284392bfada6b77546ecdbd5498d74600c7ebf7fdbd3163574e916'


def load_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value): raise ValueError('non-JSON numeric constant: ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def policy():
    path = ROOT / 'diagnostics/nested_deferred_pair/comparison-policy.json'
    require(baseline.digest(path) == POLICY_SHA256, 'pre-candidate comparison policy changed')
    return load_json(path.read_text())


def validate_schema(raw, path):
    try: Draft202012Validator(load_json(path.read_text())).validate(raw)
    except ValidationError as error: raise ValueError('raw schema: ' + error.message) from error


def shape(value, fields, label):
    require(isinstance(value, dict) and set(value) == set(fields), label + ': fields')


def topology(case, stage):
    ids = policy()['candidate_ids']
    parents = {'$host': None, '$ancestor_position': '$host', '$ancestor': '$ancestor_position',
        '$before_position': '$ancestor', 'ordinary.before': '$before_position', '$attachments': '$ancestor', '$reference': '$attachments'}
    for layer in baseline.active_layers(case, stage):
        p=layer['id']
        parents.update({p+'.anchor':'$attachments',p+'.root':p+'.anchor',p+'.$reference':p+'.root',
            p+'.$before_position':p+'.$reference',p+'.before':p+'.$before_position',
            p+'.$after_position':p+'.$reference',p+'.after':p+'.$after_position'})
        if layer['nested_active']: parents.update({p+'.nested.anchor':p+'.root',p+'.nested.root':p+'.nested.anchor'})
    parents.update({'$after_position':'$ancestor','ordinary.after':'$after_position'})
    return {name:{'id':ids[name],'parent':parent} for name,parent in parents.items()}


def box_names(case, stage):
    return ['ordinary.before','ordinary.after'] + [layer['id']+'.'+s for layer in baseline.active_layers(case,stage)
        for s in ('root','before','after',*(['nested.root'] if layer['nested_active'] else []))]


def physical_grid(bounds, scale):
    baseline.physical_grid(bounds,scale)
    require(all(edge*scale == round(edge*scale) for edge in (bounds[0],bounds[1],bounds[0]+bounds[2],bounds[1]+bounds[3])),
        'exact physical grid')


def actual_rust_projection(raw, verified=None):
    """Extract actual recorded callbacks only, never derive schedule/geometry."""
    verified = baseline.verify_observations(raw, raw['input']) if verified is None else verified
    ids=policy()['candidate_ids'];cases=[]
    for raw_case, case in zip(raw['cases'], verified['cases']):
        frames=[]
        for operation in case['operations']:
            for frame in operation['frames']:
                entries=[e for e in raw_case['events'] if e['frame']==frame['frame'] and e['event']['type']=='paint' and baseline.is_box(e['event']['node'])]
                frames.append({'operation':operation['id'],'frame':frame['frame'],'scale_factor':frame['scale_factor'],
                    'box_paint_entries':[{'sequence':e['sequence'],'rust_node':e['event']['node'],'candidate_node':e['event']['node'],
                    'candidate_id':ids[e['event']['node']],'bounds':e['event']['bounds'],'content_mask':e['event']['content_mask']} for e in entries]})
        cases.append({'id':case['id'],'frames':frames})
    return cases


def verify_rust_freeze(raw, verified):
    path=ROOT/'diagnostics/nested_deferred_pair/actual-rust-projection.json'
    require(baseline.digest(path)==policy()['actual_rust_projection_sha256'],'pre-candidate actual Rust projection changed')
    frozen=load_json(path.read_text());expected={c['id']:c for c in frozen['cases']}
    actual=actual_rust_projection(raw,verified)
    require(actual==[expected[c['id']] for c in actual],'fresh actual Rust box projection differs from approved frozen actual oracle')
    return actual


def inspect_scene(commands, nodes, case, stage, scale):
    stack, order, masks = [], [], {}
    boxes = box_names(case, stage)
    for event in commands:
        kind, node = event['kind'], event['node']
        require(node in nodes and event['id'] == nodes[node]['id'], 'emitting scene node identity')
        if kind == 'clip_push':
            physical_grid(event['bounds'], scale)
            stack.append([node, event['bounds']])
        elif kind == 'clip_pop':
            require(event['bounds'] is None and stack and stack.pop()[0] == node, 'scene clip balance')
        else:
            require(kind == 'quad' and node in boxes and node not in order, 'scene exact unique authored boxes')
            baseline.vector(event['bounds'], nodes[node]['bounds'], 'actual scene/tree bounds', 0)
            order.append(node)
            # Intersection derived from actual emitted clip commands, not Rust masks.
            mask = None
            for _, r in stack:
                if mask is None:
                    mask = list(r)
                else:
                    x,y=max(mask[0],r[0]),max(mask[1],r[1])
                    right,bottom=min(mask[0]+mask[2],r[0]+r[2]),min(mask[1]+mask[3],r[1]+r[3])
                    mask=[x,y,max(0,right-x),max(0,bottom-y)]
            masks[node] = {'derived_intersection': mask, 'observed_clip_stack': list(stack)}
    require(not stack and set(order) == set(boxes), 'complete balanced actual scene')
    return order, masks


def verify_frame(entries, case, stage, scale):
    expected, nodes, scenes = topology(case, stage), {}, []
    phase, overflow = 'start', None
    for entry in entries:
        e=entry['event']; kind=e['type']
        if kind in ('frame_start','frame_end'):
            shape(e,['type','scale_factor','window_size'],'frame')
            require(e['scale_factor']==scale and e['window_size']==case['window'],'frame scale/viewport')
            if kind=='frame_start': require(phase=='start','duplicate frame start'); phase='request_start'
            else: require(phase=='scene','incomplete frame'); phase='done'
        elif kind in ('request_start','request_end','prepaint_start'):
            shape(e,['type'],'operation boundary'); require(phase==kind,'candidate production-call order')
            phase={'request_start':'request_end','request_end':'prepaint_start','prepaint_start':'prepaint_end'}[kind]
        elif kind=='prepaint_end':
            shape(e,['type','overflow'],'prepaint result'); require(phase=='prepaint_end' and type(e['overflow']) is bool,'prepaint result')
            overflow,phase=e['overflow'],'nodes'
        elif kind=='node':
            shape(e,['type','node','id','parent','bounds','pointer_events','focusable'],'node')
            name=e['node']; require(phase=='nodes' and name in expected and name not in nodes,'structural node identity/count')
            require(e['id']==expected[name]['id'] and e['parent']==expected[name]['parent'],'structural identity/lineage')
            require(e['pointer_events'] is False and e['focusable'] is False,'authored no-input/focus config')
            physical_grid(e['bounds'],scale); nodes[name]=e
        elif kind=='scene':
            shape(e,['type','kind','node','id','bounds'],'scene')
            require(phase in ('nodes','scene'),'scene lifecycle'); phase='scene'; scenes.append(e)
        else: require(False,'unexpected candidate frame event: '+kind)
    require(phase=='done' and list(nodes)==list(expected),'complete structural preorder/frame')
    baseline.vector(nodes['$host']['bounds'],[0,0,*case['window']],'actual host bounds',0)
    order,masks=inspect_scene(scenes,nodes,case,stage,scale)
    return {'frame':entries[0]['frame'],'scale_factor':scale,'nodes':nodes,'paint_order':order,
            'observed_scene_commands':scenes,'effective_masks':masks,'overflow':overflow}


def decode_transport(raw, token, corpus):
    validate_schema(raw,ROOT/'diagnostics/nested_deferred_pair/raw.schema.json')
    shape(raw,['schema_version','layer','fixture','input','run_token','cases'],'candidate')
    require(raw['schema_version']==1 and raw['layer']==CANDIDATE_LAYER and raw['fixture']=='font-free-two-level-nested-deferred','candidate identity')
    require(isinstance(token,str) and 16<=len(token)<=64 and raw['run_token']==token,'candidate session token')
    require(raw['input']==corpus and [c['id'] for c in raw['cases']]==[c['id'] for c in corpus['cases']],'exact input/case coverage')
    return raw


def verify_candidate(raw, corpus):
    policy(); baseline.validate_scenarios(corpus); decode_transport(raw,raw.get('run_token'),corpus)
    result=[]
    for observed,case in zip(raw['cases'],corpus['cases']):
        events=observed['events']; require([e['sequence'] for e in events]==list(range(len(events))),'candidate event sequence')
        cursor,frame_number=0,0;operations=[]
        for operation,action,stage,scale in baseline.operation_plan(case):
            require(cursor<len(events) and events[cursor]=={'sequence':cursor,'operation':operation,'frame':frame_number,'event':{'type':'operation_start','input':action}},'operation start/input')
            cursor+=1;frames=[];pending=None
            while cursor<len(events) and events[cursor]['event']['type']!='operation_end':
                entry=events[cursor];cursor+=1;kind=entry['event']['type']
                require(entry['operation']==operation,'operation interleaving')
                if kind=='frame_start': require(pending is None,'nested candidate frame');pending=[];frame_number+=1
                require(entry['frame']==frame_number and pending is not None,'frame sequence/event outside frame')
                pending.append(entry)
                if kind=='frame_end': frames.append(verify_frame(pending,case,stage,scale));pending=None
            require(pending is None and frames,'missing required candidate frame')
            require(cursor<len(events) and events[cursor]=={'sequence':cursor,'operation':operation,'frame':frame_number,'event':{'type':'operation_end','scale_factor':scale}},'operation end/scale')
            cursor+=1;operations.append({'id':operation,'frames':frames})
        require(cursor==len(events),'trailing candidate events');result.append({'id':case['id'],'operations':operations})
    return result


def compare_observations(rust,candidate,corpus):
    verified=baseline.verify_observations(rust,corpus);verify_rust_freeze(rust,verified)
    original=verified['cases'];replacement=verify_candidate(candidate,corpus)
    mismatches=[];cases=[];maximum=0.0
    counts={'cases':len(corpus['cases']),'rust_frames':0,'candidate_frames':0,'compared_operations':0,'compared_frame_pairs':0}
    for case,left,right in zip(corpus['cases'],original,replacement):
        operations=[]
        for a_op,b_op in zip(left['operations'],right['operations']):
            require(a_op['id']==b_op['id'],'operation correspondence');op=a_op['id']
            counts['rust_frames']+=len(a_op['frames']);counts['candidate_frames']+=len(b_op['frames']);counts['compared_operations']+=1
            frame_pairs=[]
            # Every actual frame participates; no final-frame-only hiding or scale reuse.
            for a in a_op['frames']:
                projection=a['observed_paintable_box_projection']
                for b in b_op['frames']:
                    counts['compared_frame_pairs']+=1
                    def check(field,x,y,numeric=False):
                        nonlocal maximum
                        if numeric and isinstance(y,list) and len(x)==len(y): maximum=max(maximum,*(abs(i-j) for i,j in zip(x,y)))
                        if x!=y: mismatches.append({'case':case['id'],'operation':op,'rust_frame':a['frame'],'candidate_frame':b['frame'],
                            'field':field,'rust':x,'candidate':y,'error':'exact observed values differ'})
                    check('scale_factor',a['scale_factor'],b['scale_factor']);check('paint_order',projection,b['paint_order'])
                    for name in projection:
                        check('bounds/'+name,a['observed_paint'][name]['bounds'],b['nodes'][name]['bounds'],True)
                        check('effective_mask/'+name,a['observed_paint'][name]['content_mask'],b['effective_masks'][name]['derived_intersection'])
                    frame_pairs.append({'rust_frame':a['frame'],'candidate_frame':b['frame'],'scale_factor':a['scale_factor'],
                        'viewport':[0,0,*case['window']], 'rust_actual_paint_entry_box_projection':projection,
                        'candidate_actual_quad_emission_order':b['paint_order'],
                        'candidate_actual_quad_ids':[b['nodes'][name]['id'] for name in b['paint_order']],
                        'candidate_observed_clip_stacks':b['effective_masks']})
            operations.append({'id':op,'rust_frame_ids':[f['frame'] for f in a_op['frames']],
                'candidate_frame_ids':[f['frame'] for f in b_op['frames']],'compared_frame_pairs':frame_pairs})
        cases.append({'id':case['id'],'operations':operations})
    return {'schema_version':1,'layer':LAYER,'passed':not mismatches,'counts':counts,'cases':cases,'mismatches':mismatches,
        'comparison_policy_sha256':POLICY_SHA256,'numeric_policy':{'absolute_logical_allowance':0,'physical_grid_allowance':0,'maximum_observed_difference':maximum},
        'lifecycle_callback_parity_established':False,'input_parity_established':False,'redraw_count_parity_established':False,
        'claim':'Only exact bounded two-level box geometry and actual Rust paint-entry to actual core Quad projection. All raw frames retained and compared. No lifecycle, input, redraw-count, arbitrary-depth, nontrivial nested-clipping, fractional nested, raster, native-window or browser parity.'}


def require_semantic_match(comparison):
    require(comparison['passed'],'actual nested-deferred box projection mismatch; retain both traces')


def mutation_descriptors():
    path=ROOT/'diagnostics/nested_deferred_pair/control-policy.json'
    require(baseline.digest(path)=='3f4a823d8324c0fe721d2311930f910d424dde367ac8579e59b980ddb2d29a4d','pre-candidate control policy changed')
    expected=load_json(path.read_text())
    descriptors=load_json((ROOT/'diagnostics/nested_deferred_pair/mutations.json').read_text())
    require([{k:v for k,v in m.items() if k not in ('old','new')} for m in descriptors]==expected,'control witnesses differ from pre-candidate policy')
    require(all(set(m)==set(p)|{'old','new'} and m['old']!=m['new'] and 'PENDING' not in m['old']+m['new'] for m,p in zip(descriptors,expected)),'final exact source mutations required')
    return descriptors


def validate_mutation_outcomes(results):
    descriptors=mutation_descriptors()
    require([r['mutation'] for r in results]==[m['name'] for m in descriptors],'exact production control coverage')
    require(all(r['outcome']=='executed-paired-nested-deferred-rejection' for r in results),'each control must compile/execute, pass transport/structure, then reject all frozen order/geometry witnesses')
