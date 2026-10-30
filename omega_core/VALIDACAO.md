# Execuções dos dezesseis motores

O [catálogo](catalogo.json) contém os 16 módulos solicitados e seus exemplos.
Os [contratos técnicos](README.md) delimitam os algoritmos implementados.
O [registro de evidências](evidencias/resultados.json) fixa os hashes dos fontes,
dos relatórios e dos receipts gerados. É um registro de integridade, não uma
atestação externa ou assinatura do autor.

## Rodadas e versões

| Rodada | Código executado | Resultado |
| --- | --- | --- |
| Regressão completa, `bash scripts/test.sh -q` | `b211393` | **1.240 passaram**, 37 subtestes passaram, zero falhas/erros; 4 skips CUDA; 3 avisos; 1.391,55 segundos |
| Suíte final `testes/engines` | `954539f` | **115 passaram**, zero falhas/erros/skips; 98,31 segundos |
| Segurança nativa do compilador/runtime existente | `b211393` | **250 passaram**, zero falhas; fuzzing, ASan/UBSan/LSan e análise estática em container GCC fixado |
| Corpus diferencial | `b211393` | 25 positivos e 4 negativos corretos; contagem consistente; zero falhas de exemplo/infraestrutura |
| Planos OM-020, 024, 026, 027, 028 e 131 | `954539f` | Seis execuções com `checks_passed_acceptance_pending` |

A suíte final tem 87 testes nativos, 27 de integração e um de distribuição.
Os casos adicionados incluem limites inválidos da API C e provas globais do LP.
Não se somam 115 a 1.240 como se fossem testes independentes: há sobreposição.

Entre as duas versões, acrescentamos guardas de runtime nulo/não inicializado e
ID inválido no microkernel e contratos Lean quantificados para LPs concretos.
Reexecutamos toda a suíte dos motores, incluindo o C com sanitizers e a instalação
offline. A regressão completa não foi repetida depois dessas alterações. Os 16
fontes `.omega` e o arquivo Hamilton formal permaneceram iguais entre as rodadas;
os testes dos demais subsistemas pertencem à rodada completa indicada acima.

Os quatro skips são CUDA: OM-096, Triton, pipeline e stress numérico. Não houve
execução em GPU, conforme a decisão de continuar em CPU. A co-simulação RTL foi
executada com Icarus Verilog. Os avisos Python são duas depreciações de localização
do Orange e a configuração de paralelismo do UMAP com seed. Avisos de estilo do
Lean não foram ocultados; as auditorias de axiomas passaram.

## O que foi efetivamente confrontado

- Restos de Taylor contra precisão decimal independente, incluindo truncamento,
  composição e quantização; operações/domínios não suportados recusados.
- E-graphs contra avaliação independente das expressões; limites de saturação e
  rejeição de regras inválidas sobre divisão.
- Simplex contra enumeração exata de vértices em 24 problemas, além de casos
  degenerados, de cycling, inviabilidade, raio não limitado e orçamento esgotado.
- SINDy em recuperação esparsa e dados retidos; Euler–Lagrange e simetrias em
  exemplos polinomiais; DEL, reversibilidade e drift físico reportado.
- `d²=0` nas matrizes de fronteira de um tetraedro; complemento de Schur,
  conservação por blocos e decomposição da variância.
- TT por resíduo completo de reconstrução e norma; contração de estado produto
  com 64 sítios sem construir suas 2⁶⁴ entradas densas.
- Bayes/POMDP, restrições de ação, conservação catalítica e reparos não aplicados.
- EqProp contra pontos fixos resolvidos independentemente; intervalos de Hopfield
  e evicção; observação versus intervenção, contrafactual e critério backdoor.
- Gradientes JEPA contra diferenças finitas de objetivo independente; EMA e
  detecção de colapso; hiper-rede em tarefas da classe de programas declarada.
