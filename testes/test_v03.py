"""Testes Ômega 0.3: formas, álgebra tensorial, tape reverso e kernel."""
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
from omega.autodiff import retropropagar
from omega.execucao import MaquinaOmega, verificar_certificado
from omega.sintaxe import ErroOmega, analisar, comando_de_dict, comando_para_dict
from omega.tipos import checar_tipos

ROOT = Path(__file__).resolve().parents[1]


def rodar(texto):
    return MaquinaOmega().executar(analisar(texto))


class TiposTensor(unittest.TestCase):
    def test_dimensoes_e_funcionalidade(self):
        m = rodar('parametro x=2; vetor v=[x,3]; matriz A=[[1,2],[3,4]]; tensor z=A@v; mostrar z;')
        self.assertIn("z = ['8', '18']", m.saidas)
        tipos = checar_tipos(analisar('parametro x=2; vetor v=[x,3]; matriz A=[[1,2],[3,4]]; tensor z=A@v;'))
        self.assertEqual(tipos.simbolos['z'], 'Vetor[2]')
        self.assertEqual(tipos.simbolos['A'], 'Matriz[2,2]')

    def test_mult_matrizes(self):
        m = rodar('matriz A=[[1,2],[3,4]]; matriz B=[[5,6],[7,8]]; tensor C=A@B; mostrar C;')
        self.assertIn("C = [['19', '22'], ['43', '50']]", m.saidas)

    def test_transposta(self):
        m = rodar('matriz A=[[1,2,3],[4,5,6]]; tensor T=transposta(A); mostrar T;')
        self.assertIn("T = [['1', '4'], ['2', '5'], ['3', '6']]", m.saidas)

    def test_tensor_reage_ao_passo_de_parametro(self):
        m = rodar('parametro x=2; vetor v=[x,1]; perda f=dot(v,v); passo f em x taxa 1/4; mostrar v;')
        self.assertIn("v = ['1', '1']", m.saidas)

    def test_fuzz_produtos_matriciais_e_certificados(self):
        # Terceira implementação de referência: listas Python + Fraction.
        rng = random.Random(303)
        for _ in range(40):
            linhas, interno, colunas = [rng.randint(1,3) for i in range(3)]
            a = [[rng.randint(-3,3) for k in range(interno)] for i in range(linhas)]
            b = [[rng.randint(-3,3) for j in range(colunas)] for k in range(interno)]
            def lit(matrix):
                return '[' + ','.join('['+','.join(map(str,row))+']' for row in matrix)+']'
            m = rodar(f'matriz A={lit(a)}; matriz B={lit(b)}; tensor C=A@B; mostrar C;')
            esperado = [[str(sum(a[i][k]*b[k][j] for k in range(interno)))
                         for j in range(colunas)] for i in range(linhas)]
            self.assertEqual(m.saidas[-1], f'C = {esperado}')
            self.assertTrue(all(map(verificar_certificado,m.certificados)))

    def test_dot(self):
        m = rodar('parametro x=3; perda f=dot([x,4], [2,5]); mostrar f;')
        self.assertIn('f = 26', m.saidas)
        self.assertEqual(m.certificados[0]['tipo'], 'expansao_tensor')

    def test_escala_vetor_e_matriz(self):
        m = rodar('vetor v=[1,2]; matriz M=[[1,2],[3,4]]; tensor w=2*v+v*3; tensor N=M*2; mostrar w; mostrar N;')
        self.assertIn("w = ['5', '10']",m.saidas)
        self.assertIn("N = [['2', '4'], ['6', '8']]",m.saidas)

    def test_multiplicacao_por_transposta(self):
        m = rodar('matriz A=[[1,2],[3,4],[5,6]]; tensor B=transposta(A)@A; mostrar B;')
        self.assertIn("B = [['35', '44'], ['44', '56']]",m.saidas)

    def test_exige_dimensoes_iguais_soma(self):
        with self.assertRaisesRegex(ErroOmega, 'Dimensões incompatíveis'):
            checar_tipos(analisar('vetor a=[1,2]; vetor b=[1,2,3]; tensor c=a+b;'))

    def test_exige_dimensoes_compativeis_produto(self):
        with self.assertRaisesRegex(ErroOmega, 'exige Matriz'):
            checar_tipos(analisar('matriz A=[[1,2]]; vetor v=[1,2,3]; tensor r=A@v;'))

    def test_proibe_produto_vetor_por_matriz(self):
        with self.assertRaisesRegex(ErroOmega, 'exige Matriz'):
            checar_tipos(analisar('vetor v=[1,2]; matriz A=[[1,2],[3,4]]; tensor r=v@A;'))

    def test_matriz_irregular(self):
        with self.assertRaisesRegex(ErroOmega, 'retangular'):
            checar_tipos(analisar('matriz A=[[1,2],[3]];'))

    def test_nao_declarar_tensor_escalar(self):
        with self.assertRaisesRegex(ErroOmega, 'ao menos uma dimensão'):
            checar_tipos(analisar('tensor z=7;'))

    def test_vetor_rejeita_matriz(self):
        with self.assertRaisesRegex(ErroOmega, 'dimensão 1'):
            checar_tipos(analisar('vetor z=[[1,2]];'))

    def test_matriz_rejeita_vetor(self):
        with self.assertRaisesRegex(ErroOmega, 'dimensão 2'):
            checar_tipos(analisar('matriz z=[1,2];'))

    def test_comando_perda_exige_escalar(self):
        with self.assertRaisesRegex(ErroOmega, 'precisa ser Escalar'):
            checar_tipos(analisar('vetor v=[1,2]; perda f=v;'))

    def test_dot_com_tamanhos_diferentes(self):
        with self.assertRaisesRegex(ErroOmega, 'dot exige'):
            checar_tipos(analisar('perda f=dot([1,2],[1,2,3]);'))

    def test_nao_aceitar_variavel_inexistente_cancelada(self):
        with self.assertRaisesRegex(ErroOmega, 'não declarado'):
            checar_tipos(analisar('vetor v=[z-z,1];'))

    def test_funcao_estranha(self):
        with self.assertRaisesRegex(ErroOmega, 'Função tensorial desconhecida'):
            checar_tipos(analisar('tensor v=cos([2]);'))

    def test_redeclaracao_rejeitada(self):
        with self.assertRaisesRegex(ErroOmega, 'já declarado'):
            checar_tipos(analisar('vetor v=[1]; parametro v=4;'))

    def test_tensor_referencia_anterior(self):
        m=rodar('vetor v=[1,2]; tensor u=v+v; tensor z=u+v; mostrar z;')
        self.assertIn("z = ['3', '6']", m.saidas)

    def test_erro_posterior_sem_mutacao(self):
        m=MaquinaOmega()
        with self.assertRaises(ErroOmega):
            m.executar(analisar('parametro x=1; matriz A=[[1,2]]; tensor z=A@[1,2,3];'))
        self.assertEqual(m.parametros,{})
        self.assertEqual(m.tensores,{})

    def test_tensores_vazios_nao_permitidos(self):
        with self.assertRaisesRegex(ErroOmega, 'entre 1'):
            checar_tipos(analisar('vetor a=[];'))

    def test_limite_32_dimensao(self):
        with self.assertRaisesRegex(ErroOmega, 'entre 1'):
            checar_tipos(analisar('vetor v=[' + ','.join(['1']*33) + '];'))

    def test_comando_roundtrip(self):
        cmds=analisar('matriz A=[[1,2],[3,4]]; vetor v=[1,2]; tensor y=A@v; perda f=dot(y,y); gradientes f;')
        self.assertEqual(cmds, [comando_de_dict(comando_para_dict(c)) for c in cmds])

    def test_teorema_tensorial(self):
        m=rodar('teorema distributiva = dot([a,b],[c,d]) == a*c+b*d; verificar distributiva;')
        self.assertIn('VERIFICADO: teorema distributiva',m.saidas)
        self.assertTrue(verificar_certificado(m.certificados[0]))

    def test_teorema_vetorial_falso(self):
        with self.assertRaisesRegex(ErroOmega, 'falsa'):
            rodar('teorema errado = [x,x] == [x,2*x];')

    def test_reescrita_da_perda_tensorial(self):
        m=rodar('parametro x=2; vetor v=[x,3]; perda f=dot(v,v); reescrever f=x^2+9; mostrar f;')
        self.assertIn('f = 13',m.saidas)
        self.assertTrue(all(map(verificar_certificado,m.certificados)))


