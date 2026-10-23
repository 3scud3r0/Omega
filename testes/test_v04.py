"""Regressão 0.4: matrizes/vetores mutáveis, AD tensorial e provas independentes."""
from __future__ import annotations

import copy
from fractions import Fraction
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from omega.algebra import normalizar
from omega.autodiff_tensor import retropropagar_tensores
from omega.execucao import MaquinaOmega, verificar_certificado
from omega.sintaxe import ErroOmega, analisar, comando_de_dict, comando_para_dict
from omega.tipos import checar_tipos

ROOT = Path(__file__).resolve().parents[1]


def rodar(codigo):
    return MaquinaOmega().executar(analisar(codigo))


class ParametrosTensoriais(unittest.TestCase):
    def test_dimensoes_e_inicializacao(self):
        src = 'parametro vetor a=[1,2]; parametro matriz B=[[3,4],[5,6]]; mostrar a; mostrar B;'
        maquina = rodar(src)
        self.assertEqual(checar_tipos(analisar(src)).simbolos['a'], 'ParametroVetor[2]')
        self.assertEqual(checar_tipos(analisar(src)).simbolos['B'], 'ParametroMatriz[2,2]')
        self.assertIn("a = ['1', '2']", maquina.saidas)
        self.assertIn("B = [['3', '4'], ['5', '6']]", maquina.saidas)

    def test_gradiente_vetor_passo_exato(self):
        m = rodar('parametro vetor w=[3,4]; perda L=dot(w,w); gradiente L em w; passo L em w taxa 1/4; mostrar w; mostrar L;')
        self.assertIn("d(L)/d(w) [tensor] = ['6', '8']", m.saidas)
        self.assertIn("w = ['3/2', '2']", m.saidas)
        self.assertIn('L = 25/4', m.saidas)
        self.assertTrue(all(verificar_certificado(c) for c in m.certificados))

    def test_gradiente_matriz_e_atualizacao(self):
        m = rodar('parametro matriz W=[[1,2],[3,4]]; vetor x=[1,2]; perda L=dot(W@x,W@x); gradiente L em W; passo L em W taxa 1/100;')
        self.assertIn("d(L)/d(W) [tensor] = [['10', '20'], ['22', '44']]", m.saidas)
        self.assertEqual(m.parametros['__omega_coord_W_0_0'], Fraction(9,10))
        self.assertTrue(all(verificar_certificado(c) for c in m.certificados))

    def test_gradientes_escalares_e_tensoriais(self):
        m = rodar('parametro a=2; parametro vetor w=[1,2]; perda L=dot(a*w,a*w); gradientes L;')
        self.assertIn('d(L)/d(a) [reverso] = 20', m.saidas)
        self.assertIn("d(L)/d(w) [reverso tensorial] = ['8', '16']", m.saidas)
        self.assertTrue(verificar_certificado(m.certificados[-1]))

    def test_matriz_dinamica_reflete_atualizacao(self):
        m = rodar('parametro matriz W=[[2,0],[0,2]]; tensor A=transposta(W); vetor x=[1,1]; tensor z=A@x; perda L=dot(z,z); passo L em W taxa 1/8; mostrar z;')
        self.assertIn("z = ['1', '1']", m.saidas)

    def test_passo_recusado_sem_mutacao(self):
        cmds = analisar('parametro vetor w=[1,1]; perda L=dot(w,w); passo L em w taxa 2;')
        m = MaquinaOmega()
        with self.assertRaisesRegex(ErroOmega, 'rejeitado'):
            m.executar(cmds)
        self.assertEqual(m.parametros['__omega_coord_w_0'], Fraction(1))
        self.assertEqual(m.parametros['__omega_coord_w_1'], Fraction(1))
        self.assertFalse(any(c['tipo'] == 'passo_tensor' for c in m.certificados))

    def test_taxa_zero_ou_negativa(self):
        for taxa in ('0','-1'):
            with self.subTest(taxa=taxa), self.assertRaisesRegex(ErroOmega, 'positiva'):
                rodar(f'parametro vetor w=[1,2]; perda L=dot(w,w); passo L em w taxa {taxa};')

    def test_erro_forma_na_declaracao(self):
        casos = ['parametro vetor w=[[1,2]];', 'parametro matriz W=[1,2];',
                 'parametro vetor w=[1,2]; parametro matriz w=[[1]];',
                 'parametro matriz W=[[1,2],[3]];']
        for texto in casos:
            with self.subTest(texto=texto), self.assertRaises(ErroOmega):
                checar_tipos(analisar(texto))

    def test_codigo_fonte_nao_acessa_nomes_internos(self):
        for fonte in ('parametro __omega_coord_w_0=1;',
                      'perda L=__omega_coord_w_0+1;'):
            with self.assertRaises(ErroOmega):
                analisar(fonte)

    def test_regressao_sintaxe_da_versao_03(self):
        m = rodar('parametro x=2; parametro y=-1; matriz A=[[2,1],[1,3]]; vetor v=[x,y]; perda L=dot(A@v,A@v); gradientes L;')
        self.assertIn('d(L)/d(x) [reverso] = 10', m.saidas)
        self.assertIn('d(L)/d(y) [reverso] = 0', m.saidas)

    def test_tipos_invalidos_nao_modificam_nenhum_estado(self):
        m = MaquinaOmega()
        with self.assertRaises(ErroOmega):
            m.executar(analisar('parametro vetor w=[1,2]; perda L=dot(w,w); parametro x=y;'))
        self.assertEqual(m.parametros, {})

    def test_provas_alteradas_sao_rejeitadas(self):
        m = rodar('parametro matriz W=[[2,1],[1,2]]; vetor x=[1,2]; perda L=dot(W@x,W@x); gradiente L em W; passo L em W taxa 1/32;')
        grad = next(c for c in m.certificados if c['tipo'] == 'gradiente_tensor')
        passo = next(c for c in m.certificados if c['tipo'] == 'passo_tensor')
        for chave, modificador in [
            ('resultado', lambda c: c['resultado'][0].__setitem__(0, '999')),
            ('coordenadas', lambda c: c['coordenadas'][1].__setitem__(0, 'inexistente')),
        ]:
            cert = copy.deepcopy(grad)
            modificador(cert)
            self.assertFalse(verificar_certificado(cert), chave)
        casos = [
            lambda c: c['estado_depois'].__setitem__('__omega_coord_W_0_0', '999'),
            lambda c: c['gradientes'][0].__setitem__(0, '-999'),
            lambda c: c.__setitem__('perda_depois', '-999'),
            lambda c: c.__setitem__('taxa', '500'),
            lambda c: c['coordenadas'][0].__setitem__(0, 'nao_existe'),
        ]
        for alterar in casos:
            cert = copy.deepcopy(passo)
            alterar(cert)
            self.assertFalse(verificar_certificado(cert))

    def test_formato_intermediario_compilado(self):
        src = (ROOT/'exemplos/parametros_matriciais.omega')
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta)/'modelo.omc'
            provas = Path(pasta)/'provas.json'
            proc = subprocess.run([sys.executable,'-m','omega','compile',str(src),'-o',str(arquivo)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            proc = subprocess.run([sys.executable,'-m','omega','run',str(arquivo),'--certificados',str(provas)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertIn('2205/2048',proc.stdout)
            proc = subprocess.run([sys.executable,'-m','omega','verify',str(provas)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)

    def test_serializacao_comando_tensor(self):
        x = analisar('parametro matriz W=[[1/2,0],[0,1]];')[0]
        self.assertEqual(x, comando_de_dict(comando_para_dict(x)))

    def test_fuzz_ad_reverso_vs_derivacao_algebrica(self):
        rng = random.Random(404)
        for _ in range(30):
            m, n = rng.randint(1, 3), rng.randint(1, 3)
            W = [[rng.randint(-3, 3) for _ in range(n)] for _ in range(m)]
            v = [rng.randint(-3, 3) for _ in range(n)]
            def lit(v):
                return '[' + ','.join(lit(x) if isinstance(x,list) else str(x) for x in v) + ']'
            src=f'parametro matriz W={lit(W)}; parametro vetor x={lit(v)}; perda L=dot(W@x,W@x); gradientes L;'
            maquina=rodar(src)
            expr=maquina.perdas['L']
            p=normalizar(expr)
            ad = retropropagar_tensores(maquina.perdas_originais['L'], maquina.tensores, maquina.parametros)
            for nome, valor in ad.items():
                self.assertEqual(valor, p.derivar(nome).avaliar(maquina.parametros))
            self.assertTrue(all(verificar_certificado(c) for c in maquina.certificados))

    def test_fuzz_matriz_vezes_matriz(self):
        rng=random.Random(24)
        for _ in range(12):
            m,k,n = rng.randint(1,2), rng.randint(1,3), rng.randint(1,2)
            W=[[rng.randint(-2,2) for _ in range(k)] for _ in range(m)]
            B=[[rng.randint(-2,2) for _ in range(n)] for _ in range(k)]
            def lit(v):
                return '['+','.join(lit(x) if isinstance(x,list) else str(x) for x in v)+']'
            src = f'parametro matriz W={lit(W)}; matriz B={lit(B)}; tensor P=W@B; perda L=dot(P@[1{",1"*(n-1)}],P@[1{",1"*(n-1)}]); gradientes L;'
            maquina=rodar(src)
            p=normalizar(maquina.perdas['L'])
            r=retropropagar_tensores(maquina.perdas_originais['L'],maquina.tensores,maquina.parametros)
            for nome, valor in r.items():
                self.assertEqual(valor, p.derivar(nome).avaliar(maquina.parametros))

if __name__ == '__main__':
    unittest.main()
