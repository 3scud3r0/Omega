"""Testes de regressão do motor Ômega 1.0. Sem serviços externos."""
import copy
from fractions import Fraction as F
from pathlib import Path
import tempfile
import unittest

from omega.sintaxe import ErroOmega, analisar
from omega.motor_v1 import CompiladorV1, MaquinaV1, mk, formato, num
from omega.nucleo_v1 import verificar_certificado_v1, validar_ir, comp_grad
from omega.otimizador_v1 import otimizar, validar_otimizacao
from omega.exportar_lean import gerar_lean
from omega.cli import principal


BASE='''
parametro matriz W=[[2,0],[0,1]];
parametro vetor b=[1,-1];
vetor x=[1,2];
tensor h=relu(W @ x+b);
perda custo=dot(h,h);
'''


def build(text=BASE):
    return CompiladorV1().programa(analisar(text))


def run(text):
    return MaquinaV1(build(text)).executar()


class TestesCompiladorV1(unittest.TestCase):
    def test_versao_ir(self):self.assertEqual(build()['formato'],'omega-ir-2')
    def test_formas_matriz(self):
        ir=build()
        self.assertEqual(ir['nos'][ir['simbolos']['W']]['forma'],[2,2])
        self.assertEqual(ir['nos'][ir['simbolos']['h']]['forma'],[2])
    def test_relu_realmente_nao_linear(self):
        v=run('parametro x=-2; perda a=relu(x); mostrar a;')
        self.assertEqual(v.saidas[-1],"a = 0")
        v=run('parametro x=3; perda a=relu(x); mostrar a;')
        self.assertEqual(v.saidas[-1],"a = 3")
    def test_rejeita_dimensoes(self):
        with self.assertRaises(ErroOmega): build('parametro matriz W=[[1,2]]; vetor x=[1,2,3]; tensor y=W@x;')
    def test_rejeita_tensores_heterogeneos(self):
        with self.assertRaises(ErroOmega):build('parametro matriz W=[[1,2],[3]];')
    def test_rejeita_perda_vetorial(self):
        with self.assertRaises(ErroOmega): build('perda f=[1,2];')
    def test_rejeita_identificador(self):
        with self.assertRaises(ErroOmega):build('perda f=incerto^2;')
    def test_relu_duplicado_idempotente(self):
        v=run('parametro x=-2; perda f=relu(relu(x))+1; mostrar f;')
        self.assertEqual(v.saidas[-1],'f = 1')
    def test_potencia_lateral(self):
        self.assertEqual(run('parametro x=3; perda f=x^2; mostrar f;').saidas[-1],'f = 9')
    def test_taxa_zero_erro(self):
        with self.assertRaises(ErroOmega):run('parametro x=2; perda f=x^2; passo f em x taxa 0;')
    def test_taxa_negativa_erro(self):
        with self.assertRaises(ErroOmega):run('parametro x=2; perda f=x^2; passo f em x taxa -1;')
    def test_declaracao_repetida(self):
        with self.assertRaises(ErroOmega):build('parametro x=1; parametro x=2;')
    def test_expoente_limite(self):
        with self.assertRaises(ErroOmega):build('parametro x=1; perda f=x^21;')
    def test_zeros_identidade(self):
        ir=build('parametro matriz W=identidade(3); parametro vetor b=zeros(3); perda f=soma(W)+soma(b);')
        v=MaquinaV1(ir).executar()
        self.assertEqual(v.frente()[ir['perdas']['f']],F(3))
    def test_formas_grandes_sem_polynomial(self):
        ir=build('parametro matriz W=zeros(128,128); parametro vetor x=zeros(128); perda f=soma(W@x);')
        self.assertLess(len(ir['nos']),20)
        self.assertEqual(ir['nos'][ir['simbolos']['W']]['forma'],[128,128])
    def test_erro_memoria_tamanho(self):
        with self.assertRaises(ErroOmega):build('parametro matriz W=zeros(2048,2048);')
    def test_matriz_matriz_produto(self):
        ir=build('matriz A=[[1,2],[3,4]]; matriz B=[[2,0],[0,3]]; matriz C=A@B; perda f=soma(C);')
        self.assertEqual(MaquinaV1(ir).frente()[ir['perdas']['f']],F(26))
    def test_divisao_exata(self):
        v=run('parametro x=2; perda f=x/3; mostrar f;')
        self.assertEqual(v.saidas[-1],'f = 2/3')


