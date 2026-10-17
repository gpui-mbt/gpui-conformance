"""Recompile production mutations; a compiler failure never counts as a kill."""
from pathlib import Path
import hashlib
from compare import compare, load
from run_rust import require, save

PRODUCTION = 'element/pointer_outside.mbt'
ADAPTER = 'probe/main.mbt'
MUTATIONS = {
    'disable-outside': {'path':PRODUCTION,
        'before':'for id in self.listeners {', 'after':'for id in ([] : Array[UInt64]) {'},
    'primary-only': {'path':PRODUCTION,
        'before':'@primitives.PointerButtonPressed(position~, ..) =>',
        'after':'@primitives.PointerButtonPressed(position~, button=@primitives.Primary, ..) =>'},
    'release-outside': {'path':PRODUCTION,
        'before':'@primitives.PointerButtonPressed(position~, ..) =>',
        'after':'@primitives.PointerButtonReleased(position~, ..) =>'},
    'wrong-registry': {'path':ADAPTER,
        'before':'[5UL] // MUTATION_SITE_WRONG_REGISTRY',
        'after':'[3UL, 5UL] // MUTATION_SITE_WRONG_REGISTRY'},
    'same-event-cascade': {'path':ADAPTER,
        'before':'// MUTATION_SITE_SAME_EVENT_CASCADE: inserting a render and redispatch here',
        'after':'if app.dirty.val { let (next, _) = render(app); frame = next; dispatch(app, frame, event, button_name); app.dirty.val = true }'},
}


NAMES = ('disable-outside','primary-only','release-outside','wrong-registry','same-event-cascade')

def replacements(name):
    change=MUTATIONS[name]
    return change['path'],change['before'],change['after']

def apply_mutation(stage, mutation):
    require(mutation in MUTATIONS,'unknown mutation')
    change = MUTATIONS[mutation]
    path = Path(stage)/change['path']
    original = path.read_text()
    require(original.count(change['before'])==1,'mutation site must be unique: '+mutation)
    changed=original.replace(change['before'],change['after'])
    path.write_text(changed)
    return dict(name=mutation,path=change['path'],before=change['before'],after=change['after'],
        original_sha256=hashlib.sha256(original.encode()).hexdigest(),
        mutated_sha256=hashlib.sha256(changed.encode()).hexdigest(),
        kind='production-dispatch' if change['path'].startswith('element/') else 'production-api-adapter-misuse')


def run_controls(pair, core, oracle, out, fixture, token, rust):
    from run import compile_candidate
    controls = []
    require(set(MUTATIONS)==set(NAMES),'five reviewed controls required')
    for name in NAMES:
        record = compile_candidate(pair,core,out/'controls'/name,fixture,token,
                                   mutation=name,shared_toolchain='candidate')
        compared=compare(rust,load(out/'controls'/name/'raw.stdout'),oracle,fixture,token)
        save(out/'controls'/name/'comparison.json',compared)
        require(compared['status']=='semantic_mismatch' and compared['differences'],
                'production mutation survived: '+name)
        controls.append(dict(name=name,status='semantic_rejection',build_returncode=0,execution_returncode=0,
            differing_operations=[row['operation'] for row in compared['differences']]))
    save(out/'controls.json',controls)
    return controls
