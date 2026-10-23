# Ômega 1.3 — extensão de síntese parametrizada

Ver [README_OPEN_1_3.md](README_OPEN_1_3.md) para gramática Bool^n, enumeração exaustiva e seus limites.

# Especificação técnica da Ômega 1.2

A versão 1.2 introduz uma camada meta sobre o compilador tensorial 1.1. Ela mantém a gramática existente de `parametro`, `tensor`, `relu` e `mostrar`. A mudança essencial é permitir que **o próprio mecanismo de pesquisa use como parte de seu comportamento um programa Ômega gerado**, e não uma regra de prioridade fixa na aplicação.

- **Objetos controlados:** os parâmetros de uma função de pontuação de candidatos.
- **Espaço finito do gerador:** 243 políticas, cinco pesos em {-1,0,1}.
- **Universo de tarefas:** 16 funções booleanas de duas variáveis.
- **Universo da solução:** 625 funções obtidas com quatro coeficientes inteiros de -2 a 2.
- **Métrica observável:** ordem ordinal da primeira hipótese exata para cada tarefa.
- **Critério de seleção:** custo exclusivamente nas oito tarefas de treinamento.
- **Critério de aceitação:** minimização exaustiva reproduzida por verificador separado.
- **Limite explícito:** o mecanismo externo que enumera as políticas não é reescrito pela linguagem.

Consulte `PROVA_META_FINITA.md` para enunciados, fórmulas, prova de completude, divisão de dados e limites epistêmicos.