class TestesProvaV1(unittest.TestCase):
    def setUp(self):
        self.m=run(BASE+'gradientes custo; passo custo em W taxa 1/16;')
        self.c=self.m.certificados[-1]
    def test_gradiente_matriz(self):
        self.assertEqual(self.c['gradientes']['W'],[['6','12'],['2','4']])
    def test_gradiente_vetor(self):
        self.assertEqual(self.c['gradientes']['b'],['6','2'])
    def test_certificado_bom(self):self.assertTrue(verificar_certificado_v1(self.c))
    def test_perda_monotonica(self):
        self.assertEqual(F(self.c['perda_antes']),10)
        self.assertEqual(F(self.c['perda_depois']),F(45,32))
    def test_corromper_gradiente(self):
        d=copy.deepcopy(self.c);d['gradientes']['W'][0][0]='999'
        self.assertFalse(verificar_certificado_v1(d))
    def test_corromper_passo(self):
        d=copy.deepcopy(self.c);d['estado_depois']['W'][0][0]='2'
        self.assertFalse(verificar_certificado_v1(d))
    def test_corromper_perda(self):
        d=copy.deepcopy(self.c);d['perda_depois']='0'
        self.assertFalse(verificar_certificado_v1(d))
    def test_corromper_shape_ir(self):
        d=copy.deepcopy(self.c); d['ir']['nos'][d['ir']['simbolos']['W']]['forma']=[3,2]
        self.assertFalse(verificar_certificado_v1(d))
    def test_corromper_op(self):
        d=copy.deepcopy(self.c); d['ir']['nos'][d['ir']['perdas']['custo']]['op']='__import__'
        self.assertFalse(verificar_certificado_v1(d))
    def test_corromper_semente(self):
        m=run(BASE+'passo_ruidoso custo em W taxa 1/16 semente 72;')
        d=copy.deepcopy(m.certificados[-1]);d['semente']=55
        self.assertFalse(verificar_certificado_v1(d))
    def test_passo_livre_pode_aumentar(self):
        m=run('parametro x=1; perda f=x^2; passo_livre f em x taxa 2;')
        self.assertEqual(m.saidas[-1],'passo_livre x: 1 -> 9 (taxa 2)')
        self.assertTrue(verificar_certificado_v1(m.certificados[0]))
    def test_passo_seguro_rejeita_aumento(self):
        with self.assertRaisesRegex(ErroOmega,'Passo rejeitado'):
            run('parametro x=1; perda f=x^2; passo f em x taxa 2;')
    def test_passo_ruidoso_reprodutivel(self):
        s=BASE+'passo_ruidoso custo em W taxa 1/16 semente 11;'
        self.assertEqual(run(s).certificados,run(s).certificados)
    def test_passo_ruidoso_alterar_ruido(self):
        s=BASE+'passo_ruidoso custo em W taxa 1/16 semente 11;'
        c=copy.deepcopy(run(s).certificados[0]);c['estado_depois']['W'][1][1]='456'
        self.assertFalse(verificar_certificado_v1(c))
    def test_gradiente_zero_reconhecido(self):
        v=run('parametro x=0; perda f=relu(x); gradiente f em x;')
        self.assertEqual(v.certificados[0]['gradientes']['x'],'0')
    def test_necessidade_comando_taxa(self):
        d=copy.deepcopy(self.c);d['taxa']='1/32'
        self.assertFalse(verificar_certificado_v1(d))
    def test_tamanho_grande_verificacao_direcional(self):
        s='parametro vetor x=zeros(70); perda f=soma(x); gradientes f;'
        c=run(s).certificados[0]
        self.assertTrue(verificar_certificado_v1(c))
        c['gradientes']['x'][0]='42'
        self.assertFalse(verificar_certificado_v1(c))


