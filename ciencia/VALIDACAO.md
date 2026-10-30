# Resultados reais da biblioteca científica

Código executado: `9c9123fede61905ba6ded9c979cc9587c179ee2c`, sobre `main`
`4452a1f`. O [registro JSON](evidencias/resultados-cpu.json) conserva os hashes dos
115 fontes, os identificadores dos relatórios e as contagens observadas. Não é
uma assinatura independente de autoria ou de execução.

## Execuções concluídas

| Verificação | Resultado |
| --- | --- |
| `bash scripts/test.sh -q --junitxml=artifacts/science-full-final.xml` | 1.122 testes e 37 subtestes passaram; zero falhas/erros; 8 pulados; 3 avisos; 1.073 segundos |
| Ciência, incluída nessa suíte | 186 passaram: 151 nativos, 18 formais, 15 integração de provas, 2 distribuição/cache |
| Lean | Builds de `formal/lean` e `formal/tensor` concluídos; todos os 18 arquivos científicos rechecados e 33 declarações auditadas |
| `scripts/security.py --analyzer docker` | 250 casos passaram; zero falhas; ASan/UBSan/LSan, fuzzing e análise estática do harness de runtime no GCC fixado |
| `scripts/regression.py` | 25 positivos e 4 negativos observados; contagem correta; zero falhas de exemplo/infraestrutura |
| Roadmap: OM-020, 024, 026, 027, 028, 131 | Seis planos com `checks_passed_acceptance_pending`; aceite e revisão independente permanecem pendentes |
| `scripts/package.py` e `scripts/build-manifest.py` | Wheel e sdist gerados; sete artefatos registrados e integridade verificada |
| Distribuição isolada, dentro dos testes científicos | Wheel instalado offline em venv sem Torch; catálogo completo e kernel nativo executados |
| Verificações estáticas | 540 fontes Python analisados; dependências consistentes; bundle sincronizado e verificável; hashes rastreados conferidos |

Os avisos da suíte são duas depreciações de localização do Orange e a configuração
de paralelismo do UMAP com seed. Não foram ocultados.

## Testes inicialmente pulados

Quatro dos oito skips eram os testes RTL pela ausência do Icarus Verilog. Depois
de instalar localmente o pacote Debian `iverilog 12.0-2+b1`, executamos:

```sh
.venv/bin/python -m pytest testes/test_qpu_rtl.py -q \
  --junitxml=artifacts/science-rtl-final.xml
```

Resultado: **5 passaram, zero pulados**, incluindo os quatro casos antes
pendentes. O teste de software desse arquivo já fazia parte dos 1.122 aprovados;
as duas contagens não devem ser somadas integralmente. A CI passa a instalar
`iverilog` para executar a co-simulação em ambientes limpos.

Os outros quatro skips são CUDA (OM-096, Triton, pipeline e stress numérico).
Não há GPU/SDK CUDA nesta execução. Permanecem pendentes conforme a opção do
usuário de continuar em CPU. A suíte completa não foi repetida após instalar o
simulador; foi repetido o arquivo afetado, com sucesso.

## Garantias e fronteiras

Os 97 módulos nativos têm exemplos executados e validação de entradas. Há
comparações independentes, casos adversariais e testes de limites, preservação,
corrupção de cache, injeção de Lean, obrigações falsas e alteração concorrente
da entrada de prova. O dispatcher liga o recibo ao snapshot efetivamente
verificado. O pipeline de experimento testa uma reação de água com código,
ELF real, obrigações Lean, headers e hashes.

Os enunciados formais usam somente as dependências fundamentais autorizadas
`propext`, `Classical.choice` e `Quot.sound`, quando necessárias. Não foram
adicionados `sorry`, `admit` ou axiomas científicos. A correção de elaboração
no módulo Universal existente apenas torna `Value` uma abreviação de `Rat`,
preservando os enunciados.

Os testes não provam refinamento geral de todo o compilador/C/GMP, adequação
empírica dos modelos, ausência absoluta de falhas ou cobertura de toda a ciência.
Os subconjuntos, aproximações intervalares e operações não suportadas continuam
declarados no [catálogo](CATALOGO.md) e no [contrato técnico](README.md). As provas
de alinhamento linear e energia livre quadrática, por exemplo, não certificam
automaticamente o kernel de gaps afins e o minimizador logarítmico.

Não houve publicação científica, broadcast blockchain, promoção de versão ou
aprovação automática. A avaliação externa dos modelos e os aceites abrangentes
do roadmap permanecem trabalhos distintos destas execuções de engenharia.

## Reprodução e artefatos

Ambiente: Linux x86_64, Python 3.12.14, Lean 4.19.0, GCC 14.2.0, Mathlib
`c44e0c8ee63ca166450922a373c7409c5d26b00b`, Torch 2.5.1 CPU e Bubblewrap.
Os caminhos `artifacts/science-*` contêm XMLs e relatórios locais; a CI os coleta
como artefatos. O registro JSON fixa seus hashes, sem confundir integridade com
autenticidade. As alterações posteriores ao commit executado são documentação,
evidências, pré-requisito de CI e atualização do bundle/manifesto gerados.
