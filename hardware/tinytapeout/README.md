# Interface lógica Tiny Tapeout

`tt_um_omega_qpu.v` adapta o somador racional exato de 8 bits à interface padrão
Tiny Tapeout. A interface usa frames limitados, handshake por toggle e erros
explícitos. O testbench verifica 1/3+1/6=1/2 byte a byte, overread, frame incompleto
e denominador zero. O enable não deve mudar no meio de uma transação; sinais
externos devem ser síncronos ao clock, ou receber sincronizadores na placa.

`sky130.json` é uma entrada inicial para OpenLane 2. Sem PDK/slot de fabricação,
a configuração não foi validada por place-and-route, DRC/LVS nem por integração
com a versão específica do harness Tiny Tapeout. Não é um artefato de signoff,
tape-out ou fabricação. Antes de enviar um chip, o programa Tiny Tapeout precisa
ser escolhido e suas regras elétricas, limites de área e integração verificados.
