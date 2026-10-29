"""Physical C ABI bridge and bounded exact integer-SIMT CUDA kernels."""
import ctypes as C
import fcntl
import hashlib
from pathlib import Path
from omega_gpu_mcts.backend import CudaSearch,CudaUnavailable,Config,Grammar,Elite,Stats
from omega_gpu_mcts.numeric import Rational64
from omega_gpu_mcts.flat import RationalInterval
from omega_gpu_mcts.build import ROOT,compile_cuda
from omega_platform.sandbox import c_tool
from omega_platform.budget import BUILD_BUDGET


def libraries():
    sources=[ROOT/n for n in ('hardware/cuda/flat_ast_eval.cu','omega_gpu_mcts/mcts_kernel.cu','omega_abstract_domain/invariant_filter.cu','omega_gpu_mcts/cuda_api.cu','hardware/cuda_native/warp_mcts_evaluator.cu','hardware/cuda_native/rational_gemm.cu')]
    headers=[*sorted((ROOT/'hardware/cuda').glob('*.cuh')),*sorted((ROOT/'hardware/cuda_native').glob('*.cuh')),*sorted((ROOT/'omega_gpu_mcts').glob('*.cuh')),*sorted((ROOT/'omega_gpu_mcts').glob('*.h')),*sorted((ROOT/'omega_abstract_domain').glob('*.cuh'))]
    bridge=ROOT/'hardware/cuda_native/bridge_omega_cuda.c';fingerprint=hashlib.sha256(b''.join(p.read_bytes() for p in [*sources,*headers,bridge])).hexdigest()[:24]
    folder=ROOT/'build/cuda-native';folder.mkdir(parents=True,exist_ok=True);cuda=folder/(fingerprint+'.so');host=folder/(fingerprint+'-bridge.so')
    with (folder/'.build.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if not cuda.exists():
            temporary=cuda.with_suffix('.tmp.so');compile_cuda(sources,temporary,shared=True);temporary.replace(cuda)
        if not host.exists():
            import shutil
            cc=shutil.which('cc')
            if not cc:raise RuntimeError('A trusted C compiler is required')
            temporary=host.with_suffix('.tmp.so')
            c_tool([cc,'-std=gnu11','-O2','-shared','-fPIC',bridge,'-ldl','-o',temporary],inputs=[bridge],output_directory=folder,budget=BUILD_BUDGET,check=True);temporary.replace(host)
    return cuda,host


class BridgeSearch(CudaSearch):
    def __init__(self):
        path,host=libraries();native=C.CDLL(str(path));bridge=C.CDLL(str(host));invoke=bridge.omega_bridge_search
        args=[C.POINTER(Rational64)]*3+[C.POINTER(RationalInterval)]*2+[C.POINTER(Elite),C.POINTER(Stats),C.POINTER(C.c_char),C.c_uint32]
        invoke.argtypes=[C.c_char_p,C.POINTER(Config),C.POINTER(Grammar),*args]
        class API:
            def omega_cuda_search(self,config,grammar,*rest):return invoke(str(path).encode(),C.byref(config),C.byref(grammar),*rest)
        self.library=API();self.cuda=native;self.bridge=bridge
        if not native.omega_cuda_available():raise CudaUnavailable('C ABI and CUDA kernels compiled; no NVIDIA device, no CPU substitution')
