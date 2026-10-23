"""Suíte de regressão do núcleo Ômega 0.1 (biblioteca padrão unittest)."""
from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from omega.algebra import normalizar
from omega.execucao import MaquinaOmega, verificar_certificado
from omega.sintaxe import (
    ErroOmega, analisar, comando_de_dict, comando_para_dict,
    expressao_de_dict, expressao_para_dict,
)


def rodar(fonte: str) -> MaquinaOmega:
    return MaquinaOmega().executar(analisar(fonte))


def poly(fonte: str):
    return normalizar(analisar(f"provar {fonte} == {fonte};")[0].expressao)


class SintaxeTests(unittest.TestCase):
    def test_caracter_inesperado(self):
        with self.assertRaisesRegex(ErroOmega, "Caractere inesperado"):
            analisar("parametro x = 5 $ 3;")

    def test_sem_ponto_virgula(self):
        with self.assertRaisesRegex(ErroOmega, "Esperado ';'"):
            analisar("parametro x = 5")

    def test_precedencia_menos_exponencial(self):
        self.assertEqual(poly("-2^2").avaliar({}), -4)
        self.assertEqual(poly("(-2)^2").avaliar({}), 4)

    def test_potencia_associativa_a_direita(self):
        self.assertEqual(poly("2^2^3").avaliar({}), 256)

    def test_unicode(self):
        m = rodar("parametro θ = 4; perda erro = (θ - 1)^2; mostrar erro;")
        self.assertIn("erro = 9", m.saidas)

    def test_numeros_decimais_exatos(self):
        self.assertEqual(poly("0.1 + 0.2").avaliar({}), Fraction(3, 10))

    def test_sem_execucao_python(self):
        with self.assertRaises(ErroOmega):
            analisar("__import__('os').system('echo hello');")

    def test_aspas_nao_permitidas(self):
        with self.assertRaises(ErroOmega):
            analisar("parametro x = 'texto';")

    def test_alias_ingles(self):
        m = rodar("param x = 2; loss f = x^2; grad f wrt x; show f;")
        self.assertIn("d(f)/d(x) = 4", m.saidas)

    def test_ast_round_trip(self):
        cmds = analisar("parametro x = (2 + 1/3)^2; provar (a+b)^2 == a^2+2*a*b+b^2;")
        copia = [comando_de_dict(comando_para_dict(c)) for c in cmds]
        self.assertEqual(copia, cmds)
        expr = cmds[0].expressao
        self.assertEqual(expressao_de_dict(expressao_para_dict(expr)), expr)

    def test_ast_injetado_nao_tem_execucao(self):
        with self.assertRaises(ErroOmega):
            expressao_de_dict({"tipo": "bin", "op": "__import__", "esq": {}, "dir": {}})


class AlgebraTests(unittest.TestCase):
    def test_derivada_polynomial(self):
        p = poly("(x+1)^3 + 2*x*y")
        self.assertEqual(p.derivar("x"), poly("3*x^2 + 6*x + 3 + 2*y"))
        self.assertEqual(p.derivar("y"), poly("2*x"))

    def test_coeficientes_exatos(self):
        p = poly("1/3*x + 1/6*x")
        self.assertEqual(p, poly("x/2"))

    def test_derivada_constante(self):
        self.assertEqual(poly("42").derivar("x"), poly("0"))

    def test_potencia_zero(self):
        self.assertEqual(poly("(x+y)^0"), poly("1"))

    def test_divisao_variavel_rejeitada(self):
        with self.assertRaisesRegex(ErroOmega, "constante"):
            poly("x/y")

    def test_expoente_fracionario_rejeitado(self):
        with self.assertRaisesRegex(ErroOmega, "fracionário"):
            poly("x^(1/2)")

    def test_expoente_negativo_rejeitado(self):
        with self.assertRaisesRegex(ErroOmega, "Expoente"):
            poly("x^(-1)")

    def test_divisao_zero_rejeitada(self):
        with self.assertRaisesRegex(ErroOmega, "Divisão por zero"):
            poly("1/(2-2)")

    def test_limite_de_expoente(self):
        with self.assertRaisesRegex(ErroOmega, "Expoente"):
            poly("x^21")

    def test_identidade_exata(self):
        self.assertEqual(poly("(x + y)^4"),
                         poly("x^4 + 4*x^3*y + 6*x^2*y^2 + 4*x*y^3 + y^4"))


