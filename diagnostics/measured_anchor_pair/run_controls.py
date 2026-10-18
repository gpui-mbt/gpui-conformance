"""Isolated compiled production/API mutations; compile failure is never a kill."""
import hashlib
from pathlib import Path
from run_rust import load,require,save
from compare import compare,evaluate_control

MUTATIONS={
    'owner-origin':{
        'path':'element/anchored.mbt',
        'before':'if spec.measured_leaf {\n              reference.left()\n            } else {\n              parent.left()\n            },\n            reference.bottom(),',
        'after':'parent.left(),\n            parent.bottom(),'},
    'no-logical-rounding':{
        'path':'element/anchored.mbt',
        'before':'round_away(x - static_origin.x()),\n      round_away(y - static_origin.y()),',
        'after':'x - static_origin.x(),\n      y - static_origin.y(),'},
    'eager-device-snap':{
        'path':'element/anchored.mbt',
        'before':'ordinary.viewport,\n            None,',
        'after':'ordinary.viewport,\n            ordinary.scale_factor,'},
    'window-mode':{
        'path':'probe/main.mbt',
        'before':'@element.Local // MUTATION_SITE_LOCAL_MODE',
        'after':'@element.Window // MUTATION_SITE_LOCAL_MODE'},
    'stale-scale-metrics':{
        'path':'probe/main.mbt',
        'before':'let metrics_scale = scale // MUTATION_SITE_METRICS_SCALE',
        'after':'let metrics_scale = 1.0 // MUTATION_SITE_METRICS_SCALE'},
}
NAMES=tuple(MUTATIONS)


def replacements(name):
    m=MUTATIONS[name];return m['path'],m['before'],m['after']


def apply_mutation(stage,mutation):
    require(mutation in MUTATIONS,'unknown mutation')
    m=MUTATIONS[mutation];path=Path(stage)/m['path'];original=path.read_text()
    require(original.count(m['before'])==1,'one reviewed production mutation site: '+mutation)
    changed=original.replace(m['before'],m['after'],1);path.write_text(changed)
    return dict(name=mutation,path=m['path'],before=m['before'],after=m['after'],
        original_sha256=hashlib.sha256(original.encode()).hexdigest(),mutated_sha256=hashlib.sha256(changed.encode()).hexdigest(),
        kind='production-layout' if m['path'].startswith('element/') else 'production-api-adapter-misuse')


def run_controls(pair,core,out,fixture,token,rust,baseline,baseline_report):
    from run import compile_candidate
    results=[]
    for name in NAMES:
        record=compile_candidate(pair,core,out/'controls'/name,fixture,token,mutation=name,shared_toolchain='candidate')
        raw=load(out/'controls'/name/'raw.stdout');compared=compare(rust,raw,fixture,token)
        save(out/'controls'/name/'comparison.json',compared)
        result=evaluate_control(name,baseline_report,compared,baseline,raw,fixture,
            execution={'build_returncode':record['build']['returncode'],'execution_returncode':record['execution']['returncode']})
        results.append(result)
    save(out/'controls.json',results)
    # All controls are attempted; baseline mismatches never short-circuit evidence.
    require(all(r.get('killed') is True for r in results),'one or more production controls lack a compiled semantic witness')
    return results
