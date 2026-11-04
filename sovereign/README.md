# Fundação soberana: implementações e limites

Este documento registra o PR20. Para o incremento seguinte, consulte
[backend, rede, consenso e Ouroboros](PR21.md).

Esta entrega adiciona mecanismos executáveis aos seis eixos solicitados. **Não
conclui os seis eixos** e não transforma testes de subconjuntos em garantias do
compilador inteiro. O compilador geral continua dependendo de C/GMP e Python no
bootstrap. Não houve fabricação nem teste de placa física.

| Eixo | Implementação executável | Critérios ainda abertos |
|---|---|---|
| Backend e aritmética | Emissor ELF RV64IM próprio; compilador binário que lê expressões Ômega e emite outro ELF; BigInt de limbs de 32 bits, sinais, soma, produto, divisão, GCD e BigRational normalizado em Assembly | Linguagem completa, backend BigRational x86-64, Mach-O, compilador geral escrito em Ômega e bootstrap sem Python |
| Correção formal | Quatro teoremas Lean: preservação de valores/erros do compilador escalar para máquina de pilha, roundtrip de tokens, gramática prefixa não ambígua e serialização injetiva | Refinamentos do parser infixo real, lexer, runtime de limbs, assembler, instruções de máquina, ELF e restante da linguagem |
| Hardware | RTL iterativo de soma racional exata, testes diferenciais, síntese Yosys, place-and-route nextpnr e bitstream icepack para iCEstick HX1K/TQ144; configuração e executor OpenLane/Sky130 | Programação/teste de placa; execução OpenLane com PDK real, DRC/LVS/signoff, encapsulamento e fabricação |
| Bare-metal | Boot RV64 M→S, PMP, Sv39, páginas RX/RW/NX, faltas de página reais, CLINT, PLIC/UART, VirtIO-blk MMIO v2 e registro de conteúdo SHA3 em disco, executados no QEMU sem SBI/Linux | Sv48, SMP, UEFI, drivers de outras placas, filesystem completo, snapshots, alocação e atomicidade diante de perda de energia |
| Redes e criptografia | Núcleos TCP/IPv4 e Raft em Ômega; adaptador durável Raft; SHA3-256, HMAC-SHA3-256 e X25519 em RV64, comparados com implementações independentes | NIC integrada ao guest; TCP completo/congestionamento; TLS 1.3 ou protocolo nativo auditado; Ed25519 nativo; prova de tempo constante de X25519 e prova de segurança do consenso inteiro |
| Provas de execução | AIR com restrições de transição e fronteira, compromissos Merkle, Fiat–Shamir e testes de baixo grau FRI para máquina aritmética finita | Privacidade ZK, provas de programas Ômega arbitrários, análise de segurança auditada e parâmetros de 128 bits |

## Compilador binário RV64

`sovereign/native/compiler.S` implementa diretamente a análise e emissão de uma
linguagem fechada: uma ou mais instruções `mostrar expressão;`, literais
inteiros decimais, parênteses, negação, `+`, `-`, `*` e `/`. Não aceita funções,
variáveis, strings, IO arbitrário ou tensores. A saída é sempre `numerador/denominador`.

Exemplo de entrada:

```omega
mostrar (123456789012345678901234567890 / 3 + 1) * -2;
mostrar 1/7 + 2/7;
```

O utilitário Python monta o **seed** uma vez; o seed executável compila esse
texto para ELF sem chamar Python, C, GCC, Clang, GNU as, linker ou GMP. Em hosts
RISC-V o executável usa syscalls Linux diretamente; no host x86 desta validação
ele roda em QEMU user dentro do sandbox existente. Isso é independência de
runtime para esse fragmento, não auto-hospedagem de todo o compilador Ômega.

O limite padrão é 128 limbs/4096 bits por inteiro, configurável entre 16 e 1024
limbs. Há 32 posições na pilha de avaliação, 64 níveis de análise, 16 KiB de
entrada/literais e 8 KiB para instruções geradas. Exceder o orçamento encerra
com erro; não trunca, aproxima ou retorna sentinelas numéricas. A multiplicação
reserva a soma dos tamanhos dos operandos, portanto pode rejeitar um produto
que normalizaria para menos limbs. A execução possui também orçamento de SO.

