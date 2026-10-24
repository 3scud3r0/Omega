# Nextorch

Biblioteca de pesquisa em PyTorch para síntese de arquiteturas, computação latente,
interpretabilidade esparsa e aprendizado com admissão formal de exemplos. Inclui
um add-on para o **Orange Data Mining** com três widgets conectáveis.

A versão **0.1.0** implementa os módulos da [especificação recebida](docs/especificacao-original.txt)
com execução em CPU, exemplos reproduzíveis e testes de integração. O escopo e os
limites das hipóteses de pesquisa estão em [Arquitetura](docs/architecture.md).

## Começar no ambiente preparado

```bash
cd /workspace/Nextorch
bash scripts/test.sh -q
NEXTORCH_LEAN=/workspace/.tools/lean/bin/lean .venv/bin/nextorch demo --lean
.venv/bin/python examples/iris_workflow.py
```

O demo executa treinamento da política GFlowNet, seleção de DAGs por métricas de
custo zero, busca latente em feixe, certificação Z3 e treino conjunto do reasoner
com seu SAE. `--lean` exige também uma prova aceita pelo Lean instalado.

Resultados em `artifacts/demo/`:

- `report.json`: diagnósticos, arquitetura e resultados por ciclo;
- `certified_replay.json`: exemplos, origem e certificados formais;
- `checkpoint.pt`: pesos, otimizador, SAE/PID, replay e estado aleatório para retomada.

O exemplo Iris separa treino/teste antes de ajustar a normalização e a arquitetura;
exporta a acurácia de teste, o modelo restaurável e uma tabela Orange com features SAE.

## Instalar

Para reproduzir o ambiente completo testado em Linux x86_64 com Python 3.12,
`curl`, `tar` e `zstd` disponíveis:

```bash
bash scripts/setup.sh
```

Esse script usa [versões fixadas](requirements/cpu-py312.lock), PyTorch 2.5.1 CPU e
Lean 4.19.0 com verificação SHA256 do arquivo oficial. A instalação é repetível.
`NEXTORCH_INSTALL_LEAN=0` omite o Lean; `NEXTORCH_TOOLS_DIR` altera a pasta de ferramentas.
O núcleo funciona com Python >=3.11:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --index-url https://download.pytorch.org/whl/cpu torch==2.5.1
pip install -e '.[dev,orange,umap]'
```

`orange`, `umap` e `gpu` são extras. A API numérica não importa Qt e funciona sem
Orange. Para usar GPU, instale a distribuição CUDA do PyTorch apropriada ao seu
hardware e o extra `gpu`. O kernel Triton é opcional, explícito e apenas para inferência.

## API

```python
import torch
from nextorch import NextorchEngine, NextorchModel, seed_everything
from nextorch.formal import FormalVerificationGateway, LogicalProblem

seed_everything(42)
engine = NextorchEngine(vocab_size=16, d_model=32)
report = engine.execute_self_improvement_cycle(n_problems=8)
engine.save_checkpoint('artifacts/engine.pt')
restored = NextorchEngine.load_checkpoint('artifacts/engine.pt')

problem = LogicalProblem(((0, 1), (1, 2)), source=0)
certificate = FormalVerificationGateway.certify_deduction(problem.premises, 0, 2)
assert certificate.valid  # Premissas consistentes e negação do alvo insatisfatível.
assert not FormalVerificationGateway.verify_deduction(problem.premises, 2, 0)

