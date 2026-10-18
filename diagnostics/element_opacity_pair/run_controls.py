"""Compile and execute changed MoonBit adapter applications; never edit outputs."""
from pathlib import Path
from candidate import compile_candidate
from support import digest, load, require
from compare import compare
import uuid

MUTATIONS={
    'omit-parent':('if present(i, key) { e.with_opacity(number(i, key)).unwrap() } else { e }',
                   'if key == "parent" { e } else if present(i, key) { e.with_opacity(number(i, key)).unwrap() } else { e }'),
    'double-parent':('e.with_opacity(number(i, key)).unwrap()',
                     'e.with_opacity(number(i, key) * (if key == "parent" { number(i, key) } else { 1.0 })).unwrap()'),
    'leak-to-sibling':('.with_child(block(5, 40, 80, 255, 0, 255))',
                        '.with_child(block(5, 40, 80, 255, 0, 255).with_opacity(number(i, "parent")).unwrap())'),
    'omit-nested-opacity':('block(7, 20, 20, 255, 255, 0).with_opacity(0.25).unwrap()',
                          'block(7, 20, 20, 255, 255, 0).with_opacity(1.0).unwrap()'),
}

def apply_mutation(stage, name):
    require(name in MUTATIONS,'known mutation');path=Path(stage)/'probe/main.mbt'
    before=digest(path);text=path.read_text();old,new=MUTATIONS[name]
    require(text.count(old)==1,'exact unique mutation site')
    path.write_text(text.replace(old,new))
    return {'name':name,'path':'probe/main.mbt','before_sha256':before,'after_sha256':digest(path),'old':old,'new':new}

def run_controls(pair,core,out,fixture,rust,rust_token):
    records=[]
    (out/'controls').mkdir()
    for name in MUTATIONS:
        token=str(uuid.uuid4())
        record=compile_candidate(pair,core,out/'controls'/name,fixture,token,mutation=name,shared_toolchain='candidate')
        candidate=load(out/'controls'/name/'raw.stdout')
        # A failed compile/run is never a detected semantic negative.
        require(record['status']=='executed','control must genuinely execute')
        require(candidate['run_token']==token and candidate['input']==fixture,'control challenge/input')
        try:
            result=compare(rust,candidate,fixture,{'rust':rust_token,'candidate':token})
        except ValueError as error:
            require(str(error) in ('source opacity policy','raw/projected alpha binding','intrinsic alpha preserved'), 'control must fail semantic opacity policy')
            result={'strict_match':False,'semantic_rejection':str(error)}
        require(result['strict_match'] is False,'negative control not detected')
        records.append({'name':name,'token':token,'manifest':record,'comparison':result})
    return records
