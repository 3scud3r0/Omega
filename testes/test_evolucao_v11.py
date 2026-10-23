"""Testes de autoevolução FORMALMENTE LIMITADA da Ômega 1.1.
Não são provas de AGI: os testes auditam a implementação; a prova finita
propriamente dita é reexecutada em nucleo_evolucao.py.
"""
import copy
from fractions import Fraction as Q
from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from omega.cli import principal
from omega.evolucao import (sintetizar, exportar_evolucao, auditar_artefatos,
                           executar_hipotese, compilar_fonte, verificar_execucao,
                           programa_lean)
from omega.nucleo_evolucao import (verificar_evolucao, provar_xor_exaustivo,
                                   melhor_no_raio, perda_fechada, digest)
from omega.motor_v1 import MaquinaV1
from omega.otimizador_v1 import otimizar, validar_otimizacao
from omega.sintaxe import ErroOmega


class TesteSinteseExaustiva(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documento=sintetizar(2)

    def test_tres_geracoes(self):
        self.assertEqual([r['perda'] for r in self.documento['geracoes']], ['2','1','0'])

    def test_comprovacao_completa(self):
        self.assertTrue(provar_xor_exaustivo(self.documento))

    def test_certificado_completo(self):
        self.assertTrue(verificar_evolucao(self.documento))

    def test_coeficientes(self):
        self.assertEqual(self.documento['geracoes'][-1]['genes'],[1,-2,0])

    def test_optimalidade_exaustiva(self):
        for raio in range(3):
            self.assertEqual(self.documento['geracoes'][raio]['genes'], melhor_no_raio(raio))

    def test_perda_fechada(self):
        for raio in range(3):
            rec=self.documento['geracoes'][raio]
            self.assertEqual(Q(rec['perda']), Q(perda_fechada(rec['genes'])))

    def test_tabela_xor(self):
        self.assertEqual(self.documento['geracoes'][-1]['tabela'],['0','1','1','0'])

    def test_nenhuma_falsa_generalizacao(self):
        # XOR só foi provado para entradas booleanas: para (2,0) resulta 0,
        # para (3,0) resulta -1. Isso não é XOR binário em entradas não booleanas.
        self.assertEqual(executar_hipotese([1,-2,0],3,0),Q(-1))

    def test_rejeita_falso_gradiente_ou_falso_zero(self):
        d=copy.deepcopy(self.documento);d['geracoes'][-1]['perda']='-1'
        self.assertFalse(verificar_evolucao(d))

    def test_rejeita_tabela_adulterada(self):
        d=copy.deepcopy(self.documento);d['geracoes'][-1]['tabela']=['0','1','0','0']
        self.assertFalse(verificar_evolucao(d))

    def test_rejeita_fonte_adulterada(self):
        d=copy.deepcopy(self.documento);d['geracoes'][-1]['fonte']+='perda extra=9;'
        self.assertFalse(verificar_evolucao(d))

    def test_rejeita_genes_falsos_com_hash_recalculado(self):
        d=copy.deepcopy(self.documento);r=d['geracoes'][-1]
        r['genes']=[2,-2,0]
        r['id']=digest({k:v for k,v in r.items() if k!='id'})
        self.assertFalse(verificar_evolucao(d))

    def test_rejeita_prova_autenticada_por_hash_apenas(self):
        d=copy.deepcopy(self.documento);r=d['geracoes'][-1]
        r['tabela']=['0','0','0','0']
        r['id']=digest({k:v for k,v in r.items() if k!='id'})
        self.assertFalse(verificar_evolucao(d))

    def test_rejeita_cadeia_quebrada(self):
        d=copy.deepcopy(self.documento);d['geracoes'][2]['anterior']='GENESIS'
        self.assertFalse(verificar_evolucao(d))

    def test_rejeita_geracao_excluida(self):
        d=copy.deepcopy(self.documento);d['geracoes'].pop(1)
        self.assertFalse(verificar_evolucao(d))

    def test_rejeita_raio_impossivel(self):
        with self.assertRaises(ErroOmega):sintetizar(5)
        with self.assertRaises(ErroOmega):sintetizar(-1)
        with self.assertRaises(ErroOmega):sintetizar(True)

    def test_parada_se_nao_melhorou(self):
        with self.assertRaisesRegex(ErroOmega,'Nenhuma melhoria'):sintetizar(3)


class TesteAutoModificacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=sintetizar(2)
        cls.genes=cls.doc['geracoes'][-1]['genes']
        cls.fonte=cls.doc['geracoes'][-1]['fonte']

    def test_compilar_e_executar_quatro_estados(self):
        ir=compilar_fonte(self.fonte)
        self.assertTrue(verificar_execucao(ir,self.genes))

    def test_auto_otimizacao_com_prova(self):
        ir=compilar_fonte(self.fonte)
        novo,cert=otimizar(ir)
        self.assertTrue(validar_otimizacao(cert))
        self.assertLess(len(novo['nos']),len(ir['nos']))
        self.assertTrue(verificar_execucao(novo,self.genes))

    def test_preserva_estado_parametros(self):
        ir=compilar_fonte(self.fonte)
        m=MaquinaV1(ir).executar()
        m.estado.update({'x':Q(1),'y':Q(0),'esperado':Q(1)})
        old=m.frente()[ir['simbolos']['saida']]
        prova=m.auto_otimizar()
        new=m.frente()[m.ir['simbolos']['saida']]
        self.assertEqual(old,new)
        self.assertEqual(m.estado['x'],Q(1))
        self.assertTrue(validar_otimizacao(prova))

    def test_prova_rejeita_graph_tamper(self):
        ir=compilar_fonte(self.fonte)
        novo,cert=otimizar(ir)
        tamper=copy.deepcopy(cert)
        tamper['otimizado']['nos'][-1]['args']=[0,0]
        self.assertFalse(validar_otimizacao(tamper))

    def test_gerado_lean_4_obrigacoes(self):
        texto=programa_lean(self.genes)
        self.assertEqual(texto.count('theorem xor_'),4)
        self.assertEqual(texto.count('  decide'),4)
        self.assertIn('namespace Omega',texto)

    def test_sem_exec_avaliacao_arbitraria(self):
        with self.assertRaises(ErroOmega):
            compilar_fonte(self.fonte.replace('relu(', '__import__('))


class TesteAuditoriaIntegrada(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.dir=Path(self.tmp.name)/'evolucao'
        exportar_evolucao(self.dir)
    def tearDown(self):self.tmp.cleanup()

    def test_auditoria_reproducivel(self):
        resultado=auditar_artefatos(self.dir)
        self.assertEqual(resultado['erro_final'],'0')
        self.assertTrue(resultado['xor_exaustivamente_provado'])

    def test_adulteracao_fonte_em_disco(self):
        p=self.dir/'programa_sucessor.omega';p.write_text(p.read_text()+'# modificado')
        with self.assertRaises(ErroOmega):auditar_artefatos(self.dir)

    def test_adulteracao_arquivo_compilado(self):
        p=self.dir/'codigo_compilado.omc';doc=json.loads(p.read_text())
        doc['nos'][0]['v']='999';p.write_text(json.dumps(doc))
        with self.assertRaises(ErroOmega):auditar_artefatos(self.dir)

    def test_adulteracao_prova_ir(self):
        p=self.dir/'prova_auto_otimizacao.json';doc=json.loads(p.read_text())
        doc['mapeamento'][0]=999;p.write_text(json.dumps(doc))
        with self.assertRaises(ErroOmega):auditar_artefatos(self.dir)

    def test_adulteracao_arquivo_lean(self):
        p=self.dir/'obrigacoes_lean.lean';p.write_text('theorem false : False := by sorry')
        with self.assertRaises(ErroOmega):auditar_artefatos(self.dir)

    def test_cli_auditoria(self):
        self.assertEqual(principal(['audit-evolution',str(self.dir)]),0)
        self.assertEqual(principal(['verify-evolution',str(self.dir/'cadeia_provada.json')]),0)

    def test_cli_erro_arquivo_inexistente(self):
        self.assertEqual(principal(['verify-evolution',str(self.dir/'NAO.json')]),1)


if __name__=='__main__':unittest.main()
