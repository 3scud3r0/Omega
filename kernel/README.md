# Ômega Kernel — três candidatos nativos em uma distribuição

`omega_kernel.omega` é uma amalgamação determinística. O prefixo é um programa
Ômega executável e contém a resolução dos módulos importados. As seções C e
Python seguintes ficam em comentários `#|`, com nomes, tamanhos e SHA-256 no
manifesto. O extrator recupera os bytes sem executá-los. Os módulos canônicos
continuam disponíveis para revisão em `kernel/` e `omega_kernel/`.

O arquivo inclui dependências reais do projeto e seus 16 motores anteriores,
acessíveis pela operação `engine`. A contagem do manifesto distingue código
dos novos componentes, dependências reutilizadas e a duplicação necessária
entre o prefixo ligado e os módulos originais. Quantidade de linhas não é
evidência de correção ou de capacidade científica.

Use o fluxo `omega kernel` para esse arquivo. O frontend genérico de módulos
tem limite de 256 KiB e não deve receber toda a distribuição multilíngue como
se fosse um módulo comum. O build do workbench compila grupos de funções
completas, de aproximadamente 12 KiB, no compilador auto-hospedado e reúne as
declarações/corpos gerados em uma única unidade C. Isso limita a arena temporária
do compilador; o executável final mantém um só runtime e símbolos compartilhados.

## 1. Kernel lógico embutido

`kernel/native/logic.h` implementa um subconjunto predicativo e intensional de
teoria de tipos dependentes, com índices de De Bruijn, universos estratificados,
Pi, lambda, aplicação, let, Sigma, projeções, identidade, reflexividade,
transporte, naturais com recursor, Unit, Empty e racionais limitados. A igualdade
definicional usa beta/delta/zeta/iota, projeções e cálculo racional exato.
Uma definição só entra no ambiente depois de seu tipo e corpo serem checados.
Não há declaração de axiomas, definições opacas ou recursão geral.

O verificador exige tipo esperado explícito; não aceita simplesmente qualquer
prova válida. O protocolo não aceita arestas futuras, constantes ainda não
checadas, campos desconhecidos ou declarações de axiomas. Não existe cache de
inferência que ignore o contexto. `kernel/omega/proof.omega` é uma implementação
independente da mesma linguagem, compilada pelo Ômega para comparação.

O núcleo C recebe arenas do chamador e não usa malloc, GMP, OpenSSL, Lean ou
chamadas ao sistema. O adaptador JSON/stdio usa a libc. O limite padrão é de
4.096 nós recebidos, arena de 16.384 nós, 1.000.000 passos e profundidade 128;
os tetos configuráveis permanecem finitos. Racionais usam numerador de magnitude
até INT64_MAX e denominador positivo até INT64_MAX. Exaustão retorna
`resource-limit`, sem afirmar que uma proposição é falsa ou verdadeira.

**Não é um importador de provas Lean/Coq, nem um CIC completo.** Não implementa
indutivos arbitrários, coindução, metavariáveis de universo, unificação, táticas,
eta, irrelevância de provas ou cumulatividade. A correção global deste novo
verificador ainda não foi formalmente demonstrada. Ele amplia a base confiável
e não substitui a política existente de aceitação Lean do restante do projeto.

## 2. Tensores racionais

`tensor.h` fornece batches SoA em arenas do chamador. AVX2, AVX-512 e NEON
calculam produtos intermediários elegíveis, com seleção por CPU e fallback
escalar exato; redução por MDC e estados de erro são explícitos por lane.
Não há truncamento, saturação nem promoção de overflow a resultado válido.

`tensor_gmp.h` representa matrizes como uma grade de inteiros GMP e um
denominador comum. O GEMM usa blocos e normaliza uma vez por matriz de saída.
Entradas compactas ativam dot products SIMD int16 com acumulador int64 e
limites prévios; demais entradas usam `mpz_addmul`. O caminho geral continua
dependendo da GMP e pode alocar memória. Os limites de bits e reservas lógicas
complementam os limites de RAM/tempo impostos pelo supervisor do processo;
a reserva lógica não mede toda a memória interna da GMP.

O grafo tem até 64 nós e 16.384 células de valores intermediários. Suporta
add/sub, Hadamard, matmul, transpose, ReLU, sum e sum-squares; o reverse mode
acumula arestas repetidas e usa subgradiente zero na origem da ReLU. Essas
operações são testáveis diferencialmente; sua implementação completa não possui
um teorema universal de refinamento para C.

Certificados de cálculos matriciais pequenos recompõem as expressões e provam
igualdades particulares no kernel, com até 32 células de saída e racionais
dentro do domínio finito. Alterar o cálculo, a saída ou trocar o certificado por
uma proposição irrelevante impede a aceitação. Isso não prova uma lei física,
nem transforma dados experimentais em fatos deduzidos da lógica.

