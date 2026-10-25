"""OM-121: executable checks; source delivery, not a recorded pass."""
from omega_tools.notebooks import execute

def test_notebook_executes_in_sandbox_without_outside_file_effects(tmp_path,signed_authority):
    verifier,mint=signed_authority;target=tmp_path/'outside.txt'
    notebook={'nbformat':4,'cells':[{'cell_type':'code','source':'print(7)'}]}
    result=execute(notebook,capability=mint(['code.execute']),verifier=verifier,principal='agent')
    assert result['sandboxed'] and result['stdout'].strip()=='7' and result['returncode']==0
    notebook['cells'][0]['source']=f'open({str(target)!r},"w").write("forbidden")'
    result=execute(notebook,capability=mint(['code.execute']),verifier=verifier,principal='agent')
    assert result['returncode']!=0 and not target.exists()