class Autodiff03(unittest.TestCase):
    def test_gradiente_reverso_linha(self):
        m=rodar('parametro x=2; parametro y=-1; matriz A=[[2,1],[1,3]]; vetor v=[x,y]; tensor z=A@v; perda f=dot(z,z); gradientes f;')
        self.assertIn('d(f)/d(x) [reverso] = 10',m.saidas)
        self.assertIn('d(f)/d(y) [reverso] = 0',m.saidas)
        self.assertTrue(any(c['tipo']=='retropropagacao' for c in m.certificados))

    def test_zero_parametro_desconectado(self):
        m=rodar('parametro x=2; parametro y=100; perda f=x^2; gradientes f;')
        self.assertIn('d(f)/d(y) [reverso] = 0',m.saidas)

    def test_expoente_zero(self):
        m=rodar('parametro x=0; perda f=x^0; gradientes f;')
        self.assertIn('d(f)/d(x) [reverso] = 0',m.saidas)

    def test_expoente_e_divisor_simbolicamente_constantes(self):
        m=rodar('parametro x=2; perda f=(x^((x-x)+2))/((x-x)+2); gradientes f;')
        self.assertIn('d(f)/d(x) [reverso] = 2',m.saidas)

    def test_passo_tensores(self):
        m=rodar('parametro x=2; vetor v=[x,1]; perda f=dot(v,v); passo f em x taxa 1/4;')
        self.assertEqual(m.parametros['x'],Fraction(1))
        self.assertTrue(all(map(verificar_certificado,m.certificados)))

    def test_rejeicao_passo_piora_tensorial(self):
        with self.assertRaisesRegex(ErroOmega,'aumentaria'):
            rodar('parametro x=2; vetor v=[x,1]; perda f=dot(v,v); passo f em x taxa 10;')

    def test_reverso_vs_polinomio_aleatorio(self):
        rng=random.Random(30417)
        for _ in range(100):
            a,b,c = [rng.randint(-4,4) for __ in range(3)]
            fonte=f'({a})*x^3 + ({b})*x*y + ({c})*(y-2)^2 + x*y/3'
            ast=analisar(f'provar {fonte} == {fonte};')[0].expressao
            estado={'x':Fraction(rng.randint(-3,3)),'y':Fraction(rng.randint(-3,3))}
            rev=retropropagar(ast,estado)
            poly=normalizar(ast)
            for key in estado:
                self.assertEqual(rev[key],poly.derivar(key).avaliar(estado))


