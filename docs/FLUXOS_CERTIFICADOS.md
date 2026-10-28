# Fluxos racionais certificados

As APIs abaixo têm contratos executáveis e rejeitam resultados sem as provas
exigidas. Elas não transformam testes em provas universais do compilador C/GMP.
Os limites são parte da API, inclusive quando uma busca não encontra solução.

Este documento descreve o fluxo racional afim/ReLU original. A extensão com
Softmax, RMSNorm, Self-Attention, executáveis reutilizáveis e benchmark está em
[Transformer certificado](TRANSFORMER_CERTIFICADO.md).

| Pedido | API implementada | Domínio da garantia |
|---|---|---|
| Poda Stern–Brocot/frações contínuas | `omega.rational_pruning.approximate`, `certify_argmax`, `certify_bounded_graph` | Melhor aproximação com denominador limitado; limites locais Lean; argmax único com margem estrita. O fluxo de grafo arredonda valores e intervalos intermediários para fora. |
| Superotimização | `omega_evolution.superoptimization.discover`, `evolve`, `audit` | Busca limitada de cancelamentos racionais, prova universal, novo compilador auto-hospedado, prova dos valores e gradientes do IR e ponto fixo nativo. |
| Ponte PyTorch | `@omega.certify` e `model.export_certified` | FX estático, uma entrada vetorial, módulos `Linear`/`ReLU`, pesos congelados como racionais exatos, C/GMP e link estático. |
| Proof-carrying inference | `omega.pci.issue`, `verify`, `verify_export` | Saídas exatas, prova de execução e limites universais da caixa de entrada, assinatura Ed25519, identidade do modelo/contrato/requisição e hashes dos artefatos. |
| Borda | `omega.edge.emit` | C freestanding, sem heap/GMP/Python, racionais exatos com escalas estáticas em int64, checagem de cada produto e soma parcial e prova de limites. |
| Ações constitucionais | `omega_agent.constitutional.transfer`, `execute_transfer` | Transferências puras entre recursos com capacidades, precondições, conservação, versão do estado e invariantes Lean. |
| Destilação inversa | `omega_agent.inverse_distillation.distill_boolean`, `distill_rational` | Hipótese textual como proveniência; especificação explícita; busca limitada; circuito booleano nativo com tabela completa ou síntese racional com casos reservados. |
| Evolução por gerações | `OmegaEvolution.generations_preserve` e cadeia auditável de `evolve` | Teorema para todo número finito de passos que preservem a semântica, hashes encadeados, auditoria contra um digest externo e ponteiro local publicado após os gates. |

## Preparar e testar

No checkout existente, sem criar outro worktree:

```sh
cd /workspace/Omega
bash scripts/setup.sh
bash scripts/test.sh -q
```

Lean 4.19.0, Mathlib fixado, compilador C, GMP e Bubblewrap são necessários para
os fluxos nativos. As provas geradas só são admitidas após o checker terminar e
relatar as dependências dos teoremas. `sorryAx` e axiomas fora da política são
rejeitados. As provas são reconstruídas de dados validados durante a auditoria;
um arquivo Lean fornecido no certificado nunca é executado como entrada confiável.

## Exportar um controlador

```python
import torch
import omega
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

@omega.certify(target="controller-v1", precision="exact-rational")
class Controller(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = torch.nn.Linear(8, 16)
        self.relu = torch.nn.ReLU()
        self.fc2 = torch.nn.Linear(16, 2)

    def forward(self, x):
        return self.fc2(self.relu(self.fc1(x)))

model = Controller()
# Demonstração: produção deve fornecer a sua chave externa e reter a chave
# pública como âncora de confiança. A biblioteca não cria chaves implicitamente.
key = Ed25519PrivateKey.generate()
result = model.export_certified(
    torch.zeros(8), "artifacts/controller-demo",
    input_bounds=[[-1, 1]] * 8,
    output_bounds=[[-30, 30], [-30, 30]],
    signing_key=key, nonce="request-001",
)
```

O diretório deve ser novo. Limites insuficientes são rejeitados antes do build.
O exportador grava `model.omega`, `model.c`, binário estático `model`, manifesto
de build, `bounds.lean`, `execution.lean`, `native-result.json` e o bundle assinado
`certificate.json`. Esse binário especializa **a entrada concreta fornecida**;
as provas de limites cobrem toda a caixa declarada. Para uma biblioteca C que
recebe entradas em execução, use o backend de borda com a grade de entrada declarada.

O grafo interpreta o valor binário de cada peso float como uma fração exata.
Isso define uma semântica racional; não afirma igualdade bit a bit com a
acumulação em ponto flutuante do PyTorch. Batches, `call_function`, operações
dinâmicas, módulos personalizados e outras ativações são rejeitados.

Auditoria independente do bundle:

