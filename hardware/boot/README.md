# Boot de monitor RV64 em RTL / ECP5

Este alvo é um monitor de boot novo e pequeno, separado do kernel Sv39/PLIC/
VirtIO executado em QEMU virt. `rv64_core.v` implementa um subconjunto RV64I,
com x0 fixo, aritmética de 64 bits, desvios, acesso alinhado a memória e traps
para instruções não suportadas, fetch inválido e erros de barramento. Não
implementa modos privilegiados, MMU, interrupções ou extensões M/A/F/D/C.

O monitor verifica memória de 64 bits e aritmética, depois transmite
`OMEGA RV64 MONITOR: 42 OK\n` pela UART. O testbench decodifica e compara todos
os 26 bytes, incluindo bits de parada. A ROM é gerada sem montador externo por
`omega_sovereign.rv64.assemble` e contém todas as 128 palavras, inclusive padding.

```sh
.venv/bin/python tools/sovereign-tools.py
.venv/bin/python -c 'from omega_sovereign.boot import simulate; print(simulate("artifacts/monitor-sim"))'
.venv/bin/python -c 'from omega_sovereign.boot import fpga; print(fpga("artifacts/monitor-fpga"))'
```

ROM: 512 bytes; RAM: 128 bytes. O clock de entrada de 25 MHz é dividido
explicitamente por quatro; o core opera a 6,25 MHz e a UART usa esse clock.

Alvo escolhido: ULX3S com LFE5U-85F-6BG381C. As restrições vêm dos sinais
clk_25mhz G2, botão reset D6, transmissão FTDI L4 e LED B2 documentados em
https://github.com/emard/ulx3s/blob/master/doc/constraints/ulx3s_v20.lpf.
A placa e revisão devem ser conferidas antes de qualquer programação.
O manifesto registra hashes, ferramentas, seed e resultados de temporização.
O build rejeita uma saída UART eliminada pela síntese.

Não há placa, cabo/runner, PDK Sky130, slot Tiny Tapeout ou fabricação disponíveis
neste ambiente. `board_programmed`, `physical_boot_verified` e `fabricated`
permanecem falsos. Não se deve inferir boot físico, conformidade completa RV64,
DRC/LVS, tape-out ou fabricação a partir de RTL, simulação ou bitstream.
