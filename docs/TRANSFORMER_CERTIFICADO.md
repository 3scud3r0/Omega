# Softmax, RMSNorm, Self-Attention e benchmark certificado

O fluxo agora aceita redes estáticas com operações afins, ReLU, produtos,
Softmax, RMSNorm, SiLU e SwiGLU, além de Self-Attention Q/K/V com múltiplas
cabeças. Cada certificação declara a caixa de entrada, os limites de saída e
um erro absoluto máximo por coordenada. Ausência de prova, denominador não
positivo, domínio inválido ou erro excessivo impede emitir o certificado.

## O que Lean verifica

`formal/tensor/Omega/Transcendental.lean` prova os componentes reais usados pelo
gerador: multiplicação de intervalos, inversão positiva, limites da raiz,
monotonicidade da exponencial, duplicação de argumentos, ordem do Softmax e o
resto uniforme de Taylor em `|x| <= 1`. As dependências dos teoremas ficam na
política existente: `propext`, `Classical.choice` e `Quot.sound`.

Para exponenciais, o algoritmo divide o argumento por uma potência de dois,
avalia uma soma racional de Taylor e usa `Real.exp_bound` para limitar o resto.
Em seguida, eleva os intervalos positivos ao quadrado, arredondando os limites
para fora. Argumentos negativos usam inversão. Nenhum float fornece extremos
de certificado. O domínio atual da exponencial é `[-32,32]`, a precisão vai de
8 a 128 bits e a busca usa de 12 a 64 termos. O domínio é verificado para
**cada argumento intermediário**, inclusive os logits da atenção.

Para `1/sqrt(x)`, a implementação usa `isqrt` inteiro para encontrar racionais
`a,b` com `0 < a`, `a² <= x <= b²`; Lean prova a inversão dos extremos. RMSNorm
exige `epsilon > 0` e normaliza a última dimensão fixa. O adaptador representa
exatamente os valores binários dos pesos e do epsilon fornecidos pelo módulo.

O certificado gerado contém duas obrigações diferentes:

1. **Limites universais:** a semântica real do grafo permanece nos limites de
   saída para toda entrada na caixa declarada.
2. **Erro da execução concreta:** para os valores de entrada e saída assinados,
   a distância da saída racional à saída do grafo real é menor que o orçamento.

A propagação intervalar inclui todos os nós; Softmax também usa o fato de seu
denominador conter o numerador como parcela não negativa, provando pesos em
`[0,1]`. Os intervalos podem ser conservadores: uma rede válida pode ser recusada
se a caixa for larga demais ou o erro exigido for pequeno demais. Não se afirma
um erro uniforme da implementação aproximada para entradas que não foram
individualmente certificadas.

## Exportar um Micro-Transformer

```python
import torch
import omega
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from omega.transformer import CertifiedSelfAttention

@omega.certify(target="micro-v1", precision="certified-rational")
class Micro(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.norm = torch.nn.RMSNorm(2, eps=0.01)
        self.attention = CertifiedSelfAttention(
            2, num_heads=1, max_sequence_length=2, causal=True, bias=False,
        )
        # Fixture pequena e reproduzível. Modelos treinados devem fornecer
        # seus próprios pesos e um contrato de domínio que possa ser provado.
        with torch.no_grad():
            for layer in (self.attention.q_proj, self.attention.k_proj,
                          self.attention.v_proj, self.attention.out_proj):
                layer.weight.copy_(torch.eye(2) * 0.25)

    def forward(self, x):
        return self.attention(self.norm(x))

model = Micro().eval()
sample = torch.tensor([[0.25, 0.5], [0.75, 1.0]])
key = Ed25519PrivateKey.generate()  # demonstração; produção fornece sua chave
result = model.export_certified(
    sample, "artifacts/micro-transformer",
    input_bounds=[[-1, 1]] * 4,
    output_bounds=[[-30, 30]] * 4,
    max_error="1/100000", precision_bits=32,
    signing_key=key, nonce="micro-request-1",
)
```

O binário `model` é estático por padrão e recebe **novos valores em execução**:

```sh
printf '["1/2","1/4","1","3/4"]\n' > artifacts/micro-input.json
artifacts/micro-transformer/model artifacts/micro-input.json
```