class Certificados03(unittest.TestCase):
    def _certs(self):
        return rodar('parametro x=2; vetor v=[x,2]; matriz A=[[1,2],[0,3]]; tensor z=A@v; perda f=dot(z,z); gradientes f;').certificados

    def test_todos_passam(self):
        self.assertTrue(all(map(verificar_certificado,self._certs())))

    def test_adulterar_expansao_resultado(self):
        cert=copy.deepcopy(self._certs()[0])
        cert['expandido']['itens'][1]['valor']='999'  # altera o segundo componente de [x,2]
        self.assertFalse(verificar_certificado(cert))

    def test_adulterar_expansao_dimensoes(self):
        cert=copy.deepcopy(self._certs()[0])
        cert['dimensoes']=[3]
        self.assertFalse(verificar_certificado(cert))

    def test_adulterar_definicao_da_expansao(self):
        cert=copy.deepcopy(self._certs()[3])
        self.assertEqual(cert['tipo'],'expansao_tensor')
        cert['definicoes']['A']['itens'][0]['itens'][0]['valor']='100'
        self.assertFalse(verificar_certificado(cert))

    def test_adulterar_gradiente_reverso(self):
        cert=copy.deepcopy(self._certs()[-1])
        self.assertEqual(cert['tipo'],'retropropagacao')
        cert['resultados']['x']='1024'
        self.assertFalse(verificar_certificado(cert))

    def test_gradiente_reverso_sem_estado(self):
        self.assertFalse(verificar_certificado({'tipo':'retropropagacao','estado':{},'resultados':{}}))

    def test_certificado_tensorial_incompleto(self):
        self.assertFalse(verificar_certificado({'tipo':'expansao_tensor'}))
        self.assertFalse(verificar_certificado({'tipo':'identidade_tensorial'}))

    def test_cert_teorema_tensorial_adulterado(self):
        cert=copy.deepcopy(rodar('teorema T = [a,b] == [a,b];').certificados[0])
        self.assertEqual(cert['tipo'],'identidade_tensorial')
        cert['direita']['itens'][1]['nome']='a'
        self.assertFalse(verificar_certificado(cert))

    def test_nucleo_nao_importa_produtor(self):
        from omega import nucleo_tensor
        self.assertNotIn('omega.tensores',nucleo_tensor.__dict__)
        self.assertNotIn('omega.algebra',nucleo_tensor.__dict__)

    def test_compile_roundtrip_e_verificacao(self):
        with tempfile.TemporaryDirectory() as td:
            ir=Path(td)/'prog.omc'
            cert=Path(td)/'provas.json'
            fonte=ROOT/'exemplos/tensores_gradientes.omega'
            comandos=[(sys.executable,'-m','omega','compile',str(fonte),'-o',str(ir)),
                      (sys.executable,'-m','omega','run',str(ir),'--certificados',str(cert)),
                      (sys.executable,'-m','omega','verify',str(cert))]
            for args in comandos:
                p=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('VERIFICADO:',p.stdout)


if __name__ == '__main__':
    unittest.main()
