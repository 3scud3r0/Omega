"""Comprovação finita e ataques ao novo código de política automodificável."""
import unittest, copy, json, tempfile
from pathlib import Path
from fractions import Fraction
from omega.nucleo_meta import (TREINO,TESTE,BASE,GENES,candidatos,contagens,
                               otimo,verificar,certificado_completude,escore,alvo,saidas,digest)
from omega.meta_programa import fonte_politica
from omega.metaevolucao import construir,exportar,auditar,executar_codigo,conferir_vm
from omega.cli import principal
from omega.sintaxe import ErroOmega

class MetaCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.doc=construir()
    def test_split(self):
        self.assertEqual(len(TREINO),8);self.assertEqual(len(TESTE),8)
        self.assertEqual(set(TREINO)|set(TESTE),set(range(16)))
        self.assertFalse(set(TREINO)&set(TESTE))
    def test_representabilidade(self):
        self.assertTrue(certificado_completude())
        self.assertEqual(len(GENES),625)
        self.assertEqual(len({saidas(g) for g in GENES if all(n in (0,1) for n in saidas(g))}),16)
    def test_otimalidade_exaustiva_politica(self):
        for fase in range(3):
            self.assertEqual(tuple(self.doc['geracoes'][fase]['pesos']),otimo(fase))
    def test_reduz_treino(self):
        self.assertEqual([r['treino_total'] for r in self.doc['geracoes']],[2902,617,481])
    def test_melhora_reserva(self):
        self.assertEqual([r['teste_total'] for r in self.doc['geracoes']],[3106,648,437])
    def test_politica_realmente_mudou(self):
        self.assertEqual(self.doc['geracoes'][-1]['pesos'],[1,-1,0,0,0])
        self.assertNotEqual(fonte_politica(BASE),fonte_politica(self.doc['geracoes'][-1]['pesos']))
    def test_verificacao_integral(self):self.assertTrue(verificar(self.doc))
    def test_rejeita_falso_peso_hash_refeito(self):
        d=copy.deepcopy(self.doc);r=d['geracoes'][2]
        r['pesos']=[1,1,0,0,0]
        r['id']=digest({k:v for k,v in r.items() if k!='id'})
        d['hash']=digest({k:v for k,v in d.items() if k!='hash'})
        self.assertFalse(verificar(d))
    def test_rejeita_contagens_hash_refeito(self):
        d=copy.deepcopy(self.doc);r=d['geracoes'][2];r['teste_total']=1
        r['id']=digest({k:v for k,v in r.items() if k!='id'})
        d['hash']=digest({k:v for k,v in d.items() if k!='hash'})
        self.assertFalse(verificar(d))
    def test_rejeita_falso_split(self):
        d=copy.deepcopy(self.doc);d['teste']=d['treino'];self.assertFalse(verificar(d))
    def test_rejeita_perda_inventada(self):
        d=copy.deepcopy(self.doc);d['geracoes'][0]['treino_total']=1
        self.assertFalse(verificar(d))
    def test_sintaxe_da_politica(self):
        ir,m=executar_codigo(fonte_politica(self.doc['geracoes'][-1]['pesos']))
        self.assertTrue(conferir_vm(m,ir,self.doc['geracoes'][-1]['pesos']))
    def test_execucao_nao_python_eval(self):
        with self.assertRaises(ErroOmega):executar_codigo('parametro x = __import__("os");')
    def test_custo_completo_exato(self):
        for fase in range(3):
            p=self.doc['geracoes'][fase]['pesos'];n=contagens(p)
            self.assertEqual(sum(n[i] for i in TREINO),self.doc['geracoes'][fase]['treino_total'])
    def test_assinatura_hash_nao_prova(self):
        d=copy.deepcopy(self.doc);d['geracoes'][2]['pesos']=[100]*5
        d['hash']=digest({k:v for k,v in d.items() if k!='hash'})
        self.assertFalse(verificar(d))

class TesteMetaArquivos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.p=Path(cls.temp.name)
        exportar(cls.p)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_auditar(self):
        r=auditar(self.p);self.assertTrue(r['completude_16']);self.assertEqual(r['politicas_finais_verificadas'],243)
    def test_cli_verificador(self):
        self.assertEqual(principal(['verify-meta',str(self.p/'certificado_meta.json')]),0)
    def test_cli_auditor(self):self.assertEqual(principal(['audit-meta',str(self.p)]),0)
    def test_tres_codigos(self):
        self.assertTrue((self.p/'politica_0.omega').exists())
        self.assertTrue((self.p/'politica_2.omega').exists())
    def test_adulteracao_codigo(self):
        file=self.p/'politica_2.omega'; old=file.read_text()
        try:
            file.write_text(old.replace('tensor prioridade','tensor prioridadeFALSA'))
            with self.assertRaises(ErroOmega):auditar(self.p)
        finally:file.write_text(old)
    def test_adulteracao_compilado(self):
        file=self.p/'politica_2.omc'; old=file.read_text();parsed=json.loads(old)
        try:
            parsed['nos'][0]['v']='1000';file.write_text(json.dumps(parsed))
            with self.assertRaises(ErroOmega):auditar(self.p)
        finally:file.write_text(old)
    def test_adulteracao_certificado(self):
        file=self.p/'certificado_meta.json';old=file.read_text();d=json.loads(old)
        try:
            d['geracoes'][2]['avaliacoes']=[1]*16;file.write_text(json.dumps(d))
            with self.assertRaises(ErroOmega):auditar(self.p)
        finally:file.write_text(old)

if __name__=='__main__':unittest.main()
