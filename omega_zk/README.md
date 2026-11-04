# Execução verificável delimitada

`stark.omega` e `omega_sovereign.air_fri` continuam sendo um experimento de
AIR/FRI para uma recorrência Goldilocks, sem conhecimento zero. Eles não são
aceitos pelo novo verificador de execução.

A integração em `risc0/` fixa RISC Zero 3.0.3 e seu kernel de compatibilidade
2.2.3, com todas as dependências transitivas/checksums em Cargo.lock. O provador
é local, em CPU. O verificador aceita somente `SuccinctReceipt`, confere a
identidade esperada da imagem e o journal público esperado, e rejeita recibos
Fake/Composite, bytes extras, falhas de execução e adulterações. O modo de
desenvolvimento fica desabilitado na compilação. Não usa Bonsai, CUDA ou Groth16.

O alvo é um guest RV32IM, distinto do ELF RV64 nativo do Ômega. O parser e o
lowering procedural são os mesmos de `backend_elf64.omega`, com a entrada privada
explícita `private(0)` a `private(7)`. São admitidos inteiros u32, variáveis,
comparações, condicionais, laços, break e retorno. Todos os valores intermediários
devem caber em u32; overflow, underflow, divisão por zero, divisão não integral,
queda sem retorno e esgotamento de combustível encerram com erro. Frações,
tensores, funções gerais, efeitos e treinamento neural não estão nesse alvo.

O guest lê exatamente oito palavras privadas, solicita entropia ao host, executa
o programa e compara o retorno ao resultado público declarado. Somente em caso
de sucesso publica um journal com os hashes do fonte e da IR, resultado,
combustível e versão semântica. A identidade criptográfica inclui também o
kernel de compatibilidade. O verificador precisa de uma identidade e journal
esperados, obtidos por uma compilação confiável; aceitar os valores enviados
pelo próprio proponente não vincula a prova ao problema desejado. A prova
estabelece a existência de uma entrada privada que produz o resultado, não sua
origem empírica nem a correção do compilador fonte→IR.

## Uso

Pré-requisitos de build: rustup, Rust 1.90.0, compilador C++17 e dependências do
bootstrap Ômega. O provador tem dependências C++ em tempo de build; não é uma
implementação autóctone sem dependências. O verificador Linux/musl é estático;
não precisa de Lean, fonte, entrada privada ou reexecução do guest para verificar
um recibo. Não é um binário bare-metal.

```sh
bash scripts/setup-zkvm.sh
.venv/bin/python -m omega_zk --tool build/risc0/release/omega-risc0 compile \
  omega_zk/examples/soma_privada.omega --result 10 --output artifacts/zkvm-program
# Crie um JSON local com oito u32. Não publique a entrada privada.
.venv/bin/python -m omega_zk --tool build/risc0/release/omega-risc0 prove \
  artifacts/zkvm-program caminho/entrada-privada.json --output artifacts/receipt.bin
.venv/bin/python -m omega_zk \
  --tool build/risc0/x86_64-unknown-linux-musl/release/omega-risc0 verify \
  artifacts/receipt.bin --image-id IDENTIDADE_ESPERADA \
  --journal artifacts/zkvm-program/journal.json
```

A compilação do provador exige o artefato de recursão em
`risc0-artifacts.s3.us-west-2.amazonaws.com`, verificado pelo SHA-256
`744b999f0a35b3c86753311c7efb2a0054be21727095cf105af6ee7d3f4d8849`.
Não substitua esse artefato por um arquivo vazio, não habilite DOCS_RS e não
aceite recibos simulados para contornar falhas de instalação.

Os testes em `testes/zkvm/reference.py` executam os bytes em uma CPU RV32IM
independente (Unicorn), com um adaptador mínimo da ABI. São testes de compilação
e execução, não provas de conhecimento zero. O teste criptográfico real exige
`OMEGA_RISC0_PROVER` e `OMEGA_RISC0_VERIFIER`; sua ausência gera um skip explícito.
O workflow `zkvm.yml` fornece ambos e exige geração/verificação/adulteração reais.
A segurança depende do protocolo e implementação RISC Zero, hashes e parâmetros
fixados; não foi demonstrada em Lean neste repositório. Não há evidência de
50 KB/5 ms, nem de provas para dez horas de treinamento, nesta entrega.