class TestesOtimizadorV1(unittest.TestCase):
    def setUp(self):
        self.ir=build('''parametro matriz W=[[1,2],[3,4]]; vetor x=[2,1];
            tensor M=transposta(transposta(W));
            tensor y=relu(relu(M@x));
            perda f=dot(y,y)+0;
            mostrar f;''')
        self.optim,self.proof=otimizar(self.ir)
    def test_encolhe(self): self.assertLess(len(self.optim['nos']),len(self.ir['nos']))
    def test_prova_valida(self):self.assertTrue(validar_otimizacao(self.proof))
    def test_mesmo_resultado(self):
        a=MaquinaV1(self.ir).executar().saidas
        b=MaquinaV1(self.optim).executar().saidas
        self.assertEqual(a,b)
    def test_adulterar_prova(self):
        d=copy.deepcopy(self.proof);d['mapeamento'][-1]=0
        self.assertFalse(validar_otimizacao(d))
    def test_adulterar_resultado(self):
        d=copy.deepcopy(self.proof);d['otimizado']['nos'][0]['v']='987'
        self.assertFalse(validar_otimizacao(d))
    def test_sem_otimizacoes(self):
        ir=build('parametro x=2; perda f=x^2;')
        novo,cert=otimizar(ir)
        self.assertEqual(ir['nos'],novo['nos'])
        self.assertTrue(validar_otimizacao(cert))
    def test_regra_potencia_um(self):
        ir=build('parametro x=2; perda f=x^1; mostrar f;')
        novo,cert=otimizar(ir)
        self.assertEqual(MaquinaV1(novo).executar().saidas[-1],'f = 2')
        self.assertIn('pow_one',[x['regra'] for x in cert['regras']])
    def test_regra_dupla_negacao(self):
        ir=build('parametro x=2; perda f=-(-x);')
        _,cert=otimizar(ir)
        self.assertIn('double_neg',[x['regra'] for x in cert['regras']])


class TestesFerramentasV1(unittest.TestCase):
    def test_exportar_lean(self):
        c=run('parametro x=3; perda f=x^2; passo f em x taxa 1/4;').certificados
        texto=gerar_lean(c)
        self.assertIn('import Mathlib',texto)
        self.assertIn('by norm_num',texto)
        self.assertIn('monotonia_',texto)
    def test_cli_v1_completo(self):
        s=BASE+'passo custo em W taxa 1/16; mostrar custo;'
        with tempfile.TemporaryDirectory() as dir:
            root=Path(dir);source=root/'p.omega';source.write_text(s)
            compiled=root/'p.omc'; cert=root/'c.json';lean=root/'proof.lean'
            self.assertEqual(principal(['compile',str(source),'-o',str(compiled)]),0)
            self.assertEqual(principal(['run',str(compiled),'--certificados',str(cert)]),0)
            self.assertEqual(principal(['verify',str(cert)]),0)
            self.assertEqual(principal(['export-lean',str(cert),'-o',str(lean)]),0)
            self.assertIn('norm_num',lean.read_text())
    def test_cli_otimizador(self):
        with tempfile.TemporaryDirectory() as dir:
            root=Path(dir);f=root/'p.omega';f.write_text('parametro x=2; perda f=x+0; mostrar f;')
            opt=root/'opt.omc'; proof=root/'p.json'
            self.assertEqual(principal(['optimize',str(f),'-o',str(opt),'--prova',str(proof)]),0)
            self.assertEqual(principal(['verify',str(proof)]),0)
            self.assertEqual(principal(['run',str(opt)]),0)
    def test_cli_classico_compatibilidade(self):
        with tempfile.TemporaryDirectory() as dir:
            source=Path(dir)/'teste.omega'
            source.write_text('parametro x=2; perda f=x^2; passo f em x taxa 1/4;')
            self.assertEqual(principal(['run',str(source)]),0)
            self.assertEqual(principal(['check',str(source)]),0)
    def test_ir_invalid_document(self):
        with tempfile.TemporaryDirectory() as dir:
            f=Path(dir)/'test.omc';f.write_text('{"formato":"omega-ir-2","nos":[]}')
            self.assertEqual(principal(['run',str(f)]),1)


if __name__=='__main__': unittest.main()

class TestesAutotransformacaoControlada(unittest.TestCase):
    def test_mutacao_aceita(self):
        fonte='parametro x=2; perda f=relu(relu(x))+0; mostrar f;'
        m=run(fonte)
        antigo=m.frente()[m.ir['perdas']['f']]
        prova=m.auto_otimizar()
        self.assertTrue(validar_otimizacao(prova))
        self.assertEqual(m.frente()[m.ir['perdas']['f']], antigo)
        self.assertGreater(len(prova['regras']),0)
    def test_mutacao_rejeita_certificado_falso(self):
        m=run('parametro x=2; perda f=x+0;')
        novo,cert=otimizar(m.ir)
        cert['regras'][0]['regra']='regra_inexistente'
        with self.assertRaises(ErroOmega):m.substituir_ir(novo,cert)
    def test_mutacao_preserva_estado_treinado(self):
        m=run('parametro x=2; perda f=x^2+0; passo f em x taxa 1/4;')
        x=m.estado['x']
        m.auto_otimizar()
        self.assertEqual(m.estado['x'],x)
        self.assertEqual(x,F(1))