x = torch.randn(64, 4)
y = (x[:, 0] > 0).long()
model = NextorchModel.from_tensor(x, output_dim=2, width=16)
losses = model.fit(x, y, epochs=100, lr=0.03)
model.save('artifacts/tabular.pt')
```

`from_table(Orange.data.Table)` usa uma ponte ajustada no conjunto de treino:
categorias viram one-hot, valores contínuos recebem imputação e Z-score, tabelas
esparsas são aceitas. `model.bridge.transform(test_table)` reutiliza essas
estatísticas. `OrangeBridge.append_features` preserva alvos, metas, pesos e IDs.

## Orange Canvas

Com um desktop Qt disponível:

```bash
.venv/bin/orange-canvas examples/nextorch.ows
```

A categoria **Nextorch Epistemic AI** registra:

| Widget | Entradas | Saídas |
|---|---|---|
| Nextorch Synthesizer | Data | Nextorch Model, Engine Diagnostics |
| Latent Inspector | Nextorch Model, Data | Decoded Features Table |
| Formal Loop Monitor | Nextorch Model, Domain Rules | Certified Dataset |

No workflow de exemplo, escolha um dataset no widget File. O Synthesizer analisa
o espectro, seleciona um DAG e treina o modelo/SAE. O Inspector mostra trajetórias
em 2D/3D com PCA, t-SNE ou UMAP e exporta ativações esparsas. No Formal Loop Monitor,
clique **Start / continue**; regras opcionais podem chegar por sinal ou arquivo
JSON/SMT2, como [este exemplo](examples/domain_rules.smt2). O botão Stop conserva
os ciclos concluídos. Cálculos rodam em segundo plano; a projeção limita a amostra
visual a 64 linhas e a exportação processa todas as linhas.

No ambiente de nuvem sem desktop, os testes Qt usam `QT_QPA_PLATFORM=offscreen`.
Não é necessário iniciar um servidor web.

## Verificação formal e limites

O Z3 verifica consequências dos axiomas fornecidos. Premissas inconsistentes,
`unknown`, timeout e contraexemplos impedem admissão. O replay revalida as
conclusões ao carregar; hashes identificam certificados e não substituem a prova.
O loop diferencia propostas do modelo e propostas de um especialista simbólico,
ambas submetidas à mesma barreira. `expert_iteration=False` desativa o especialista.

Para exigir **Z3 e Lean em todas as admissões**, inclusive na restauração do replay:

```python
from nextorch import NextorchConfig, NextorchEngine
engine = NextorchEngine(config=NextorchConfig(require_lean=True))
```

Configure `NEXTORCH_LEAN` com o caminho do executável. Ausência, timeout ou rejeição
do Lean impede a admissão nesse modo. A barreira também expõe `certify_async` para
aplicações que já possuem um event loop.

O Lean verifica deduções proposicionais com um subconjunto explícito de provas,
sem `sorry`, axiomas novos ou metaprogramas arbitrários. A aprovação exige retorno
bem-sucedido e `#print axioms` sem dependência de axiomas. Este release não instala
Mathlib nem oferece um REPL irrestrito para executar código Lean externo.

As métricas SynFlow, SNIP, Jacobiano e Hessiano são diagnósticos. A parametrização
segue as coordenadas finitas descritas na especificação; transferência universal
para modelos de 10¹¹ parâmetros não foi demonstrada. A busca GFlowNet é limitada
por orçamento de candidatos e profundidade. O SAE não fornece garantia de eliminar
drift; nomes semânticos de features exigem anotações do usuário.

Net2Wider preserva a função, dentro da precisão numérica, duplicando neurônios e
dividindo pesos de saída. O crescimento automático amplia a projeção interna da
célula latente ao detectar platô e mantém a largura de sua interface. Camadas
novas recebem estado novo de otimizador; estados de parâmetros preservados são
mantidos. A demonstração científica de autoaperfeiçoamento geral requer benchmarks
adicionais e não é uma propriedade presumida desta biblioteca.

## Testes e proveniência

```bash
bash scripts/test.sh -q
.venv/bin/python -m build
.venv/bin/python -m pip check
```

Os testes cobrem matemática conhecida, gradientes, treinamento, certificados,
persistência, expansão funcional e o fluxo real dos widgets. Lean precisa do
executável; CUDA/Triton precisa de uma GPU. Ausências são registradas como skips.
A CI configura jobs de núcleo e integração; a execução remota depende do envio
deste código ao GitHub. Veja [a validação local](docs/validation.md).

O upstream [biolab/orange3](https://github.com/biolab/orange3), GPL-3.0-or-later,
está clonado separadamente em `/workspace/orange3`, commit
`db6ea81d9babb0a392c4fac714337aa7882246c6`. A integração executada usa a distribuição
Orange3 3.40.0 instalada por wheel. Consulte as licenças das dependências antes de distribuir.
