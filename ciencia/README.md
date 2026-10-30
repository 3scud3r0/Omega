# Biblioteca científica Ômega — 115 contratos de implementação

O catálogo contém os 115 caminhos solicitados: 97 módulos `.omega` executáveis e
18 arquivos Lean. Sete aplicativos, dois módulos comuns e o pacote de supervisão
`omega_science` integram a biblioteca. A versão publicada do projeto continua
2.0.0. Quantidade de arquivos não certifica uma versão 3.0 nem aceitação científica.

A implementação é de modelos e domínios delimitados, descritos individualmente
em [CATALOGO.md](CATALOGO.md) e no catálogo legível por máquina
[catalogo.json](catalogo.json). Não é uma biblioteca exaustiva de toda a ciência.
Os resultados de execução e as pendências estão em [VALIDACAO.md](VALIDACAO.md).

## Execução

```sh
bash scripts/setup.sh
.venv/bin/python -m omega science list
.venv/bin/python -m omega science run 23 exemplos/ciencia/agua.json
.venv/bin/python -m omega science experiment 23 exemplos/ciencia/agua.json \
  --saida artifacts/ciencia-agua
.venv/bin/python -m omega science prove exemplos/ciencia/observacoes.json \
  --saida artifacts/ciencia-observacoes
```

Use destinos novos. Também existe `python -m omega_science`, que não precisa
carregar os componentes neurais da CLI geral. `science build fisica` informa o
caminho do executável nativo. Depois de compilar, ele pode ser chamado diretamente:

```sh
CAMINHO_DO_BINARIO 1 exemplos/ciencia/oscilador.json
```

O binário recebe um ID de seu domínio e um JSON de entrada. Sua saída usa o codec
canônico de documentos racionais (`std/string.omega`); `omega_science` converte
esse protocolo para objetos e para JSON legível. IDs 81–98 são arquivos formais,
não operações nativas. Entradas, exemplos e escopos de cada ID estão no catálogo.

As rotinas científicas são implementadas em Ômega e compiladas para C/GMP. Não
usam Python, PyTorch, MATLAB ou floats para os cálculos. A supervisão de build,
serialização, sandbox e Lean usa Python, como o restante do projeto. O executável
compilado não inicia Python. Ele depende de Linux, libc, GMP e OpenSSL; não é um
binário freestanding nem um executável universal para qualquer máquina.

O wheel inclui os fontes científicos em `omega_native/_sources` e suporta os
comandos locais de catálogo/build/run. Provas e experimentos com Lean requerem
a toolchain e o projeto formal preparados no checkout. Uma instalação não baixa
modelos, datasets, artigos ou credenciais automaticamente.

## Contratos numéricos e recursos

Use inteiros e strings como `"1/3"`; a API Python também aceita `Fraction`.
Floats, bools, null, dimensões incompatíveis, divisões inválidas e domínios fora
do contrato são recusados. Os escalares e os tamanhos das matrizes, sequências,
grafos, árvores e circuitos têm orçamentos explícitos nos fontes. Inteiros usados
por Miller–Rabin, Pollard e Euclides utilizam resto via GMP/`qfloor`, sem truncar
os intermediários para um inteiro de máquina.

Os binários executam em Bubblewrap sem rede e sem acesso ao restante do workspace,
com limites de tempo, CPU, memória, combustível, profundidade e saídas. O cache
vincula a closure de módulos, fonte ligada, headers, bootstrap e binário. Artefatos
modificados são rejeitados; uma mudança nos fontes gera outra chave de build.

Uma operação pode falhar por orçamento, mesmo quando seu tamanho está dentro do
limite estrutural. Em particular, enumeração de Ising e crescimento de denominadores
têm custo real. Não se promete simulação por bilhões de passos ou tempo fixo de
reprodução. O usuário deve declarar a unidade física dos dados: os kernels
recebem valores nas unidades coerentes do modelo; não inferem unidades de números
sem anotação. O ID 103 oferece um grafo de dimensões SI com conversões exatas.

## Provas e experimentos

```sh
(cd formal/tensor && lake build ScienceAxioms)
.venv/bin/python -m pytest testes/science -q
```

