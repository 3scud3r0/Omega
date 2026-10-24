"""Reproducible native fuzzing and instrumentation, always in namespaces."""
from __future__ import annotations
from dataclasses import asdict,replace
import hashlib
import json
from pathlib import Path
import random
import shutil
import tempfile

from .budget import Budget,BUILD_BUDGET,COMPILER_BUDGET
from .sandbox import run,instrumented,trusted


def mutations(seed,count=48):
    rng=random.Random(20261024)
    alphabet='{}[]();"\\\n0129+-*/@α_'
    result=[seed[:i] for i in sorted(set([0,1,2,len(seed)//2,len(seed)-1]))]
    for _ in range(count):
        text=seed
        for _ in range(rng.randint(1,5)):
            i=rng.randrange(len(text)+1)
            text=text[:i]+rng.choice(alphabet)+text[i+rng.randrange(2):]
        result.append(text)
    return list(dict.fromkeys(result))


def validate(root,*,count=48):
    root=Path(root).resolve()
    rows=[]
    def record(target,text,out,expected=None):
        sanitizer=any(s in out.stderr for s in ('AddressSanitizer','LeakSanitizer','runtime error:'))
        good=not sanitizer and not out.timed_out and out.returncode in (0,1)
        if expected is not None:good=good and out.returncode==expected
        rows.append({'target':target,'input_sha256':hashlib.sha256(text.encode()).hexdigest(),
                     'input':text,'returncode':out.returncode,'passed':good,
                     'stderr':out.stderr[-4000:],'sandboxed':out.sandboxed})
    cc=shutil.which('cc')
    if not cc:raise RuntimeError('Native diagnostics require GCC')
    with tempfile.TemporaryDirectory(prefix='omega-security-') as tmp:
        tmp=Path(tmp)
        harness=tmp/'runtime'
        flags=['-std=gnu11','-g','-O1','-fno-omit-frame-pointer','-fno-pie','-no-pie',
               '-fsanitize=address,undefined','-I',root/'omega_selfhost']
        trusted([cc,*flags,root/'testes/foundation/runtime_harness.c','-lgmp','-o',harness],
                budget=BUILD_BUDGET,check=True)
        diagnostic=replace(Budget(),wall_seconds=10,cpu_seconds=5)
        invalid=['"\\','"\\u','"\\ud800','"\\ud800\\u','"unterminated',
                 '"line\nbreak"','{"a":1,"a":2}','01','-','1.','[1,]','{"x":}',
                 '['*257+'0'+']'*257]
        for text in invalid:
            record('json-invalid',text,instrumented([harness,'json',text],budget=diagnostic),1)
        for text in ['0','-3','"Ω🚀"','[1,2,{"x":"y"}]','"\\ud83d\\ude80"']:
            out=instrumented([harness,'json',text],budget=diagnostic)
            record('json-roundtrip',text,out,0)
            if out.ok and json.loads(out.stdout)!=json.loads(text):rows[-1]['passed']=False
        for text in mutations('{"a":[1,2],"s":"hello"}',count):
            record('json-fuzz',text,instrumented([harness,'json',text],budget=diagnostic))
        for text in ['0','-1','1/3','99999999999999999999999999999999999','1/0','..','١٢']:
            record('rational',text,instrumented([harness,'number',text],budget=diagnostic))
        for mode in ('cycle','equalcycle','fuel'):
            record('runtime-budget',mode,instrumented([harness,mode],budget=replace(diagnostic,fuel=1000,depth=32)),1)
        # Verify that the instrumentation itself detects a real memory defect.
        bad=tmp/'canary.c';bad.write_text('#include <stdlib.h>\nint main(int n,char**v){char*p=malloc(1);volatile char*q=p;q[n+8]=v[0][0];free(p);return 0;}\n')
        canary=tmp/'canary'
        trusted([cc,*[f for f in flags if f!='-fsanitize=address,undefined'],'-fsanitize=address',bad,'-o',canary],budget=BUILD_BUDGET,check=True)
        detected=instrumented([canary],budget=diagnostic)
        rows.append({'target':'sanitizer-canary','passed':detected.returncode!=0 and 'AddressSanitizer' in detected.stderr,
                     'returncode':detected.returncode,'stderr':detected.stderr[-2000:],'sandboxed':detected.sandboxed})
        from omega_selfhost.bootstrap import compile_source
        source=tmp/'compiler.c';source.write_text(compile_source((root/'omega_selfhost/compiler.omega').read_text()))
        compiler=tmp/'compiler'
        trusted([cc,*flags,source,'-lgmp','-o',compiler],budget=BUILD_BUDGET,check=True)
        seeds=['parametro x=1; perda l=(x-2)^2; mostrar l;',
               'funcao principal(){var a=[1,2]; print(json(a)); retornar 0;}']
        for seed in seeds:
            for text in [seed,*mutations(seed,count)]:
                inp=tmp/'candidate.omega';out=tmp/'candidate.c';inp.write_text(text)
                result=instrumented([compiler,inp,out],readonly=[inp],writable=[tmp],budget=COMPILER_BUDGET)
                record('lexer-parser',text,result)
        # Exercise the real tensor/GMP/AD runtime under the same instruments,
        # then check its result independently with the Lean kernel.
        native_source=root/'exemplos/rede_profunda.omega'
        native_c=tmp/'tensor.c';native_binary=tmp/'tensor'
        instrumented([compiler,native_source,native_c],readonly=[native_source],
                     writable=[tmp],budget=COMPILER_BUDGET,check=True)
        trusted([cc,*flags,native_c,'-lgmp','-o',native_binary],budget=BUILD_BUDGET,check=True)
        output=instrumented([native_binary],budget=diagnostic)
        record('native-tensor-ad',native_source.name,output,0)
        if output.ok:
            from omega_selfhost.driver import verify_result
            verify_result(json.loads(output.stdout))
        kernel=root/'formal/tensor/.lake/build/bin/omega_tensor_kernel'
        invalid_ir=['', '{','[]','null','{"format":"omega-native-result-2"}']
        for text in [*invalid_ir,*mutations('{"ir":{"commands":[]},"certificates":[]}',count)]:
            inp=tmp/'invalid.json';inp.write_text(text)
            result=run([kernel,inp],readonly=[inp],budget=Budget(),threads=True)
            record('ir-json-verifier',text,result,1 if text in invalid_ir else None)
        # Static analysis covers the runtime data/codec entry points. The full
        # generated compiler is instrumented and fuzzed above; GCC's analyzer
        # exceeds its budget on that unit, so no whole-compiler static claim is
        # made. Every diagnostic from this analyzed unit is fatal.
        for src in (root/'testes/foundation/runtime_harness.c',):
            result=trusted([cc,'-std=gnu11','-O0','-fanalyzer','-Werror',
                            '-Wno-unused-function','-Wno-unused-variable','-Wno-misleading-indentation',
                            '-I',root/'omega_selfhost','-c',src,'-o',tmp/'analysis.o'],budget=BUILD_BUDGET)
            rows.append({'target':'gcc-analyzer','source':src.name,'passed':result.ok,'stderr':result.stderr})
    return {'format':'omega-security-report-1','seed':20261024,'mutation_count':count,
            'passed':sum(r['passed'] for r in rows),'failed':sum(not r['passed'] for r in rows),
            'valid':all(r['passed'] for r in rows),'cases':rows,
            'instrumentation':'ASan+UBSan+LSan, 32-TiB virtual diagnostic quota; normal candidates retain strict RLIMIT_AS'}