class MotorTests(unittest.TestCase):
    def test_exemplo(self):
        root = Path(__file__).parents[1]
        m = MaquinaOmega().executar(analisar(
            (root / "exemplos" / "primeiro_programa.omega").read_text(encoding="utf8")))
        self.assertEqual(m.parametros, {"x": Fraction(2), "y": Fraction(-3, 2)})
        self.assertEqual(m.avaliar(m.perdas["objetivo"]), Fraction(5, 4))
        self.assertEqual(len(m.certificados), 6)
        self.assertTrue(all(map(verificar_certificado, m.certificados)))

    def test_rejeitar_passo_que_aumenta_perda(self):
        with self.assertRaisesRegex(ErroOmega, "perda aumentaria"):
            rodar("parametro x=3; perda e=(x-1)^2; passo e em x taxa 2;")

    def test_rejeitar_taxa_zero(self):
        with self.assertRaisesRegex(ErroOmega, "Taxa deve ser positiva"):
            rodar("parametro x=3; perda e=x^2; passo e em x taxa 0;")

    def test_rejeitar_prova_falsa(self):
        with self.assertRaisesRegex(ErroOmega, "Identidade polinomial falsa"):
            rodar("provar (a+b)^2 == a^2+b^2;")

    def test_rejeitar_reescrita_invalida(self):
        with self.assertRaisesRegex(ErroOmega, "Reescrita rejeitada"):
            rodar("parametro x=1; perda f=x^2; reescrever f=x^2+1;")

    def test_variavel_nao_declarada(self):
        with self.assertRaisesRegex(ErroOmega, "não declarado"):
            rodar("perda erro = x^2;")

    def test_colisao_de_simbolos(self):
        with self.assertRaisesRegex(ErroOmega, "já declarado"):
            rodar("parametro x = 1; perda x = 1;")

    def test_certificado_alterado_e_rejeitado(self):
        m = rodar("parametro x=3; perda f=x^2; passo f em x taxa 1/4;")
        cert = json.loads(json.dumps(m.certificados[0]))
        cert["perda_depois"] = "0"
        self.assertFalse(verificar_certificado(cert))

    def test_estado_adulterado_rejeitado(self):
        m = rodar("parametro x=3; parametro y=5; perda f=x^2+y^2; passo f em x taxa 1/4;")
        cert = json.loads(json.dumps(m.certificados[0]))
        cert["estado_depois"]["y"] = "6"
        self.assertFalse(verificar_certificado(cert))

    def test_gradiente_adulterado_rejeitado(self):
        m = rodar("parametro x=3; perda f=x^2; gradiente f em x;")
        cert = json.loads(json.dumps(m.certificados[0]))
        cert["resultado"] = "100"
        self.assertFalse(verificar_certificado(cert))

    def test_iden_forma_alterada_rejeitada(self):
        m = rodar("provar (a+b)^2 == a^2+2*a*b+b^2;")
        cert = json.loads(json.dumps(m.certificados[0]))
        cert["forma_normal"] = []
        self.assertFalse(verificar_certificado(cert))

    def test_passo_perda_constante(self):
        m = rodar("parametro x=9; perda f=7; passo f em x taxa 1/3;")
        self.assertEqual(m.parametros["x"], Fraction(9))
        self.assertTrue(verificar_certificado(m.certificados[0]))


class FerramentasTests(unittest.TestCase):
    def test_cli_compilar_rodar_verificar(self):
        root = Path(__file__).parents[1]
        arquivo = root / "exemplos" / "primeiro_programa.omega"
        with tempfile.TemporaryDirectory() as pasta:
            intermediate = Path(pasta) / "teste.omc"
            certs = Path(pasta) / "proofs.json"
            for command in [
                ["compile", str(arquivo), "-o", str(intermediate)],
                ["check", str(intermediate)],
                ["run", str(intermediate), "--certificados", str(certs)],
                ["verify", str(certs)],
            ]:
                result = subprocess.run([sys.executable, "-m", "omega", *command],
                                        cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("omega-ir-1", intermediate.read_text())
            self.assertIn("omega-cert-1", certs.read_text())

    def test_cli_prova_falsa_exit_code(self):
        root = Path(__file__).parents[1]
        p = subprocess.run([sys.executable, "-m", "omega", "run",
                            str(root / "exemplos" / "prova_falsa.omega")],
                           cwd=root, capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("ERRO ÔMEGA", p.stderr)

    def test_cli_passo_ruim_exit_code(self):
        root = Path(__file__).parents[1]
        p = subprocess.run([sys.executable, "-m", "omega", "run",
                            str(root / "exemplos" / "passo_recusado.omega")],
                           cwd=root, capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("perda aumentaria", p.stderr)


if __name__ == "__main__":
    unittest.main()
