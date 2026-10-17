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
_spec = importlib.util.spec_from_file_location('deferred_priority_rust_verify', ROOT / 'diagnostics/deferred_priority/verify.py')
baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(baseline)
require = baseline.require
LAYER = 'supplemental-flat-deferred-priority-native-pair'
CANDIDATE_LAYER = 'compiled-moonbit-deferred-priority'
TOLERANCE = 2 ** -10
GRID_TOLERANCE = 2 ** -10
POLICY_SHA256 = 'ab397c1604af04c65f25b45ea3b96a03d3d4cb318e7a246cc9ccae1220d601ca'


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
    path = ROOT / 'diagnostics/deferred_priority_pair/comparison-policy.json'
    require(baseline.digest(path) == POLICY_SHA256, 'pre-candidate comparison policy changed')
    return load_json(path.read_text())


def validate_schema(raw, path):
    try: Draft202012Validator(load_json(path.read_text())).validate(raw)
    except ValidationError as error: raise ValueError('raw schema: ' + error.message) from error


def shape(value, fields, label):
    require(isinstance(value, dict) and set(value) == set(fields), label + ': fields')


def topology(case, stage):
    names = ['$host', '$before_position', 'ordinary.before', '$attachments', '$reference', '$after_position', 'ordinary.after']
    for layer in case['layers']:
        names += [layer['id'] + '.' + suffix for suffix in ('anchor','root','$first_holder','first','$second_holder','second')]
    ids = {name: str(i + 1) for i, name in enumerate(names)}
    parents = {'$host': None, '$before_position': '$host', 'ordinary.before': '$before_position',
               '$attachments': '$host', '$reference': '$attachments'}
    for layer in baseline.active_layers(case, stage):
        p = layer['id']
        parents.update({p+'.anchor':'$attachments', p+'.root':p+'.anchor', p+'.$first_holder':p+'.root',
                        p+'.first':p+'.$first_holder', p+'.$second_holder':p+'.root', p+'.second':p+'.$second_holder'})
    parents.update({'$after_position':'$host', 'ordinary.after':'$after_position'})
    return {name: {'id': ids[name], 'parent': parent} for name, parent in parents.items()}


def box_names(case, stage):
    return ['ordinary.before','ordinary.after'] + [l['id']+'.'+s for l in baseline.active_layers(case,stage) for s in ('root','first','second')]


def inspect_scene(commands, nodes, case, stage, scale):
    stack, order, masks = [], [], {}
    boxes = box_names(case, stage)
    for event in commands:
        kind, node = event['kind'], event['node']
        require(node in nodes and event['id'] == nodes[node]['id'], 'emitting scene node identity')
        if kind == 'clip_push':
            baseline.physical_grid(event['bounds'], scale)
            stack.append((node, event['bounds']))
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
            config=baseline.interaction_for(case,name)
            require(e['pointer_events']==bool(config and config['listener']!='none') and e['focusable'] is False,'authored pointer/focus config')
            baseline.physical_grid(e['bounds'],scale); nodes[name]=e
        elif kind=='scene':
            shape(e,['type','kind','node','id','bounds'],'scene')
            require(phase in ('nodes','scene'),'scene lifecycle'); phase='scene'; scenes.append(e)
        else: require(False,'unexpected candidate frame event: '+kind)
    require(phase=='done' and list(nodes)==list(expected),'complete structural preorder/frame')
    baseline.vector(nodes['$host']['bounds'],[0,0,*case['window']],'actual host bounds',0)
    order,masks=inspect_scene(scenes,nodes,case,stage,scale)
    return {'frame':entries[0]['frame'],'scale_factor':scale,'nodes':nodes,'paint_order':order,
            'observed_scene_commands':scenes,'effective_masks':masks,'overflow':overflow}


