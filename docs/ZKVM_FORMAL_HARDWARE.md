# Fronteiras de execução, correção e hardware

Esta entrega não fecha as três fronteiras em sua totalidade. Os critérios de
aceite devem distinguir implementação, execução simulada, prova criptográfica,
prova do compilador completo e validação física.

## O que foi implementado

- Lowering procedural compartilhado em Ômega e emissor ELF32/RV32IM para um
  subconjunto checked-u32 com oito palavras privadas, laços e combustível.
- Integração com RISC Zero fixada por Cargo.lock, provador local e verificador
  estático independente que exige identidade/journal esperados. Modos Fake e
  Composite não são aceitos. O teste real não usa a antiga recorrência AIR/FRI.
- Provas indutivas em Lean de preservação/progresso para AST aritmética→IR de
  pilha, preservando a pilha preexistente para expressões de tamanho arbitrário.
- Prova bit a bit da codificação/decodificação de ADDI com imediatos positivos,
  round-trip little-endian e vínculo desses bytes ao fragmento aditivo já
  formalizado em CompilerCorrectness.lean. Sem provas admitidas.
- Core RV64I delimitado, ROM de monitor, RAM, UART, traps e fluxo ECP5/ULX3S.
  Simulação compara cada byte e os bits de parada da UART.
- Interface lógica Tiny Tapeout para o somador racional, com frames, handshake,
  status, limites de leitura e erros explícitos. Testbench e configuração
  inicial OpenLane; a configuração não constitui signoff de ASIC.
- Correção de propagação de SIGKILL no supervisor, descoberta quando uma síntese
  excedeu o orçamento: sinais sem disposição configurável não causam EINVAL.

## Limites que permanecem

**Prova criptográfica de execução:** a geração da prova real está pendente nesta
máquina enquanto o domínio do artefato de recursão estiver bloqueado. Compilar
o verificador, rejeitar fraudes e executar bytes em Unicorn não substitui essa
prova. O workflow dedicado exige um recibo real, verificação independente e
rejeição de adulterações. Não há medição que confirme 50 KB ou 5 ms. O alvo
RV32IM não prova a execução do ELF RV64, BigRational ou treinamento neural.

**Correção formal de todo o compilador:** permanece aberta. Os novos teoremas
cobrem os domínios declarados, não parser geral, todos os tipos, tensores,
regalloc/spills, laços RV64, sistema de módulos, chamadas, runtime e loader ELF.
A prova para AST aritmética termina na IR de pilha; a prova de bytes aplica-se
apenas ao fragmento ADDI. Passar em testes não fecha esses refinamentos.

**Hardware físico:** o usuário informou não possuir placa, runner nem projeto de
fabricação. Não houve programação USB/JTAG, boot em placa, signoff DRC/LVS,
tape-out ou fabricação. O monitor é distinto do kernel privilegiado Sv39/PLIC/
VirtIO de QEMU. O core implementa RV64I parcial e não reivindica conformidade
RV64GC. A configuração Tiny Tapeout precisa ser adaptada ao harness/programa e
validada com o PDK e ferramentas de fabricação escolhidos.

## Reproduzir

```sh
bash scripts/setup-native.sh
PATH="/workspace/.tools/cargo/bin:$PATH" bash scripts/setup-zkvm.sh
.venv/bin/python -m pytest testes/zkvm -q
bash scripts/test.sh -q --junitxml=artifacts/full.xml
```

Para exigir a prova real, forneça os caminhos `OMEGA_RISC0_PROVER` e
`OMEGA_RISC0_VERIFIER` gerados por setup-zkvm.sh. Sem provador o teste é registrado
como skip, nunca como prova aprovada. Veja os detalhes em
[omega_zk/README.md](../omega_zk/README.md),
[hardware/boot/README.md](../hardware/boot/README.md) e
[hardware/tinytapeout/README.md](../hardware/tinytapeout/README.md).
