## 1.3.0

- Síntese Bool^n (DNF, ANF e Shannon), número de variáveis definido por dados.
- Meta seleção de pesos da política `.omega`, com transformação e compilação verificadas.
- Auditoria de arquivos, grafo de soluções, orçamentos e regressão de 218 testes antigos.
- Limitação expressa: não é AGI, nem inteligência ilimitada.

# Histórico da Ômega

## 1.2.0

- Adicionado gerador de **código Ômega executável** para programas que ordenam a própria busca de candidatos.
- Implementados novos comandos CLI: `meta-evolve`, `audit-meta` e `verify-meta`.
- Integrada a seleção de políticas em três gerações, com provas operacionais exaustivas no espaço de 243 políticas e 625 hipóteses.
- Criado núcleo independente `nucleo_meta.py` e auditoria completa da execução dos programas gerados.
- Demonstrada redução de 6.008 para 918 avaliações agregadas em 16 tarefas booleanas, mantendo oito delas reservadas para teste.
- Preservados os comandos e módulos anteriores, incluindo evolução XOR da versão 1.1.
- Adicionados testes de adulteração de certificados, código-fonte e IR.

## 1.1 e anteriores

Consulte os arquivos históricos no TXT integral que acompanha esta versão. As versões anteriores demonstravam sobretudo síntese de *programas-solucão*, não modificação executável da política que os pesquisa.
