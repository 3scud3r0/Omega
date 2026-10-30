"""All eighteen formal files are kernel-checked; permitted dependencies are audited."""
from pathlib import Path
import pytest
from omega_science.runtime import catalog,ROOT,inspect_lean_transcript
from omega_selfhost.proof import lake_binary
from omega_selfhost.axiom_policy import forbid_admissions
from omega_platform.sandbox import trusted
from omega_platform.budget import PROOF_BUDGET,Budget

FORMAL=[entry for entry in catalog()['files'] if entry['kind']=='formal']

@pytest.fixture(scope='module',autouse=True)
def build_scientific_library():
    trusted([lake_binary(),'build','ScienceAxioms'],cwd=ROOT/'formal/tensor',
            budget=Budget(wall_seconds=3600,cpu_seconds=3600,memory_bytes=8*1024**3,
                          output_bytes=16*1024**2,processes=1024,open_files=4096),check=True)

@pytest.mark.parametrize('entry',FORMAL,ids=lambda e:str(e['id']))
def test_each_scientific_theorem_file_is_checked_without_unauthorized_dependencies(entry):
    source=ROOT/entry['path']
    forbid_admissions(source.read_text())
    result=trusted([lake_binary(),'env','lean',source],cwd=ROOT/'formal/tensor',budget=PROOF_BUDGET,check=True)
    checked=inspect_lean_transcript(result.stdout+result.stderr,entry['theorems'])
    assert set(checked)==set(entry['theorems'])
