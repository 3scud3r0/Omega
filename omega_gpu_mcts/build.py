"""Local CUDA compilation; no network installation occurs during an import."""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def nvcc():
    configured=os.environ.get('OMEGA_NVCC')
    if configured:
        path=Path(configured)
        if not path.is_file():raise RuntimeError('OMEGA_NVCC must name the compiler executable')
        return path.resolve()
    found=shutil.which('nvcc')
    if found:return Path(found).resolve()
    pinned=ROOT.parent/'.tools/cuda-py/nvidia/cu13/bin/nvcc'
    if pinned.is_file():return pinned
    raise RuntimeError('CUDA compiler unavailable; run scripts/setup-cuda.sh or set OMEGA_NVCC')


def compile_host(*,numeric_only=False,sanitize=False):
    sources=[ROOT/'hardware/cuda/rational_host.cpp']
    if not numeric_only:sources.append(ROOT/'hardware/cuda/host_reference.cpp')
    headers=sorted((ROOT/'hardware/cuda').glob('*.cuh'))+sorted((ROOT/'omega_abstract_domain').glob('*.cuh'))+sorted((ROOT/'omega_gpu_mcts').glob('*.cuh'))+sorted((ROOT/'omega_gpu_mcts').glob('*.h'))
    signature=hashlib.sha256(b''.join(p.read_bytes() for p in [*sources,*headers])+str(sanitize).encode()).hexdigest()[:20]
    directory=ROOT/'build/hyper-core';directory.mkdir(parents=True,exist_ok=True)
    target=directory/('host-'+signature+'.so')
    if not target.exists():
        temporary=target.with_suffix('.tmp.so')
        subprocess.run(['g++','-std=c++17','-O2','-shared','-fPIC','-Wall','-Wextra','-Werror',
                        '-Wno-misleading-indentation',*(['-fsanitize=undefined','-fno-sanitize-recover=all'] if sanitize else []),
                        *map(str,sources),'-o',str(temporary)],check=True,capture_output=True,text=True)
        temporary.replace(target)
    return target


def compile_cuda(sources,target,*,shared=False):
    target=Path(target).absolute();target.parent.mkdir(parents=True,exist_ok=True)
    command=[str(nvcc()),'-std=c++17','-arch=sm_80','-O2','-lineinfo',
             *(['-shared','-Xcompiler=-fPIC'] if shared else []),*map(str,sources),'-o',str(target)]
    subprocess.run(command,cwd=ROOT,check=True,capture_output=True,text=True,timeout=300)
    return target


def cuda_library():
    import fcntl
    paths=sorted(p for folder in ('hardware/cuda','omega_gpu_mcts','omega_abstract_domain')
                 for p in (ROOT/folder).iterdir() if p.suffix in ('.cu','.cuh','.h'))
    compiler=nvcc()
    version=subprocess.check_output([compiler,'--version'])
    digest=hashlib.sha256(version+b''.join(p.read_bytes() for p in paths)).hexdigest()[:20]
    directory=ROOT/'build/hyper-core';directory.mkdir(parents=True,exist_ok=True)
    destination=directory/('cuda-'+digest+'.so')
    with (directory/'.cuda-build.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if not destination.exists():
            sources=[ROOT/name for name in ('hardware/cuda/flat_ast_eval.cu','omega_gpu_mcts/mcts_kernel.cu','omega_abstract_domain/invariant_filter.cu','omega_gpu_mcts/cuda_api.cu')]
            temporary=destination.with_suffix('.tmp.so');compile_cuda(sources,temporary,shared=True);temporary.replace(destination)
    return destination
