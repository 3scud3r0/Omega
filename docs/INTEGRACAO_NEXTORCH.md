# Integração Ômega / Nextorch

O repositório Nextorch foi clonado em `/workspace/Nextorch`. Seu pacote foi
incorporado em `nextorch/`, sem depender desse checkout para importar, testar,
construir o wheel ou executar a integração. O fluxo é comandado pelo Ômega.

## Instalação

`bash scripts/setup.sh` prepara Linux x86_64/Python 3.12 com PyTorch 2.5.1 CPU,
Nextorch, Orange/Qt, testes e Lean 4.19.0. O arquivo oficial Lean é verificado
por SHA256; a instalação preserva a verificação TLS. As dependências Python
estão fixadas em `requirements/cpu-py312.lock`. GCC/Clang e `zstd` são pré-requisitos
do sistema. Não há serviços remotos, tokens ou downloads de pesos necessários.

Para outras plataformas, instale Python >=3.11, a distribuição PyTorch apropriada,
`pip install -e '.[neural,dev,orange]'`, um compilador C e Lean 4.19.0. O motor
clássico continua utilizável a partir do checkout com Python >=3.10 sem extras.

`OMEGA_LEAN` seleciona o executável Lean para o novo núcleo. `NEXTORCH_LEAN`
seleciona o mesmo executável para a barreira proposicional original do Nextorch.
O script de testes configura ambos. Qt roda com `QT_QPA_PLATFORM=offscreen`
na nuvem; para Canvas interativo é necessário um desktop Qt.

## Fluxo executado

1. Receber tarefas `{id, arity, outputs}`, de `Bool^0` até `Bool^12`.
   A ordem das linhas usa `x0` como bit menos significativo.
2. Nextorch analisa o espectro, treina a política GFlowNet, seleciona uma
   arquitetura, treina seu modelo recorrente e SAE. Os limites são explícitos:
   `--epochs`, `--width`, `--candidates`, `--policy-steps` e `--seed`.
3. Produzir duas propostas: ANF das previsões neurais e Shannon exato com ordem
   de variáveis sugerida pela saliência neural. A segunda usa a tabela fornecida,
   e é identificada como `nextorch:saliency+exact-shannon`; não é uma previsão
   neural perfeita por definição. O treinamento usa todas as linhas da tarefa;
   este experimento não mede generalização nem usa `train_ids` para separação.
4. O núcleo independente rejeita árvores malformadas, variáveis fora do domínio,
   profundidade excessiva e qualquer contraexemplo. Nenhum hash substitui a
   verificação da semântica. Entre as propostas aceitas, escolher a de menor DAG.
5. Com `--lean`, gerar uma fonte fechada com a especificação, circuito e bytecode;
   exigir que Lean confira o certificado e a correspondência do bytecode.
   Ausência, timeout ou rejeição do Lean impedem a publicação do experimento.
6. Com `--native`, gerar C11, compilar e executar todas as linhas da especificação
   antes de publicar o binário. As operações são booleanas exatas, sem floats.
7. Publicar o diretório de resultados somente quando todas as tarefas tiverem
   passado. Uma falha preserva o destino e descarta os resultados temporários.

O kernel admite no máximo 4096 linhas, 20000 nós expandidos e profundidade 128;
o comando aceita até 32 tarefas. Esses limites evitam trabalho ilimitado. Não
há promessa de sucesso do treinamento nem de aceleração frente ao sintetizador
puramente simbólico. Uma proposta neural errada é registrada como rejeitada.

## Comandos e artefatos

```sh
export OMEGA_LEAN=/workspace/.tools/lean-4.19.0-linux/bin/lean
export NEXTORCH_LEAN="$OMEGA_LEAN"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
.venv/bin/python -m omega intuition exemplos/tarefas_abertas.json \
  --saida artifacts/intuicao --epochs 80 --lean --native
.venv/bin/python -m omega audit-intuition artifacts/intuicao --lean --native
.venv/bin/python -m omega verify-intuition artifacts/intuicao/task_000.json
.venv/bin/python -m omega compile-native artifacts/intuicao/task_000.json --saida /tmp/circuito
.venv/bin/python -m omega prove-lean artifacts/intuicao/task_000.json --saida /tmp/Certificado.lean
```

`manifest.json` registra parâmetros, diagnósticos, rejeições, origem da proposta,
compilador e hashes dos artefatos. `task_NNN.json` contém a especificação e o
circuito certificado. Os índices numéricos evitam transformar IDs em caminhos.
`task_NNN.lean`, `task_NNN.c` e `task_NNN` são os artefatos opcionais de prova,
fonte C e executável. O binário recebe um índice de linha ou, sem argumentos,
imprime a tabela-verdade inteira; entradas fora do domínio retornam erro.

A auditoria sempre recalcula a certificação. `--lean` reconstrói a prova a partir
do circuito e a confere novamente. `--native` reconstrói e testa um novo binário
em diretório temporário; não executa o binário potencialmente adulterado entregue
no diretório auditado. Hashes indicam integridade, não autenticidade de origem.
Não se recupera uma prova da história de treinamento apenas a partir do manifesto.

## Verificador / compilador independente de Python

```sh
export PATH=/workspace/.tools/lean-4.19.0-linux/bin:$PATH
(cd formal/lean && lake build)
formal/lean/.lake/build/bin/omega_kernel artifacts/intuicao/task_000.json
```

Esse executável lê JSON, valida o domínio, executa o verificador booleano
formalizado e emite as instruções do compilador Lean. Ele verifica a semântica,
não a autenticidade dos hashes, as métricas ou os diagnósticos neurais. O parser,
o IO e a implementação do compilador Lean usado para gerar o binário pertencem
à base de confiança; a prova não cobre esses componentes.

## Orange

Abra `.venv/bin/orange-canvas exemplos/omega_nextorch.ows` em um desktop Qt
e escolha `exemplos/intuicao_xor.tab` no widget File. O workflow original do
Nextorch permanece em `exemplos/nextorch/nextorch.ows`.

`Omega Certifier` aceita atributos e um alvo com valores 0/1, com todas as
combinações de entrada presentes exatamente uma vez. Categorias discretas são
interpretadas por seus rótulos `0` e `1`, mesmo se a codificação interna estiver
invertida. Dados incompletos, ausentes ou não booleanos são recusados.

Clique em **Sintetizar e certificar**. A opção **Exigir prova Lean 4** vem ativada.
O processamento ocorre em segundo plano; trocar a entrada invalida a saída
anterior. A interface exporta o certificado e o relatório de admissão como
objetos, não uma alegação sobre segurança causal de dados do mundo real.

As APIs originais Nextorch continuam disponíveis, inclusive o demo:
`.venv/bin/python -m nextorch demo --lean --output artifacts/nextorch-demo`.
As funções neurais e os widgets originais são ferramentas de proposta; somente
a passagem pelos verificadores apropriados dá a garantia documentada.