## Reprodução e evidências

Ferramentas necessárias: Python/pytest e ambiente Ômega existente, Lean 4.19
com Mathlib fixada, bubblewrap, QEMU user/system RISC-V, Icarus Verilog, Yosys,
nextpnr-ice40 e icepack. O lock em `requirements/sovereign-tools.json` contém
versões, tamanhos e SHA-256 dos pacotes Debian 13 usados nesta sessão.
`tools/sovereign-tools.py` extrai os pacotes sem root/postinst. As dependências
já instaladas no host continuam sendo pré-requisitos; esse lock não é uma
imagem de SO hermética. Em outras distribuições, use ferramentas compatíveis
do sistema. Não substitua bibliotecas do host pelas de outra distribuição.

```bash
.venv/bin/python -m omega_sovereign seed artifacts/sovereign/compiler
.venv/bin/python -m omega_sovereign crypto-reference artifacts/sovereign/crypto
.venv/bin/python -m omega_sovereign boot artifacts/sovereign/boot.elf
.venv/bin/python -m omega_sovereign fpga artifacts/sovereign/board
.venv/bin/python tools/validate-sovereign.py --output artifacts/sovereign/review
```

Os destinos precisam ser novos. A validação cria executáveis, disco temporário,
bitstream, logs, prova AIR/FRI, XML de testes e `report.json` com hashes e
resultados reais. Candidatos Linux rodam em namespaces/seccomp/rlimits. A
simulação de máquina usa QEMU sem rede, com disco novo explícito e orçamento;
o emulador é ferramenta confiada, o guest não recebe o filesystem do host.

O bitstream executa um autoteste `1/3+1/6=1/2`: LED1 sucesso, LED2 falha, LED3
heartbeat, LED4 ocupado e LED5 inicializado. Não é a Q-PU tensorial completa.
O núcleo aceita numeradores/denominadores unsigned de 8 bits; saídas de 17 bits
normalizadas; divisor zero é erro explícito. O pior caso do GCD por subtrações
é finito por esses limites, mas não tem latência constante.

OpenLane só executa com `openlane` instalado e `--pdk-root` contendo `sky130A`.
Ausência de ferramenta/PDK/GDS é erro. O executor nunca marca signoff ou
fabricação como aprovados, nem inicia pedidos de fabricação.

## Fronteiras de confiança

As provas Lean estão em `formal/Sovereign.lean`; não contêm novos axiomas,
`sorry` ou `admit`. A gramática provada é de **tokens prefixos**, distinta do
parser infixo nativo. Testes diferenciais ligam as implementações às referências;
não substituem os refinamentos formais ainda pendentes.

X25519 usa a ladder RFC 7748 e rejeita segredo compartilhado todo zero. As
divisões/normalizações da implementação têm tempo variável: **não use chaves
secretas de produção**. SHA3 e HMAC também precisam de auditoria e provas de
refinamento; ausência de branches por dados no código não prova ausência de
canais laterais físicos. Os três algoritmos não constituem TLS.

O TCP é um endpoint passivo stop-and-wait com IPv4 sem fragmentação e sem opções
TCP: MTU 1500, uma transmissão pendente, 4096 bytes recebidos e cinco retries.
Não abre sockets nem transmite na rede. Raft exige membros autenticados e
fixos, 3/5/7 nós, até 256 entradas e até 64 eventos por chamada. Não tolera nós
bizantinos. O adaptador host faz fsync do hard state antes de devolver respostas,
abandona o papel volátil em falhas de persistência e reinicia como follower.
Isso não formaliza o armazenamento, o transporte ou o protocolo completo.

AIR/FRI prova apenas `x[i+1]=x[i]^2+c` no campo Goldilocks, entre 8 e 256 passos.
O verifier recebe o enunciado esperado externamente, autentica aberturas, checa
restrições e folds; não reconstrói o traço. As aberturas **revelam dados** e o
campo de 64 bits não oferece uma alegação de segurança de 128 bits. A prova é
experimental, pode ter centenas de KiB e não é um certificado Lean, uma zk-VM
universal ou uma prova de ausência de bugs do Ômega.