def verify_route(e, frame, case):
    shape(e,['type','action','position','hit_test','target','capture','bubble','callback_capture','callback_bubble','callbacks'],'actual route')
    require(e['position']==case['probe_position'],'route position')
    nodes=frame['nodes']; p=e['position']
    # Candidate-only invariant of the preserved core contract. This is not a GPUI prediction.
    eligible=[]
    for name in frame['paint_order']:
        r=nodes[name]['bounds']; mask=frame['effective_masks'][name]['derived_intersection']
        # No emitted clip means no observed scene clipping restriction here.
        # This candidate-only routing invariant cannot manufacture paired mask evidence.
        inside=all(r[a]<=p[a]<r[a]+r[a+2] for a in (0,1))
        if mask is not None: inside=inside and all(mask[a]<=p[a]<mask[a]+mask[a+2] for a in (0,1))
        if nodes[name]['pointer_events'] and inside: eligible.append(name)
    target=eligible[-1] if eligible else None
    require(e['target']==e['hit_test']==target,'candidate-only reverse-paint topmost invariant')
    bubble=[]; node=target
    while node is not None: bubble.append(node); node=nodes[node]['parent']
    capture=list(reversed(bubble))
    require(e['capture']==e['callback_capture']==capture and e['bubble']==e['callback_bubble']==bubble,'actual structural dispatch routes')
    callbacks=[{'node':name,'id':nodes[name]['id'],'phase':phase} for phase,path in [('capture',capture),('bubble',bubble)] for name in path]
    require(e['callbacks']==callbacks,'actual dispatch closure calls')


def decode_transport(raw, token, corpus):
    validate_schema(raw,ROOT/'diagnostics/deferred_priority_pair/raw.schema.json')
    shape(raw,['schema_version','layer','fixture','input','run_token','cases'],'candidate')
    require(raw['schema_version']==1 and raw['layer']==CANDIDATE_LAYER and raw['fixture']=='font-free-flat-deferred-priority','candidate identity')
    require(isinstance(token,str) and 16<=len(token)<=64 and raw['run_token']==token,'candidate session token')
    require(raw['input']==corpus and [c['id'] for c in raw['cases']]==[c['id'] for c in corpus['cases']],'exact input/case coverage')
    return raw


def verify_candidate(raw, corpus):
    policy(); baseline.validate_scenarios(corpus); decode_transport(raw,raw.get('run_token'),corpus)
    result=[]
    for observed,case in zip(raw['cases'],corpus['cases']):
        events=observed['events']; require([e['sequence'] for e in events]==list(range(len(events))),'candidate event sequence')
        cursor,frame_number,last_frame=0,0,None; operations=[]
        for operation,action,stage,scale,is_input in baseline.operation_plan(case):
            require(cursor<len(events) and events[cursor]=={'sequence':cursor,'operation':operation,'frame':frame_number,'event':{'type':'operation_start','input':action}},'operation start/input')
            cursor+=1; frames=[]; pending=None; routes=[]
            while cursor<len(events) and events[cursor]['event']['type']!='operation_end':
                entry=events[cursor]; cursor+=1; e=entry['event']; kind=e['type']
                require(entry['operation']==operation,'operation interleaving')
                if kind=='frame_start': require(pending is None,'nested candidate frame'); pending=[]; frame_number+=1
                require(entry['frame']==frame_number,'candidate frame sequence')
                if kind=='route':
                    require(is_input and pending is None and last_frame is not None,'route outside input/frame')
                    verify_route(e,last_frame,case); routes.append(e)
                else:
                    require(pending is not None,'frame event outside frame'); pending.append(entry)
                    if kind=='frame_end':
                        last_frame=verify_frame(pending,case,stage,scale); frames.append(last_frame); pending=None
            require(pending is None and (is_input or frames),'missing required candidate frame')
            require([r['action'] for r in routes]==(['down','up'] if is_input else []),'exact actual down/up input coverage')
            require(cursor<len(events) and events[cursor]=={'sequence':cursor,'operation':operation,'frame':frame_number,'event':{'type':'operation_end','scale_factor':scale}},'operation end/scale')
            cursor+=1; operations.append({'id':operation,'frames':frames,'routes':routes,'final_observed_frame':last_frame})
        require(cursor==len(events),'trailing candidate events'); result.append({'id':case['id'],'operations':operations})
    return result


