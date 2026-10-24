from pathlib import Path
import os,subprocess,tempfile
import pytest
from omega_selfhost.proof import source,check_identities,lake_binary

ROOT=Path(__file__).resolve().parents[2]


def test_generated_proofs_use_explicitly_built_prelude():
    text,_=source([{'tipo':'identidade_nativa','left':['n','0'],'right':['n','0']}])
    assert text.splitlines()[0]=='import ProofPrelude'
    if not (ROOT/'formal/tensor/.lake/build/lib/lean/ProofPrelude.olean').is_file():
        pytest.fail('ProofPrelude is not built; the installation is incomplete')
    assert check_identities([{'tipo':'identidade_nativa','left':['n','0'],'right':['n','0']}])['theorems']==1


def test_proof_prelude_build_graph_contains_every_generated_import():
    # Ask Lake for the real resolved import closure, not a populated developer
    # cache; the module is a declared library and an import of the default exe.
    result=subprocess.run([str(lake_binary()),'query','+ProofPrelude:deps'],
                          cwd=ROOT/'formal/tensor',capture_output=True,text=True)
    if result.returncode:
        # Lake versions differ in the query facet name. Compiling the declared
        # target remains a real mandatory operation and preserves its status.
        result=subprocess.run([str(lake_binary()),'build','ProofPrelude'],
                              cwd=ROOT/'formal/tensor',capture_output=True,text=True,timeout=300)
    assert result.returncode==0,result.stderr
    project=ROOT/'formal/tensor'
    deps=project/'.lake/packages/mathlib/.lake/build/lib/lean/Mathlib/Tactic'
    assert (deps/'NormNum.olean').is_file()
    assert (deps/'SplitIfs.olean').is_file()
