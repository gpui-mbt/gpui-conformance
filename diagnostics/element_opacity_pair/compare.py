"""Source-frozen projection. Raw traces alone are never execution evidence."""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
UPSTREAM = '5a5fbe79917971a4d52a96b6ddb04da198a5012e'
COLORS = {(1,0,0):2,(0,1,0):3,(0,0,1):4,(1,0,1):5,(1,1,0):7}

def require(ok, message):
    if not ok: raise ValueError(message)

def load(path):
    def pairs(items):
        result = {}
        for key,value in items:
            require(key not in result,'duplicate JSON key')
            result[key]=value
        return result
    def invalid(value): raise ValueError('nonfinite JSON: '+value)
    return json.loads(Path(path).read_text(),object_pairs_hook=pairs,parse_constant=invalid)

def numeric(v):
    return type(v) in (int,float) and math.isfinite(v)

def expected_alpha(case):
    def opacity(key): return 1 if case[key] is None else case[key]
    p,c,g = (opacity(key) for key in ('parent','child','grandchild'))
    inherited = 1 if case['deferred'] else p
    result = {2:p,3:inherited*c,4:inherited*c*g*case['alpha']/255*case['binding'],5:1}
    if case['nested']: result[7]=0.25
    return {key:value for key,value in result.items() if value > 0}

def validate_fixture(fixture):
    require(set(fixture)=={'schema_version','viewport','cases'} and fixture['schema_version']==1,'fixture schema')
    require(fixture['viewport']==[240,180],'bounded viewport')
    expected = ['default','unit','nested-half','intrinsic-alpha','binding-alpha','zero-hit','clipped','deferred-reset','nested-deferred-reset']
    require([c['id'] for c in fixture['cases']]==expected,'complete case matrix')
    for c in fixture['cases']:
        require(set(c)=={'id','parent','child','grandchild','alpha','binding','clip','deferred','nested'},'case fields')
        require(all(c[k] is None or numeric(c[k]) and 0<=c[k]<=1 for k in ('parent','child','grandchild')),'element opacity')
        require(type(c['alpha']) is int and 0<=c['alpha']<=255 and numeric(c['binding']) and 0<=c['binding']<=1,'paint alpha')
        require(all(type(c[k]) is bool for k in ('clip','deferred','nested')),'flags')
        require(not c['nested'] or c['deferred'],'nested deferred')
        require(not(c['clip'] and c['deferred']),'unsupported scroll/anchor composition')

def validate_trace(trace, fixture, backend, token):
    require(trace['schema_version']==1 and trace['backend']==backend,'trace backend')
    require(trace['run_token']==token and type(token) is str and len(token)>=16,'fresh run token')
    require(trace['input']==fixture,'trace input binding')
    if backend=='rust-gpui': require(trace['upstream_revision']==UPSTREAM,'Rust revision')
    require([c['id'] for c in trace['cases']]==[c['id'] for c in fixture['cases']],'complete observed cases')
    for case,observed in zip(fixture['cases'],trace['cases']):
        ids = [2,3,4,5]+([7] if case['nested'] else [])
        require([b['id'] for b in observed['bounds']]==ids,'complete observed layout')
        for b in observed['bounds']:
            require(len(b['bounds'])==4 and all(numeric(n) for n in b['bounds']) and all(n>0 for n in b['bounds'][2:]),'nonempty bounds')
        require(type(observed['target']) is int and observed['target']==4,'real pointer target including opacity-zero')
        alpha = {}
        for quad in observed['quads']:
            require(set(quad)=={'bounds','clip','rgba'},'quad fields')
            require(all(len(quad[k])==4 and all(numeric(n) for n in quad[k]) for k in quad),'quad values')
            rgb = tuple(round(x) for x in quad['rgba'][:3])
            require(rgb in COLORS and all(abs(x-y)<=1e-6 for x,y in zip(rgb,quad['rgba'][:3])),'distinct source paint colors')
            identity=COLORS[rgb]
            require(identity not in alpha,'duplicate primitive')
            alpha[identity]=quad['rgba'][3]
        expected=expected_alpha(case)
        require(alpha.keys()==expected.keys(),'missing primitive or wrong transparent culling')
        require(all(abs(alpha[k]-expected[k])<=1e-6 for k in expected),'source opacity policy')
        if backend=='moonbit-core':
            require([r['id'] for r in observed['raw_alpha']]==([2,5,3,4,7] if case['nested'] else [2,5,3,4] if case['deferred'] else [2,3,4,5]),'raw traversal identity')
            require(all(set(r)=={'id','alpha','opacity'} and numeric(r['alpha']) and numeric(r['opacity']) for r in observed['raw_alpha']),'raw alpha fields')
            expected_all=expected_alpha(dict(case,parent=1 if case['parent'] is None else case['parent']))
            actual_raw={r['id']:r for r in observed['raw_alpha']}
            for identity,row in actual_raw.items():
                require(abs(row['alpha']*row['opacity']-expected_all.get(identity,0))<=1e-6,'raw/projected alpha binding')
                require(abs(row['alpha']-(case['alpha']/255 if identity==4 else 1))<=1e-6,'intrinsic alpha preserved')

def project_case(case):
    """GPUI Scene::finish may commute disjoint quads, never overlapping quads.
    Preserve all raw observations; canonicalize only the comparison projection.
    """
    def identity(q): return COLORS[tuple(round(x) for x in q['rgba'][:3])]
    def visible(q):
        b,c=q['bounds'],q['clip']
        return [max(b[0],c[0]),max(b[1],c[1]),min(b[0]+b[2],c[0]+c[2]),min(b[1]+b[3],c[1]+c[3])]
    def overlaps(a,b):
        return max(a[0],b[0])<min(a[2],b[2]) and max(a[1],b[1])<min(a[3],b[3])
    quads=case['quads'];constraints=[]
    for i,a in enumerate(quads):
        for b in quads[i+1:]:
            if overlaps(visible(a),visible(b)): constraints.append([identity(a),identity(b)])
    return {'id':case['id'],'bounds':case['bounds'],'target':case['target'],
            'quads':sorted(quads,key=identity),'overlap_order':sorted(constraints)}


def compare(rust, candidate, fixture, tokens):
    validate_fixture(fixture)
    require(tokens['rust']!=tokens['candidate'],'distinct execution challenges')
    validate_trace(rust,fixture,'rust-gpui',tokens['rust'])
    validate_trace(candidate,fixture,'moonbit-core',tokens['candidate'])
    differences=[]
    def visit(a,b,path):
        if numeric(a) and numeric(b):
            tolerance=1e-6 if '.rgba.' in path else 1e-4
            if abs(a-b)>tolerance: differences.append(path)
        elif type(a) is not type(b): differences.append(path)
        elif isinstance(a,dict):
            if a.keys()!=b.keys(): differences.append(path+'.keys')
            else:
                for k in a: visit(a[k],b[k],path+'.'+k)
        elif isinstance(a,list):
            if len(a)!=len(b): differences.append(path+'.length')
            else:
                for i,(x,y) in enumerate(zip(a,b)): visit(x,y,path+'.'+str(i))
        elif a!=b: differences.append(path)
    for r,c in zip(rust['cases'],candidate['cases']):
        visit(project_case(r),project_case(c),r['id'])
    return {'schema_version':1,'strict_match':not differences,'differences':differences,
            'qualification':'trace comparison only; evidence.verify is required for executed qualification',
            'case_count':len(fixture['cases'])}