Os 18 arquivos formais preservam os nomes do inventário, mas seus enunciados
explicitam hipóteses e subconjuntos. Há provas de conservação para o oscilador
quadrático, forma simplética, boost normalizado de Lorentz, rotações racionais
unitárias, conservação estequiométrica linear, optimalidade/atingibilidade da
recorrência de Needleman–Wunsch com gaps lineares, limites reais de Taylor,
identidade de Sylvester 3×3 e estabilidade assintótica escalar, entre outras.
Não se adicionam postulados físicos como novos axiomas Lean. O checker audita as
dependências permitidas (`propext`, `Classical.choice`, `Quot.sound`).

`science prove` reconstrói obrigações fechadas sobre dados numéricos: igualdade de
somas, produtos escalares, somas de quadrados e não negatividade. O nativo emite
as expressões completas e hashes; o supervisor roda Lean, compila `.olean` e só
emite receipt após aceitação e auditoria. Não recebe táticas, imports ou código
Lean do solicitante. Uma obrigação falsa produz erro e mantém evidências parciais.
O certificado é de sua proposição numérica, não de uma hipótese científica inteira.

`science experiment` tem contratos revisados para os IDs 1, 23, 50, 53, 70 e 102.
Executa o modelo, vincula as observações ao build, reconstrói os testes numéricos
do contrato, pede Lean e prepara um artigo com código ligado, C, binário em hex,
prova, receipt, headers e hashes. Para outros IDs use `run`; o agente não escolhe
um checker mais fraco. Os arquivos do experimento e seus hashes ficam em
`experiment.json`. SHA-256 verifica integridade relativa à referência conhecida;
não autentica autor, origem experimental ou instante de descoberta.

O refinamento geral de C/GMP e do compilador não é demonstrado por esses novos
teoremas. A prova matemática da recorrência linear de alinhamento não é uma prova
completa do código nativo de gaps afins. A prova quadrática de energia livre não
certifica automaticamente o minimizador nativo de mistura ideal logarítmica.
Os dados, suas unidades, condições de contorno e a adequação física/empírica de
cada modelo continuam exigindo revisão. Lean verifica consequências no sistema
formal declarado; não demonstra consistência absoluta de toda a matemática nem
verdade empírica de uma lei da natureza.

## Correções necessárias às alegações do inventário

- Verlet é simplético e, no oscilador implementado, preserva uma energia modificada;
  a energia física geralmente muda. A mudança é reportada explicitamente.
- Aritmética racional evita arredondamento. Erros de discretização, de modelo e de
  dados permanecem. Seno, log, raízes e constantes irracionais usam intervalos.
- Eulerianos de De Bruijn podem produzir sequências diferentes com os mesmos
  k-mers. O arquivo Lean contém um contraexemplo de não unicidade.
- A CCR do oscilador quântico não pode valer sem defeito em dimensão finita.
  O termo de fronteira é explicitado. Gates H/T e amplitudes gerais ficam fora
  de ℚ(i); o emulador suporta gates racionais e estado esparso, não 2³² amplitudes.
- O FDTD implementado conserva divergência magnética discreta em uma malha TE 2D;
  isso não é, por si só, uma prova de conservação da carga elétrica.
- Equilíbrio químico e conservação de átomos não demonstram viabilidade de uma
  síntese. A conservação só cobre as linhas declaradas no inventário fornecido.
- Os arquivos de espectro/IK/Voronoi têm, respectivamente, um solver simétrico
  2×2, geometria planar 2R e recorte por semiplanos; não anunciam QR genérico,
  IK irrestrita de seis eixos ou o algoritmo de Fortune.
- O gerador de ruído usa uma aproximação gaussiana discreta finita. Os escores
  PAM/BLOSUM são estimados de contagens fornecidas, não tabelas publicadas inventadas.

## Agentes, autoridade e publicação

Hipóteses, ajustes amostrais, observações, papers e citações entram como dados sem
autoridade. O extrator de literatura reconhece somente o formato controlado
`CLAIM equality NUMERO NUMERO`; outras passagens ficam identificadas como não
suportadas, com proveniência. Não introduz axiomas automaticamente.

O falseador procura contraexemplos em um domínio finito; uma busca sem testemunha
não prova universalidade. O planejador químico otimiza apenas o grafo e os custos
fornecidos. Nenhum módulo aciona equipamento, fornece receita de laboratório,
publica artigo ou movimenta recursos financeiros automaticamente.

O registro blockchain prepara um payload Bitcoin OP_RETURN/EVM com o digest.
Broadcast, taxas, assinatura e verificação independente de inclusão dependem de
um adaptador externo autorizado. `broadcast=0` e a ausência de timestamp verificado
permanecem explícitos. O pacote não fabrica uma publicação ou confirmação de rede.