A ordem das coordenadas é a ordem contígua do tensor. O executável confere a
forma e os limites de entrada. Ele usa GMP, Taylor racional e raiz inteira,
sem Python, libtorch ou libm. Exponenciais e raízes aproximadas usam uma grade
diádica de `precision_bits + 8` bits e preservam positividade. A análise real e
o teste do erro cobrem também esse arredondamento. Isso não torna irracionais
racionais exatos: o certificado declara explicitamente o erro.

O compilador auto-hospedado gera C procedural. Um emissor restrito liga dois
intrínsecos GMP auditáveis de `omega_selfhost/certified_transcendental.h` no
lugar de stubs explícitos. `model.build.json` registra hashes do compilador,
intrínsecos, runtime, grafo e artefatos; o bundle assina também esse manifesto.
Para reproduzir o build, use `omega.real_native.build_runtime`, que executa
essa ligação. Compilar os stubs `.omega` isoladamente não liga os intrínsecos.

O C/GMP e o compilador C continuam na base de confiança. Cada execução admitida
é comparada com um oráculo racional independente; Lean verifica a relação da
saída observada com a semântica real. Isso não é uma prova de refinamento de
todo o código C, nem uma prova criptográfica sucinta da execução de uma CPU.

## Auditar e certificar entradas novas

`omega.pci.verify_export` aceita o novo formato `omega-pci-real-1`. Além de
modelo, entrada, caixa, limites, nonce, contexto e chave pública externos, o
auditor deve fixar `expected_max_error`. Alterações do contrato são rejeitadas
antes de repetir trabalho formal. O auditor reconstrói a prova de dados
validados; nunca executa o arquivo Lean recebido como código confiável.

```python
from omega.pci import verify_export, digest

statement = result["certificate"]["payload"]["statement"]
checked = verify_export(
    result["directory"], public_key=key.public_key(),
    expected_graph_sha256=digest(statement["graph"]),  # reter externamente
    expected_inputs=["1/4", "1/2", "3/4", "1"],
    expected_input_bounds=[[-1, 1]] * 4,
    expected_output_bounds=[[-30, 30]] * 4,
    expected_max_error="1/100000",
    expected_nonce="micro-request-1", expected_context="micro-v1",
)
```

Use `omega.real_native.infer_certified` para executar o mesmo binário em uma
entrada nova e emitir outro certificado, com nonce novo e hash do binário
fixado externamente. A função executa uma cópia dos bytes cujo hash conferiu,
confere a saída racional e assina a ligação entre binário e certificado.
`verify_inference` audita essa ligação e repete a verificação real. A assinatura
é uma atestação do emissor; o registro de consumo de nonces pertence ao host.

## Atenção, batches e sequências limitadas

`CertifiedSelfAttention` aceita `[sequência, embedding]` e
`[batch, sequência, embedding]`. Emite as projeções Q/K/V, produtos QKᵀ,
`1/sqrt(d)`, Softmax por linha, combinação com V e projeção de saída. A variante
causal omite as chaves futuras; cada linha possui pelo menos uma chave.
O adaptador de `torch.nn.MultiheadAttention` aceita Q=K=V,
`need_weights=False`, layout padrão de projeções e, para batches,
`batch_first=True`. Máscara causal explícita é oferecida pelo módulo Ômega;
máscaras arbitrárias e linhas totalmente mascaradas não são aceitas.

As operações afins, Softmax e RMSNorm suportam tensores de rank 1 a 3. Há
orçamentos de 256 coordenadas de entrada/saída e 4096 nós escalares. Cabeças,
embedding e comprimento são constantes de cada grafo. SiLU e
`CertifiedSwiGLU` usam o mesmo mecanismo de exponenciais e produtos.

`omega.sequence_family.export_family` aceita exemplos para **todos** os
comprimentos de 1 até um máximo de 16, com embedding e batch fixos. Cada membro
tem seu próprio contrato, binário, prova, nonce e contexto. O índice assinado
`family.json` só é publicado depois de todos os membros passarem.
`verify_family` exige a lista completa de identidades esperadas, impedindo
substituição ou omissão de comprimentos. Isso permite comprimentos limitados
sem padding; não certifica laços Python arbitrários dependentes de valores.