def compare_observations(rust,candidate,corpus):
    original=baseline.verify_observations(rust,corpus)['cases']; replacement=verify_candidate(candidate,corpus)
    mismatches=[]; cases=[]; maximum=0.0
    counts={'cases':len(corpus['cases']),'rust_frames':0,'candidate_frames':0,'compared_operations':0,'rust_mouse_down_callbacks':0,'candidate_input_operations':0}
    for case,left,right in zip(corpus['cases'],original,replacement):
        pairs=[]; prior=None
        for rust_op,candidate_op in zip(left['operations'],right['operations']):
            require(rust_op['id']==candidate_op['id'],'operation correspondence')
            if rust_op['frames']: prior=rust_op['frames'][-1]
            a,b=prior,candidate_op['final_observed_frame']; require(a is not None and b is not None,'observed final frame')
            counts['rust_frames']+=len(rust_op['frames']); counts['candidate_frames']+=len(candidate_op['frames']); counts['compared_operations']+=1
            names=set(box_names(case,'removed' if rust_op['id'].startswith('removed') else 'base'))
            projection=[n for n in a['observed_paint_order'] if n in names]
            def check(field,x,y,numeric=False):
                nonlocal maximum
                try:
                    if numeric:
                        if len(x)==len(y): maximum=max(maximum,*(abs(i-j) for i,j in zip(x,y)))
                        baseline.vector(x,y,field,TOLERANCE)
                    else: require(x==y,field+': different values')
                except ValueError as error: mismatches.append({'case':left['id'],'operation':rust_op['id'],'field':field,'rust':x,'candidate':y,'error':str(error)})
            check('scale_factor',a['scale_factor'],b['scale_factor']); check('paint_order',projection,b['paint_order'])
            for name in projection:
                check('bounds/'+name,a['observed_paint'][name]['bounds'],b['nodes'][name]['bounds'],True)
                check('effective_mask/'+name,a['observed_paint'][name]['content_mask'],b['effective_masks'][name]['derived_intersection'])
            callbacks=rust_op['observed_input_callbacks']; routes=candidate_op['routes']
            counts['rust_mouse_down_callbacks']+=len(callbacks); counts['candidate_input_operations']+=bool(routes)
            pairs.append({'id':rust_op['id'],'rust_frame_ids':[f['frame'] for f in rust_op['frames']],
                'candidate_frame_ids':[f['frame'] for f in candidate_op['frames']],
                'compared_rust_frame':a['frame'],'compared_candidate_frame':b['frame'],
                'rust_actual_paint_entry_box_projection':projection,'candidate_actual_quad_emission_order':b['paint_order'],
                'input_parity_established':False,'rust_actual_mouse_down_callbacks':callbacks,'candidate_actual_routes':routes,
                'input_qualification':'Different contracts: GPUI multi-listener/occlusion/propagation versus core topmost structural routing. No paired input claim.'})
        cases.append({'id':left['id'],'operations':pairs})
    return {'schema_version':1,'layer':LAYER,'passed':not mismatches,'counts':counts,'cases':cases,'mismatches':mismatches,
        'comparison_policy_sha256':POLICY_SHA256,'numeric_policy':{'absolute_logical_allowance':TOLERANCE,'physical_grid_allowance':GRID_TOLERANCE,'maximum_observed_difference':maximum},
        'lifecycle_callback_parity_established':False,'input_parity_established':False,
        'claim':'Bounded box geometry and source-derived actual Rust paint-entry to actual core Quad emission projection only. Every raw frame retained/validated. No lifecycle or input callback equality, raster, native-window or browser claim.'}


def require_semantic_match(comparison):
    require(comparison['passed'],'actual deferred-priority box projection mismatch; retain both traces')


def mutation_descriptors():
    path=ROOT/'diagnostics/deferred_priority_pair/control-policy.json'
    require(baseline.digest(path)=='6a8bde926ce504e1b8a360722de738e5dde9f29efd68293afc7c8f2e6d6bdd26','pre-candidate control policy changed')
    expected=load_json(path.read_text())
    descriptors=load_json((ROOT/'diagnostics/deferred_priority_pair/mutations.json').read_text())
    require([{k:v for k,v in m.items() if k not in ('old','new')} for m in descriptors]==expected,'control witnesses differ from pre-candidate policy')
    require(all(set(m)==set(p)|{'old','new'} and m['old']!=m['new'] and 'PENDING' not in m['old']+m['new'] for m,p in zip(descriptors,expected)),'final exact source mutations required')
    return descriptors


def validate_mutation_outcomes(results):
    descriptors=mutation_descriptors()
    require([r['mutation'] for r in results]==[m['name'] for m in descriptors],'exact production control coverage')
    require(all(r['outcome']=='executed-paired-deferred-priority-rejection' for r in results),'each control must compile/execute, pass transport/structure, then reject its paint-order witnesses')