- Microatores Ômega/C em doze combinações de atores, quantum e capacidade; testes
  de aritmética, overflow, layout, ponteiros nulos e IDs inválidos com ASan/UBSan.
- Header microkernel compilado como freestanding sem chamadas de heap/OS;
  wheel completo instalado offline e executado em venv sem Torch.

## Provas e demonstrações persistentes

Os seis teoremas de `formal/HamiltonPrinciple.lean` foram compilados e auditados.
As únicas dependências fundamentais permitidas são `propext`, `Classical.choice`
e `Quot.sound`, quando usadas. Não se adicionaram axiomas científicos ou admissões.

As demonstrações em `artifacts/engines/demos` foram executadas pelos mesmos
comandos adicionados à CI:

| Diretório | Evidência |
| --- | --- |
| `lp` | Certificado primal/dual, fatos numéricos e teorema Lean com limite objetivo para toda atribuição racional viável do problema recebido |
| `action` | Reconstrução independente das condições iniciais, passos, DEL e identidade simplética em trajetória finita; objetos `.olean` |
| `synthesis` | Programa Ômega realmente compilado, C, ELF, execução dos três casos, referência racional independente, headers e provas numéricas |
| `actors` | C realmente compilado, arenas alocadas, saída comparada com referência Ômega, fontes, hashes e receipt |

Os testes de integração também compilaram os contratos globais de inviabilidade
e de raio com crescimento objetivo. Fontes/hash adulterados, candidatos com saída
errada, objetivos/duais incorretos e trajetórias incompatíveis com o pedido são
recusados. Snapshots impedem que a mutação do objeto original altere o sujeito
registrado no receipt depois da verificação.

## Memória medida

Medições independentes com `wait4`/`ru_maxrss` Linux no commit `b211393`, uma
execução por configuração. A carga tem uma instrução `halt` por ator, sem pesos
neurais ou processo Lean. O harness aloca as arenas, e o header inicializa esse
armazenamento. O custo do supervisor Python e do compilador fica fora do RSS
deste processo nativo.

| Atores | Arena por ator | Total das arenas | Pico RSS do harness |
| --- | --- | --- | --- |
| 1 | 64 KiB | 64 KiB | 640 KiB |
| 32 | 64 KiB | 2 MiB | 2.560 KiB |
| 256 | 64 KiB | 16 MiB | 16.896 KiB |
| 1 | 512 KiB | 512 KiB | 1.024 KiB |
| 32 | 512 KiB | 16 MiB | 16.896 KiB |
| 256 | 512 KiB | 128 MiB | 131.584 KiB |

São medições de reserva e execução de bytecode mínimo, não de inteligência,
throughput de provas, M:N ou capacidade para 20 mil modelos. Não se extrapola uma
garantia de RSS por agente, inferência neural ou execução do Lean desses valores.

## Reprodução e limites

Ambiente: Linux x86_64, Python 3.12.14, Lean 4.19.0, Mathlib
`c44e0c8ee63ca166450922a373c7409c5d26b00b`, GCC 14.2.0, GMP e Bubblewrap.
Os XMLs, relatórios, demos e perfis estão sob `artifacts/engines`, coletado pela CI.
O manifesto final de distribuição é gerado por:

```sh
.venv/bin/python scripts/package.py
.venv/bin/python scripts/build-manifest.py --output artifacts/engines/build-manifest.json
.venv/bin/python scripts/build-manifest.py --verify artifacts/engines/build-manifest.json
```

Os algoritmos têm os escopos do catálogo: TT por projeção racional não é SVD
ótima; o scheduler é cooperativo stackless, não fibras M:N; a memória é finita;
o compilador variacional cobre polinômios, não toda teoria de campos. A prova
global do LP não prova refinamento geral do compilador/C/GMP nem valida uma lei
física ou hipótese causal empírica. Avaliação externa e os aceites amplos do
roadmap continuam pendentes. Não houve promoção de versão ou ação externa.
