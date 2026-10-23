"""Testes da linguagem Ômega 0.2 (tipos e núcleo isolado)."""
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
from omega.execucao import MaquinaOmega, verificar_certificado
from omega.nucleo import avaliar, derivada, forma_normal, polinomio
from omega.sintaxe import ErroOmega, analisar, comando_de_dict, comando_para_dict, expressao_para_dict
from omega.tipos import checar_tipos

ROOT = Path(__file__).parents[1]


class Tipos02(unittest.TestCase):
    def test_teorema_exemplo(self):
        fonte = (ROOT / "exemplos/tipos_e_teoremas.omega").read_text(encoding="utf8")
        comandos = analisar(fonte)
        t = checar_tipos(comandos)
        self.assertEqual(t.simbolos["x"], "Parametro")
        self.assertEqual(t.simbolos["objetivo"], "Polinomio")
        self.assertEqual(t.simbolos["quadrado_da_soma"], "Prova")
        m = MaquinaOmega().executar(comandos)
        self.assertIn("VERIFICADO: teorema quadrado_da_soma", m.saidas)
        self.assertTrue(all(map(verificar_certificado, m.certificados)))

    def test_round_trip_comandos_novos(self):
        cs = analisar("teorema eq = (a+b)^2 == a^2+2*a*b+b^2; verificar eq;")
        self.assertEqual(cs, [comando_de_dict(comando_para_dict(c)) for c in cs])

    def test_teorema_falso_recusado(self):
        with self.assertRaisesRegex(ErroOmega, "falsa"):
            MaquinaOmega().executar(analisar("teorema mentira = a^2 == a;"))

    def test_teorema_nao_declarado(self):
        with self.assertRaisesRegex(ErroOmega, "não declarado"):
            checar_tipos(analisar("verificar desconhecido;"))

    def test_tipo_errado_gradiente(self):
        with self.assertRaisesRegex(ErroOmega, "esperado Parametro"):
            checar_tipos(analisar("parametro x=1; perda f=x^2; gradiente f em f;"))

    def test_tipo_errado_passo(self):
        with self.assertRaisesRegex(ErroOmega, "esperado Polinomio"):
            checar_tipos(analisar("parametro x=1; passo x em x taxa 1/4;"))

    def test_perda_referenciada_como_parametro(self):
        with self.assertRaisesRegex(ErroOmega, "esperado Parametro"):
            checar_tipos(analisar("parametro x=1; perda f=x^2; parametro y=f+2;"))

    def test_ast_nao_pode_esconder_variavel_cancelada(self):
        with self.assertRaisesRegex(ErroOmega, "não declarado"):
            checar_tipos(analisar("parametro x=1; perda f=(nao_declarada-nao_declarada)+x;"))

    def test_prova_nomeada_nao_e_parametro(self):
        with self.assertRaisesRegex(ErroOmega, "esperado Parametro"):
            checar_tipos(analisar("teorema eq = a^2 == a*a; parametro x = eq;"))

    def test_colisao_prova_perda(self):
        with self.assertRaisesRegex(ErroOmega, "já declarado"):
            checar_tipos(analisar("teorema eq = a == a; perda eq=1;"))

    def test_impedir_mutacao_se_comando_posterior_tem_tipo_invalido(self):
        maquina = MaquinaOmega()
        with self.assertRaises(ErroOmega):
            maquina.executar(analisar("parametro x=1; perda f=x^2; gradiente f em f;"))
        self.assertEqual(maquina.parametros, {})
        self.assertEqual(maquina.saidas, [])

    def test_arquivo_compilado_valida_tipo_de_novo(self):
        from omega.cli import ler_comandos
        with tempfile.TemporaryDirectory() as pasta:
            alvo = Path(pasta) / 's.omc'
            p = subprocess.run([sys.executable, "-m", "omega", "compile",
                                str(ROOT / 'exemplos/tipos_e_teoremas.omega'),
                                '-o', str(alvo)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            t = checar_tipos(ler_comandos(alvo))
            self.assertIn('quadrado_da_soma', t.simbolos)
            for action in ('run', 'types', 'check'):
                r = subprocess.run([sys.executable, '-m', 'omega', action, str(alvo)],
                                   cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)


class Nucleo02(unittest.TestCase):
    def test_sem_dependencia_da_algebra_executor(self):
        from omega import nucleo
        self.assertNotIn('omega.algebra', nucleo.__dict__)

    def test_certificado_alterado_forma(self):
        m = MaquinaOmega().executar(analisar("teorema e=(u+v)^2 == u^2+2*u*v+v^2;"))
        falso = copy.deepcopy(m.certificados[0])
        falso['forma_normal'][0]['coeficiente'] = '999'
        self.assertFalse(verificar_certificado(falso))

    def test_certificado_passo_alterado_gradiente(self):
        m = MaquinaOmega().executar(analisar("parametro x=3; perda f=x^2; passo f em x taxa 1/4;"))
        falso = copy.deepcopy(m.certificados[0])
        falso['gradiente'] = '0'
        self.assertFalse(verificar_certificado(falso))

    def test_identidade_como_divisao_constante(self):
        m = MaquinaOmega().executar(analisar("provar x/2+x/2 == x;"))
        self.assertTrue(verificar_certificado(m.certificados[0]))

    def test_truncamento_de_certificado(self):
        self.assertFalse(verificar_certificado({"tipo":"identidade"}))
        self.assertFalse(verificar_certificado({"tipo":"passo"}))
        self.assertFalse(verificar_certificado({"tipo":"gradiente"}))
        self.assertFalse(verificar_certificado({"tipo":"inesperado"}))

    def test_tabela_verdade_simbologica_aleatoria(self):
        # Comparações independentes entre o executor e o núcleo usando 120 polinômios.
        r = random.Random(20261023)
        atomos = ['x', 'y', 'z', '-2', '0', '1', '1/3', '(x+y)']
        for _ in range(120):
            termos = []
            for __ in range(5):
                a, b = r.choice(atomos), r.choice(atomos)
                termos.append(f'({a})*({b})')
            fonte = '+'.join(termos)
            expr = analisar(f'provar {fonte} == {fonte};')[0].expressao
            direto = normalizar(expr)
            kernel = polinomio(expressao_para_dict(expr))
            self.assertEqual(direto.forma_normal(), forma_normal(kernel))
            estado = {'x':Fraction(r.randint(-3,3)), 'y':Fraction(r.randint(-3,3)), 'z':Fraction(r.randint(-3,3))}
            self.assertEqual(direto.avaliar(estado), avaliar(kernel, estado))
            for var in estado:
                self.assertEqual(direto.derivar(var).avaliar(estado), avaliar(derivada(kernel, var), estado))


if __name__ == '__main__':
    unittest.main()
