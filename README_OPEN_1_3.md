# Ômega 1.3 — síntese aberta com verificação exaustiva finita

**Escopo verdadeiro:** a 1.3 aceita tarefas Booleanas `Bool^n -> Bool` com `n` definido pelos dados, sintetiza programas a partir de DNF, forma normal algébrica (ANF) e decomposição de Shannon com diferentes ordenações. As próprias políticas de priorização são emitidas como programas `.omega` e compiladas na IR `.omc` pelo compilador herdado 1.2. O algoritmo escolhe novos pesos quando a complexidade total de seus programas de treinamento diminui.

**Não é inteligência ilimitada:** cada tarefa tem `2^n` casos; a verificação completa é exponencial em `n`. As famílias de operadores (`not`, `and`, `or`, `xor`, `ite`), os critérios, o gerador e o interpretador Python permanecem definidos por humanos. O conjunto de políticas por busca é finito para cada raio, ainda que o raio possa aumentar. Nenhuma prova de AGI, generalização universal ou evolução sem limites existe neste pacote.

## Uso

Requer Python 3.10+; sem bibliotecas extras. Na pasta `Omega_v1_3`:

```sh
python -m omega open-evolve exemplos/tarefas_abertas.json --saida experimento --geracoes 2
python -m omega verify-open experimento/cadeia_aberta.json
python -m omega audit-open experimento
python -m omega run experimento/politica_ativa.omega
python -m unittest discover -s testes -v
```

O núcleo novo também pode ser executado independentemente:

```sh
python -m omega_open evolve exemplos/tarefas_abertas.json experimento --generations 2
python -m omega_open audit experimento
```

## Declaração de novas tarefas

Crie JSON:

```json
{
  "tasks": [
    {"id": "xor_2", "arity": 2, "outputs": [0,1,1,0]},
    {"id": "and_2", "arity": 2, "outputs": [0,0,0,1]}
  ],
  "train_ids": ["xor_2"]
}
```

A ordem dos bits nas linhas segue `x0` como bit menos significativo do índice: `0=(0,0)`, `1=(1,0)`, `2=(0,1)`, `3=(1,1)`.

O conjunto de treino é usado para selecionar a política. As demais tarefas são avaliadas, mas não determinam a seleção. O sistema mede **nós distintos no DAG simbólico**, NÃO tempo de execução ou qualidade cognitiva. Os orçamentos `--max-linhas`, `--max-ordens`, `--max-nos`, `--geracoes` controlam recursos e podem ser ajustados em cada execução; não confunda isso com execução infinita real.

## Modelo de confiança

- `omega_open/logic.py` gera expressões exatas imutáveis e usa uma tabela-verdade própria para testes locais;
- `omega_open/checker.py` não importa o sintetizador e avalia novamente cada linha da tabela, validando formas e métricas;
- `omega_open/engine.py` reexecuta integralmente todas as estratégias e todas as políticas dentro do orçamento configurado (`audit`), detectando omissões e adulterações de arquivos;
- cada registro traz SHA-256, que detecta mudança acidental ou inconsistência, mas **não autentica** a origem do certificado;
- se o compilador `omega` estiver disponível, políticas geradas são compiladas em `.omc` e executadas em entradas de teste. A verificação algébrica de todos os possíveis valores de três variáveis é feita diretamente sobre sua fórmula linear, não pelo compilador externo.

O verificador é um programa Python, não um teorema aprovado pelo kernel do Lean. O texto "prova" significa enumeração completa em domínio Booleano finito, dentro da implementação auditável.

## Arquivos

- `exemplos/tarefas_abertas.json`: tarefas de treinamento e teste
- `exemplos/evolucao_aberta/cadeia_aberta.json`: registro reproduzível
- `exemplos/evolucao_aberta/politica_*.omega`: cada geração do programa de priorização
- `exemplos/evolucao_aberta/politica_*.omc`: representação compilada pela Ômega anterior
- `testes/test_open_v13.py`: testes de regressão e adulteração

Esta versão é distribuída como projeto de pesquisa, não como sistema de execução autônoma irrestrita.