Para classificação, `omega.transcendental.certify_softmax_argmax` usa o teorema
universal `softmax_order`, preserva o argmax estrito dos logits e dispensa a
avaliação de exponenciais. Esse caminho também funciona com logits fora de
`[-32,32]`. Na atenção, os pesos são necessários e não se pode fazer esse atalho.

## Benchmark dos três modos

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m omega_bench.certified_control \
  --output artifacts/control-comparison --samples 32 --steps 128 \
  --repetitions 3 --max-denominator 65536 --plot
```

O comando compila a mesma rede MLP/ReLU para C/GMP exato e C/GMP com poda
nativa por frações contínuas. PyTorch usa os mesmos pesos FP32 congelados,
interpretados como racionais binários nos outros dois modos. A planta é
explicitamente **linearizada**, com Euler exato, `dt=1/50` e `g/l=10`.

Entradas comuns medem erro da inferência. Trajetórias separadas partem do mesmo
estado e usam a mesma atualização racional da planta, isolando a divergência
introduzida pelo controlador. Lean prova a identidade universal da rede ReLU
com a política linear, confere cada observação exata do banco de entradas comuns
e os limites de erro observados dos outros modos nesse banco. As trajetórias
são reexecutadas independentemente com `Fraction`, sem afirmar uma prova Lean
de refinamento de cada passo da execução C. Uma decisão podada é admitida somente com margem
estrita; o dataset inclui um empate que deve ser recusado.

O relatório inclui mediana e máximo das médias por execução, memória RSS de
cada processo, tamanho de intermediários, erros exatos, divergência angular,
decisões alteradas/recusadas, versões e hashes. O tempo inclui conversão de
entrada e controlador, tanto no banco comum quanto nas trajetórias; exclui leitura do dataset, compilação e Lean. A admissão
das decisões é auditada **fora** do tempo de inferência. A memória de FP32 inclui
o runtime Python/PyTorch; ela não mede apenas os tensores do modelo.

Resultados são medições do ambiente, não promessas de velocidade. A poda pode
reduzir memória e ficar mais lenta. Erro zero do modo exato refere-se à semântica
racional declarada; poda tem erro limitado. Nenhum desses resultados prova
estabilidade de um drone, de um pêndulo não linear ou de um sistema físico com
sensores incertos. Os artefatos `report.json`, `observations.json`, `dataset.json`,
`benchmark.lean`, C, binários e `comparison.svg` permitem inspecionar a medição.

A medição desta implementação está em
[`validation/certified-transformer-benchmark.json`](../validation/certified-transformer-benchmark.json)
e no [gráfico independente](../validation/certified-transformer-benchmark.svg).
Com 32 entradas comuns, 128 passos e três repetições neste ambiente:

| Modo | Mediana por chamada | RSS do processo | Maior erro nas entradas comuns |
|---|---:|---:|---:|
| C/GMP exato | 44,479 µs | 82,88 MiB | 0 |
| C/GMP com poda | 79,646 µs | 33,88 MiB | 9,58 × 10⁻⁹ |
| PyTorch FP32 | 32,969 µs | 239,32 MiB | 1,21 × 10⁻⁸ |

A poda reteve intermediários de até 24 bits, contra 3408 bits no modo exato,
com 31 decisões certificadas e uma recusa por empate. Nesta medição a economia
de memória teve custo de tempo; não houve aceleração em relação a FP32.

## Verificação e limites restantes

```sh
bash scripts/test.sh -q
.venv/bin/python scripts/build-monolith.py --check
.venv/bin/python scripts/package.py
```

Os testes cobrem referências Decimal independentes, provas de endpoints,
orçamentos impossíveis, denominadores, atenção causal e multi-head, batches,
MHA, exportação estática, entradas novas, assinaturas/adulteração, famílias de
comprimentos, equivalência da poda GMP com `Fraction.limit_denominator` e os
três modos do benchmark.

GELU/erf, treinamento e gradientes aproximados, grafos sem limites de recursos,
máscaras arbitrárias e equivalência de programas Turing-completos não fazem
parte dessas garantias. Código fora do domínio é rejeitado. O resultado é uma
implementação completa destes caminhos delimitados, sem afirmar universalidade
para qualquer Transformer, hardware ou controlador.