```python
from omega.pci import verify_export
from omega.pci import digest

certificate = result["certificate"]
statement = certificate["payload"]["statement"]
# Em produção, retenha os valores esperados na configuração do auditor,
# independentemente do bundle recebido.
verification = verify_export(
    result["directory"], public_key=key.public_key(),
    expected_graph_sha256=digest(statement["graph"]),
    expected_inputs=[0] * 8, expected_nonce="request-001",
    expected_context="controller-v1",
    expected_input_bounds=[[-1, 1]] * 8,
    expected_output_bounds=[[-30, 30], [-30, 30]],
)
```

A assinatura autentica a chave fixada pelo auditor. Não substitui Lean.
O auditor recalcula a execução racional e revalida as provas; esse formato não
é uma SNARK, não é um verificador de microssegundos e não oferece integração
automática com blockchain. Nonces são vinculados à requisição; o host continua
responsável pelo seu registro de consumo contra replays.

## Poda com margem

```python
from omega.rational_pruning import certify_argmax, certify_bounded_graph

local = certify_argmax(["10001/3000", "1/3"], max_denominator=100)
# Para um grafo exportado, evita avaliar a rede inteira em racionais crescentes:
bounded = certify_bounded_graph(
    statement["graph"], [0] * 8, max_denominator=2**32, max_bits=128,
)
```

`Fraction.limit_denominator` usa frações contínuas, equivalentes à busca de
vizinhos apropriados na árvore de Stern–Brocot. Um limite de denominador não
limita sozinho o numerador: magnitudes que excedem o orçamento são rejeitadas.
A decisão só é entregue quando os intervalos certificados separam estritamente
o vencedor de todos os concorrentes. Empates e margens inconclusivas falham.
O modo de grafo limita os resultados das operações e arredonda intervalos para
fora; os pesos e os operandos temporários de uma operação ainda usam racionais.

O argumento correto inclui a margem: para erros coordenados `e_i`, é suficiente
`y_w - y_i > e_w + e_i` para todo `i != w`. Um simples `|y-y'| <= epsilon`
não garante argmax. Não se modifica silenciosamente o backpropagation existente:
erros de gradiente e comportamento de treinamento exigem outro contrato.

## Evoluir e auditar um compilador local

```python
from omega_evolution.superoptimization import evolve, audit

experiment = evolve("artifacts/evolution-demo", generations=2)
head = experiment["generations"][-1]["sha256"]  # reter fora do diretório
audit("artifacts/evolution-demo", expected_head_sha256=head)
```

A busca propõe `(a+b)-b -> a` e `(a-b)+b -> a`. Lean verifica identidades para
todo ambiente racional. Somente templates do emissor auditados podem instalar
essas regras; o kernel independente reconhece as testemunhas e verifica os
valores e gradientes. Cada geração compila a própria fonte com o compilador
anterior, recompila duas vezes nativamente e exige igualdade do C estabilizado.
O checkout e o compilador de produção não são substituídos. `current` é um
ponteiro do experimento local, criado somente ao final de todos os gates.

O teorema `generations_preserve` não usa axiomas e prova por indução a preservação
para qualquer número finito de passos, **sob a hipótese de cada passo preservar
a semântica**. Ele não prova automaticamente essa hipótese para patches
arbitrários, nem a correção de GCC, GMP ou do emissor. Ponto fixo também não
constitui uma prova universal da correção do compilador.

## Borda, ações e destilação

`omega.edge.emit(graph, inputs, outputs, directory)` gera uma função
`int omega_edge(const int64_t *input, int64_t *output)`. Entradas fora do domínio
retornam erro. Não há alocação dinâmica nem dependências externas. Cada nó tem
uma escala racional fixa escolhida por mínimo múltiplo comum; `scales.json`
documenta as escalas de entrada, nós e saída. Um inteiro de entrada `x`
representa `x / input_scale` (padrão: 1); os inteiros de saída devem ser divididos
pelas escalas de saída correspondentes. Coeficientes fracionários são exatos,
sem truncamento. Crescimento de escala e possibilidade de overflow em qualquer
produto/soma parcial são rejeitados. Portabilidade C freestanding é validada no host;
cross-compilação e medições em ARM/RISC-V requerem as toolchains e os dispositivos.

`ResourceState((5, 1), (10, 4))` representa saldos e capacidades. Uma chamada
`transfer(state, source=0, destination=1, amount=2, expected_version=0)` prova o
passo antes de retornar o novo estado imutável. `execute_transfer` também emite,
compila e executa a ação aritmética `.omega`. O teorema universal de transferência
e as provas concretas conferem as precondições e a conservação. Efeitos externos
precisam de um adaptador transacional autorizado pelo host; nenhuma string de
shell do proponente é executada.

`distill_boolean(hypothesis, task, directory, max_size=9, max_candidates=10000)`
enumera circuitos por tamanho, verifica a tabela completa com Lean e compila C
nativo, conferindo todas as linhas. A gramática é `{constante, variável, not,
and, or, xor}`. A minimalidade se refere a essa gramática e ao tamanho da árvore,
não a todos os programas possíveis. A busca pode esgotar o orçamento.
`distill_rational` reutiliza a síntese nativa isolada com exemplos de treinamento
e casos reservados; exemplos finitos não estabelecem correção universal.
Nenhuma hipótese textual ou LLM inventa especificações, credenciais ou provas.