## 3. Emissão direta de código de máquina

Os módulos `source.omega`, `assembler.omega`, `x86_64.omega`, `aarch64.omega`,
`riscv64.omega` e `elf.omega` compilam uma função pura Ômega para ELF64 Linux.
Instruções, fixups e cabeçalhos são emitidos diretamente em Ômega, sem chamar
GCC, assembler ou linker para o programa resultante. O bootstrap das ferramentas
e o caminho de tensores ainda precisam do compilador C.

O subconjunto tem parâmetros i64, constantes, variáveis locais imutáveis,
operações aritméticas, comparações, curto-circuito e árvores terminais se/senao.
Não suporta toda a linguagem Ômega, chamadas, loops, heap, strings ou tensores.
Overflow é erro; divisão só aceita quociente inteiro. Resto segue truncamento
em direção a zero; INT64_MIN/-1 é erro tanto em divisão como em resto.

O ELF tem segmentos RX e RW separados, pilha não executável e nenhuma libc ou
interpretador dinâmico. Lê exatamente N inteiros little-endian de um arquivo
somente leitura indicado em argv[1], rejeitando dados faltantes ou excedentes.
Escreve 18 bytes: dígito de status, 16 hexadecimais maiúsculos do resultado e LF.
Status/exit: 0 sucesso, 1 overflow, 2 divisão por zero, 3 erro de IO/protocolo,
4 divisão não integral. Erros carregam resultado zero.

O validador Python confere cabeçalhos, tamanho e permissões. Não é verificador
de instruções. Toda execução continua isolada por namespace, seccomp, mounts
explícitos e quotas. A política seccomp atual do projeto é do host x86-64;
AArch64/RISC-V podem ser executados nesse host com QEMU explicitamente fornecido.
Não se afirma validação em hardware ARM/RISC-V sem evidência própria.

## Uso

Na instalação do repositório, com GMP de desenvolvimento, compilador C e
Bubblewrap configurados:

```sh
python -m omega_kernel build logic
python -m omega_kernel build tensor
python -m omega_kernel build workbench
python -m omega_kernel request verify proof.json
python -m omega_kernel request verify-omega proof.json
python -m omega_kernel request tensor tensor.json
python -m omega_kernel request graph graph.json
python -m omega_kernel certify-tensor tensor.json --output certificate.json
python -m omega_kernel verify-tensor certificate.json
python -m omega_kernel compile function.omega --architecture x86_64 --output program
python -m omega_kernel run function.omega 3 7
python -m omega_kernel inspect omega_kernel.omega
python -m omega_kernel extract omega_kernel.omega /tmp/omega-kernel-sources
```

Também disponível por `omega kernel ...`. A extração é distribuição de fontes;
o adaptador Python usa os pacotes de infraestrutura da instalação do Ômega.
Para um bootstrap mínimo das fontes extraídas, `omega_selfhost/bootstrap.py`
pode compilar `omega_kernel_linked.omega` para C; compile esse C com o runtime
extraído e GMP/OpenSSL, e execute o resultado apenas no sandbox.

Exemplo `tensor.json`:

Os arquivos de entrada prontos para esses comandos estão em `kernel/examples/`.
São entradas do backend de funções puras, sem o `principal` exigido de um
aplicativo procedural completo no corpus geral.

```json
{"operation":"gemm","a":{"rows":1,"columns":2,"values":["1/3","2/7"]},"b":{"rows":2,"columns":1,"values":[3,7]}}
```

Exemplo `function.omega`:

```text
funcao square_difference(a,b) {
  var sum=a+b;
  retornar sum*(a-b);
}
```

## Manutenção e validação

```sh
python -m omega_kernel.amalgamation --generate
python -m omega_kernel.amalgamation --check
python -m pytest testes/kernel -v
```

Testes incluem comparação entre os verificadores C/Ômega, rejeição de provas
forjadas e escopo incorreto, limites, tensores contra referência exata,
gradientes, integridade de certificados, três ISAs, cabeçalhos adulterados,
fuzzing determinístico e ASan/UBSan. QEMU ausente é registrado como pendência,
não como sucesso. Benchmarks devem informar dimensões, CPU, backend, custo de
normalização e todas as dependências. Nenhum ganho de 50–100x ou tempo em
nanossegundos é prometido.

Os resultados efetivamente executados ficam em `kernel/VALIDACAO.md`; antes
da execução a presença dos testes não é evidência de aprovação. Racionais exatos
eliminam arredondamento no domínio representado; não eliminam erro de modelo,
discretização, incerteza empírica ou oscilação de energia de Verlet.
