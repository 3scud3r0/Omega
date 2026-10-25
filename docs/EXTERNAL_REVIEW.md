# Protocolo proposto de reprodução externa

Este arquivo contém instruções, não uma revisão externa realizada.
Não há assinatura ou aceite pré-preenchido.

O revisor deve ser uma identidade independente dos autores/proponentes,
configurada pelo supervisor. Deve receber o commit, hashes dos artefatos,
configuração e versões das ferramentas, datasets autorizados e seeds. Deve
reproduzir os marcos em ambiente separado com os mesmos orçamentos, preservar
falhas e custos e conferir os certificados no checker correto.

`omega_bench.reproduction` representa uma revisão autenticada vinculada ao
artefato e ao experimento exatos. `ReproductionGate` verifica a assinatura por
um autenticador fornecido pelo host; um relatório autoassinado pelo proponente
não conta como reprodução independente. O pacote não cria chaves ou contatos
externos automaticamente.

A etapa de testes/validação desta entrega foi adiada pelo usuário. Permanecem
pendentes compilação dos fontes novos, provas Lean, testes de integração,
avaliações adversariais, benchmarks retidos, medições de hardware e auditoria.
