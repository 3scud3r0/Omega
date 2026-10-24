# Validação Ômega 2.0

O fluxo validado cobre o compilador auto-hospedado, a emissão e execução nativas,
o núcleo tensorial Lean e a integração Nextorch/Orange preservada.

`bash scripts/test.sh -q`: **350 testes e 64 subtestes passaram; 1 teste CUDA
foi ignorado por ausência de GPU**. A instalação completa foi repetida e
`pip check` não encontrou incompatibilidades. Lean/Mathlib foram compilados e
os teoremas gerais foram conferidos sem admissões.

## Evidências de auto-hospedagem

`build/selfhost/bootstrap.json` contém os hashes da fonte `.omega`, runtime C,
fontes C dos estágios 0/1/2/3 e binários estabilizados. O comando falha se os
fontes C divergirem ou se os binários dos estágios 1 e 2 forem diferentes.
Os testes recompilam o compilador com `PATH=/nonexistent`; os programas de rede
nativa também executam com Python indisponível no PATH.

## Regressão e ataques

- Comparação da IR auto-hospedada com o compilador de referência.
- Execução de todos os exemplos válidos, incluindo os programas de evolução,
  provas polinomiais/tensoriais, aliases em inglês e a rede profunda.
- Rejeição dos exemplos intencionalmente inválidos de tipos, dimensões,
  identidade falsa e atualização com aumento de perda.
- Gradientes e estados nativos comparados à VM de referência e certificados
  antigos revalidados independentemente quando os formatos são compatíveis.
- Prova Lean dos valores e gradientes de todas as coordenadas remapeadas pela
  otimização de exemplo.
- Rejeição de adulterações de gradiente, taxa, semente, forma, valores observados,
  cadeia de certificados, estado final e testemunha de otimização.
- Verificação exata de um parâmetro com 65 coordenadas; uma alteração na última
  coordenada é recusada pelo núcleo Lean.
- Recusa de execução verificada sem o kernel formal; recusa de identidade
  universal falsa; prevenção de colisões entre coordenadas tensoriais internas e
  nomes de símbolos do usuário.
- Vínculo entre os certificados de identidade e os comandos da IR: substituir a
  prova por uma identidade verdadeira diferente é rejeitado.
- Ordem de avaliação de chamadas, racionais, strings Unicode, identificadores
  Unicode, dígitos decimais Unicode, combustível e profundidade de recursão.

As provas fechadas são conferidas por Lean com verificação de retorno, ausência
de `sorryAx` e presença de todas as declarações esperadas. O gerador de provas de
reescrita pode produzir avisos estilísticos de táticas que deixam de ser
necessárias após o fechamento de uma meta; eles não são admissões nem substituem
a conferência pelo kernel. Os teoremas gerais reportam seus axiomas fundamentais.

Os testes originais do Nextorch incluem treinamento, persistência, Z3/Lean,
GFlowNet, SAE, Orange e projeções t-SNE/UMAP. CUDA exige hardware ausente nesta
máquina e deve aparecer como ignorado, não aprovado. A execução local não prova
que a CI remota executou; o workflow do PR reproduz instalação e testes.

Os números finais e os logs desta execução são entregues em
`artifacts/validation-v2/`. A validação 1.4 anterior foi preservada como histórico.
