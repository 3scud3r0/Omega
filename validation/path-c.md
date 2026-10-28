# Validação do Caminho C

Execução em 2026-10-28, Linux x86_64, Python 3.12.14, Lean 4.19.0,
CC Debian 14.2 e Icarus Verilog 12.0.

```sh
LEAN_NUM_THREADS=4 bash scripts/test.sh -q --junitxml=artifacts/path-c-final-tests.xml
.venv/bin/python scripts/build-monolith.py --check
.venv/bin/python scripts/package.py
```

A suíte completa terminou sem falhas ou erros. O JUnit registra
905 casos incluindo subtestes, 2 ignorados por ausência de CUDA,
0 falhas e 0 erros. O incremento adiciona 48 casos de teste.
Os builds dos projetos Lean e do kernel nativo também passaram. Os testes
anteriores de self-attention, Softmax, RMSNorm, inferência assinada e benchmark
de controle foram mantidos e executados.

## Evidência dos novos fluxos

- Refinamentos: parser nativo e independente concordam; `x*(1-x)` permanece
  em `[0,1]` sob `x∈[0,1]`; divisores sem prova e inicializadores incompatíveis
  são rejeitados. O corpus contém 29 programas: 25 positivos e quatro
  rejeições esperadas, sem falhas de infraestrutura.
- Síntese: MCTS encontra incremento racional e Lean verifica o contrato para
  todas as entradas racionais. Propostas isoladas são verificadas de novo no
  host. Exemplos finitos que não satisfazem a proposição universal são recusados.
- Automutação: a regra `(x*2)-x → x` reduziu o probe de sete para cinco nós de
  IR, estabilizou quatro estágios nativos e produziu 21 teoremas de valor,
  gradiente e domínio. A geração foi auditada por reconstrução independente,
  ativada como compilador padrão e usada em uma compilação/execução posterior.
  O SHA-256 e os registros dos estágios estão em `path-c.json`.
- Ações: transição de resfriamento com prova de Hoare, assinatura Ed25519,
  capability vinculada à ação e CAS durável. Adulterações, replay, autorização
  de outro sujeito e estados obsoletos foram recusados. Perda de confirmação
  bloqueia retries. Somente adaptadores locais de teste foram despachados.
- C freestanding: checkpoint `weights_only` afim/ReLU exportado, compilado e
  executado em toda uma grade de entrada; resultado igual à referência
  racional. Buffers reutilizados, ausência de chamadas a heap/GMP/Python e
  limites de entrada foram conferidos. Headers C passaram com `-Werror` e
  UBSan, incluindo overflow e handles expirados.
- Rastros: intermediários do binário nativo foram comparados à execução exata;
  limites selecionados receberam provas Lean. Replay detectou alterações.
  Bases não ortonormais e conceitos sem o predicado exigido foram rejeitados.
- RTL: 732 casos da ALU em larguras 8, 16 e 32 comparados com `Fraction`,
  incluindo erro exato de aproximação, sinais, overflow e divisão por zero.
  Seis transações exercitaram o GCD iterativo e seu handshake.
- Distribuição: wheel e sdist construídos; os cinco pacotes, os dois headers C
  e o RTL no arquivo de fontes foram conferidos. O monólito foi regenerado e
  verificado contra as fontes rastreadas.

## Limites das conclusões

As provas cobrem os contratos e domínios declarados. A redução de IR não é
um teorema de aceleração universal. A equivalência dos mapas concretos e o
ponto fixo de bootstrap não provam um compilador arbitrário ou a cadeia C
inteira. O RTL é referência simulada, sem prova formal RTL, temporização ou
chip fabricado. Progresso do escalonador assume carga finita e serviço bem
sucedido; segurança de ações depende do modelo de estado e do host.

Consulte [o manifesto e as fronteiras](../docs/CAMINHO_C.md). O JUnit e os
binários ficam em `artifacts/`, ignorado pelo Git; os comandos reproduzem a
validação sem versionar executáveis.
