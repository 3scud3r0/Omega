"""End-to-end native bootstrap, exact tensors, formal admission and attacks."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from omega_selfhost import driver
from omega_selfhost.bootstrap import compile_source
from omega.sintaxe import analisar,ErroOmega
from omega.motor_v1 import CompiladorV1,MaquinaV1,num
from omega.nucleo_v1 import verificar_certificado_v1
from omega_platform.budget import Budget,COMPILER_BUDGET
from omega_platform.sandbox import run as isolated_run

ROOT=Path(__file__).resolve().parents[1]
KERNEL=ROOT/'formal/tensor/.lake/build/bin/omega_tensor_kernel'


@unittest.skipUnless(shutil.which('cc'),'Native C compiler required')
class BootstrapTests(unittest.TestCase):
    def test_verified_three_stage_fixed_point(self):
        compiler=driver.compiler()
        report=json.loads((driver.BUILD/'bootstrap.json').read_text())
        self.assertTrue(report['fixed_point'])
        self.assertEqual(len(set(report['stage_c_sha256'])),1)
        self.assertEqual(report['stage_binary_sha256'][1],report['stage_binary_sha256'][2])
        self.assertFalse(report['native_stages_use_python'])
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'without-python.c'
            isolated_run([compiler,driver.PACKAGE/'compiler.omega',out],
                         readonly=[driver.PACKAGE/'compiler.omega'],writable=[tmp],
                         budget=COMPILER_BUDGET,check=True)
            self.assertEqual(driver.digest(out),report['stage_c_sha256'][2])

    def test_ordered_calls_strings_loops_and_exact_rationals(self):
        source='''funcao inc(s) { put(s,"n",s["n"]+1); retornar s["n"]; }
funcao pair(a,b) { retornar a*10+b; }
funcao principal() {
 var s=obj(); put(s,"n",0);
 print(pair(inc(s),inc(s)));
 var values=[];var i=0;enquanto(i<4){push(values,i);i=i+1;}
 print(json(values));print(text(1/3+1/6));
 print("\\u03a9\\n\\t\\uD83D\\uDE80");retornar 0;
}'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'sample.omega';path.write_text(source)
            c0=root/'bootstrap.c';c0.write_text(compile_source(source))
            c1=root/'native.c'
            isolated_run([driver.compiler(),path,c1],readonly=[path],writable=[tmp],budget=COMPILER_BUDGET,check=True)
            self.assertEqual(c0.read_text(),c1.read_text())
            exe=root/'sample';driver.cc(c1,exe)
            self.assertEqual(isolated_run([exe],check=True).stdout,'12\n[0,1,2,3]\n1/2\nΩ\n\t🚀\n')

    def test_fuel_and_recursion_are_bounded(self):
        for body in ('enquanto(1){} retornar 0;', 'retornar principal();'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);src=root/'bad.omega';src.write_text('funcao principal(){'+body+'}')
                c=root/'bad.c';exe=root/'bad'
                isolated_run([driver.compiler(),src,c],readonly=[src],writable=[tmp],budget=COMPILER_BUDGET,check=True);driver.cc(c,exe)
                proc=isolated_run([exe],budget=Budget(fuel=1000,depth=512,wall_seconds=5))
                self.assertNotEqual(proc.returncode,0)
                self.assertIn('budget' if 'enquanto' in body else 'depth',proc.stderr)

    def test_unicode_identifiers_and_decimal_literals(self):
        source='parametro α=١٢; perda custo=(α-١)^2; gradiente custo em α; mostrar custo;'
        ref=CompiladorV1().programa(analisar(source))
        self.assertEqual(driver.compile_text(source),ref)

    def test_json_control_characters_have_valid_c_string_encoding(self):
        value=''.join(chr(i) for i in range(1,32))+chr(127)+'a7"\\Ω🚀'
        source='funcao principal(){print(json('+json.dumps(value,ensure_ascii=False)+'));retornar 0;}'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'controls.omega';path.write_text(source)
            binary=root/'controls';driver.build(path,binary)
            self.assertEqual(binary.with_suffix('.c').read_text(),compile_source(source))
            self.assertEqual(json.loads(isolated_run([binary],check=True).stdout),value)


@unittest.skipUnless(KERNEL.is_file(),'Run scripts/setup-native.sh')
class NativeTensorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.binary=cls.root/'network'
        driver.build(ROOT/'exemplos/rede_profunda.omega',cls.binary)
        cls.result,cls.verification=driver.run(cls.binary)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_deep_network_matches_reference_without_python_runtime(self):
        ref=MaquinaV1(CompiladorV1().programa(analisar(
             (ROOT/'exemplos/rede_profunda.omega').read_text()))).executar()
        self.assertEqual(self.result['outputs'],ref.saidas)
        self.assertEqual(self.result['state'],{k:num(v) for k,v in ref.estado.items()})
        self.assertTrue(all(verificar_certificado_v1(c) for c in self.result['certificates']))
        self.assertTrue(self.verification['valid'])
        proc=isolated_run([self.binary],check=True)
        self.assertEqual(json.loads(proc.stdout),self.result)

    def test_kernel_rejects_changed_gradient_step_seed_shape_and_chain(self):
        def gradient(d):d['certificates'][0]['gradientes']['W1'][0][0]='1'
        def seed(d):d['certificates'][-1]['semente']=1
        def state(d):d['certificates'][1]['estado_depois']['W2'][0][0]='9'
        def rate(d):d['certificates'][1]['taxa']='1/1024'
        def chain(d):d['certificates'].pop(1)
        def final(d):d['state']['W1'][0][0]='9'
        def observed(d):d['values']['custo']='0'
        def shape(d):d['ir']['nos'][8]['forma']=[1,4]
        for mutate in (gradient,seed,state,rate,chain,final,observed,shape):
            with self.subTest(mutation=mutate.__name__):
                forged=copy.deepcopy(self.result);mutate(forged)
                with self.assertRaises((ValueError,RuntimeError)):
                    driver.verify_result(forged)

    def test_missing_lean_fails_closed(self):
        from unittest.mock import patch
        with patch.dict(os.environ,{'OMEGA_TENSOR_KERNEL':'/nonexistent/kernel'}):
            with self.assertRaises(RuntimeError):driver.verify_result(self.result)

    def test_exact_gradient_above_previous_sampling_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'large.omega'
            src.write_text('parametro vetor w = ['+','.join(['1']*65)+'];\nperda f=dot(w,w);\ngradientes f;')
            exe=root/'large';driver.build(src,exe)
            result,verified=driver.run(exe)
            self.assertTrue(verified['valid'])
            self.assertEqual(result['certificates'][0]['gradientes']['w'],['2']*65)
            result['certificates'][0]['gradientes']['w'][64]='3'
            with self.assertRaises(RuntimeError):driver.verify_result(result)

    def test_all_repository_sources_are_supported_or_intentionally_rejected(self):
        from omega_platform.corpus import regression
        report=regression(ROOT)
        self.assertTrue(report['valid'],json.dumps(report,indent=2,ensure_ascii=False))
        self.assertTrue(report['count_matches'])
        self.assertEqual(report['infrastructure_failures'],0)

    def test_optimization_has_universal_value_and_gradient_proofs(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe=Path(tmp)/'optimized'
            driver.build(ROOT/'exemplos/otimizacao_ir.omega',exe,optimize=True)
            result,verified=driver.run(exe)
            self.assertTrue(verified['optimization']['theorems']>0)
            proof=exe.with_suffix('.opt.lean').read_text()
            self.assertIn('theorem value_',proof)
            self.assertIn('theorem gradient_',proof)
            result['optimization']['regras'][0]['resultado']=999
            with self.assertRaises((RuntimeError,ValueError)):driver.verify_result(result)

    def test_false_universal_identity_is_rejected_by_lean(self):
        from omega_selfhost.proof import check_identities
        forged={'tipo':'identidade_nativa','left':['v','x'],'right':['n','0']}
        with self.assertRaises(ValueError):check_identities([forged])

    def test_tensor_coordinates_cannot_alias_user_symbols(self):
        sources=[
            'parametro vetor w=[1]; parametro w_0=2; provar w==[w_0];',
            'parametro matriz w=[[1]]; parametro vetor w_0=[2]; provar w==[w_0];',
            'parametro vetor w=[1]; provar w==[__omega_coord_1_w_1_0];',
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for i,source in enumerate(sources):
                with self.subTest(source=source):
                    path=Path(tmp)/f'bad{i}.omega';path.write_text(source)
                    with self.assertRaises((RuntimeError,ValueError)):
                        driver.build(path,Path(tmp)/f'bad{i}')
                        driver.run(Path(tmp)/f'bad{i}')

    def test_universal_proof_must_match_the_program_statement(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe=Path(tmp)/'matrix'
            driver.build(ROOT/'exemplos/produto_matrizes.omega',exe)
            result,verified=driver.run(exe)
            self.assertTrue(verified['valid'])
            # A true but unrelated theorem must not replace the promised proof.
            result['certificates'][0]={'tipo':'identidade_nativa',
                                      'left':['n','0'],'right':['n','0']}
            with self.assertRaises(RuntimeError):driver.verify_result(result)

if __name__=='__main__':unittest.main()
