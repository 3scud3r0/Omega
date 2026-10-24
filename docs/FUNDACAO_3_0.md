# Fundação para Ômega 3.0 — OM-001 a OM-010

Base de implementação: `db582ea1c13919f9d0ab94b893b37bb98aa0073f`.
O contrato completo das 150 tarefas está em `roadmap/tasks.tsv`. Os critérios
fornecidos pelo usuário foram preservados, em ordem, nas 11 fases (0 a 10).
Esta entrega estabelece a fundação; não constitui a conclusão das 150 tarefas,
uma versão 3.0 validada ou uma demonstração de inteligência geral.

## Entregas e reprodução

| Tarefa | Implementação | Verificação |
| --- | --- | --- |
| OM-001 | Biblioteca `ProofPrelude` declarada em Lake e importada pelo executável; dependências reais das provas geradas | Build Lean + teste de identidade trivial e regressão de identidades matriciais |
| OM-002 | `testes/corpus.json` com cobertura exata, 24 exemplos positivos e quatro rejeições previstas | `scripts/regression.py`; falhas de infraestrutura e de programas são categorias distintas |
| OM-003 | CI Ubuntu 22.04/24.04, Python 3.12.14, Lean/Mathlib fixados, ações por SHA; nenhum cache de módulos Lean compilados | Logs e artefatos por sistema; confirmação remota é um requisito separado do teste local |
| OM-004 | Manifesto abrange todo `.omega` de `exemplos/`, incluindo subdiretórios | IR/estado/saída contra referência v1; observáveis e parâmetros contra referência clássica; C procedural contra estágio zero |
| OM-005 | Mutações reproduzíveis de lexer/parser, JSON, racionais e IR; regressões de escapes truncados e estruturas cíclicas | `scripts/security.py`, seed 20261024; rejeição normal, sinal e timeout são distinguidos |
| OM-006 | ASan, UBSan, LSan habilitados; análise GCC do runtime/codec sem dispensar diagnósticos | Alvo com defeito deliberado comprova a instrumentação; compilador completo é instrumentado/fuzzado, não declarado integralmente analisado pelo GCC |
| OM-007 | `Budget` validado, prlimit, supervisão de saída/tempo; combustível/profundidade na execução nativa | Testes de CPU, tempo, memória, saída, combustível, recursão e quota do scratch |
| OM-008 | Namespaces Bubblewrap, mounts explícitos, ambiente limpo, seccomp e recolhimento de processos | Bloqueio de rede/fork, leitura/escrita externa e segredos; ausência do mecanismo impede execução |
| OM-009 | Hashes do compilador, runtime, bootstrap, supervisores, GCC e GMP; registro por binário e manifesto da distribuição | `scripts/build-manifest.py`; adulteração, ausência e caminhos que escapam são recusados |
| OM-010 | Modelo de ameaças, fronteiras e limitações abaixo | Testes adversariais do sandbox, certificados, corpus, manifesto e sanitizers |

Em Linux x86-64, instale GCC/GMP, zstd, bibliotecas Qt, Bubblewrap, Meson,
Ninja, pkg-config e libcap-dev. `bash scripts/setup.sh` prepara Python e Lean;
em distribuições com Bubblewrap antigo, `setup-sandbox.sh` compila a versão
0.12.0, com o hash do arquivo oficial fixado. O ambiente precisa permitir
namespaces de usuário. A CI configura essa capacidade nos seus runners descartáveis.

```sh
bash scripts/setup.sh
bash scripts/test.sh -q --junitxml=artifacts/foundation/test-results.xml
.venv/bin/python scripts/regression.py --output artifacts/foundation/corpus.json
.venv/bin/python scripts/security.py --output artifacts/foundation/security.json
.venv/bin/python -m build --no-isolation
.venv/bin/python scripts/build-manifest.py --output artifacts/build-manifest.json
.venv/bin/python scripts/build-manifest.py --verify artifacts/build-manifest.json
```

O relatório do corpus contém a contagem esperada derivada do manifesto, a
contagem observada e o resultado individual de cada arquivo. Um sinal de
processo, falta de kernel ou sandbox e timeout não contam como rejeição
intencional de exemplo. Um novo exemplo sem classificação impede aprovação.
O manifesto é uma especificação revisável, não uma contagem descoberta depois
de observar quantos exemplos passaram.

## Invariantes de execução e fronteiras de confiança

São não confiáveis: fontes fornecidas, programas compilados, certificados JSON,
mutações e resultados nativos. GCC/GMP, Python, Lean, Mathlib, Bubblewrap,
prlimit, biblioteca C, carregador e kernel Linux pertencem à base confiável.
Hashes detectam alterações; não autenticam um autor e não substituem revisão.
A prova de um subconjunto semântico não prova o kernel Linux, GCC ou GMP.

O frontend auto-hospedado e os candidatos nativos executados pelas APIs e pelo
launcher `omegac` passam pelo sandbox. Ele recebe somente o executável, as
bibliotecas do sistema e os caminhos explicitamente concedidos. Não recebe
HOME, proxy ou credenciais. Possui namespaces privados de rede, processos e
mounts, capacidades removidas, filtros de syscalls e scratch temporário com
limite agregado de espaço. A API falha se o mecanismo não estiver disponível.
Executar um binário diretamente no shell ultrapassa essa API e fica sob a
responsabilidade de quem o executa; o binário não é uma VM de isolamento.

O perfil normal impede criação de processos/threads e sockets. O verificador
Lean tem um perfil explícito que permite somente clones de threads com VM,
grupo de threads e manipuladores compartilhados; clone3 retorna ENOSYS para
que libc use o clone filtrado. Fork e rede continuam proibidos. O processo
supervisor externo adota e recolhe monitores órfãos. Os builds e a elaboração
de provas geradas exclusivamente por renderizadores confiáveis têm limites
de recursos, mas permanecem ferramentas confiáveis fora desse sandbox.

Escrita persistente só existe quando o chamador confiável concede um diretório.
Um arquivo montado somente para leitura dentro desse diretório permanece
protegido. A quota agregada do scratch não é uma quota agregada dos diretórios
persistentes concedidos: nesses diretórios aplicam-se limites por arquivo,
tempo e recursos. Não conceda um diretório externo a código desconhecido para
obter apenas uma saída; use o scratch e copie a saída validada. Os caminhos
temporários de compilação são concedidos pelo orquestrador, nunca pelo programa.

Tempo de CPU, endereço virtual, tamanho de arquivo, descritores, stack e
processos têm limites de sistema operacional. O supervisor limita tempo real
e captura de saída. Combustível mede pontos instrumentados da linguagem,
não instruções de CPU; profundidade da linguagem e de codecs é controlada,
e stack/CPU/tempo continuam limitados mesmo para código que não coopere.
O runtime libera seus racionais GMP e alocações registradas ao sair normalmente
ou por rejeição. Ao receber SIGKILL o sistema operacional recupera a memória.

ASan reserva cerca de 20 TiB de endereço virtual para sombra. Somente os alvos
diagnósticos fixos usam uma quota virtual de 32 TiB e o watchdog RSS do ASan;
isso **não é uma garantia rígida de memória física**. CPU, tempo, arquivos,
saída, isolamento e ambiente limpo permanecem ativos. LSan precisa de um
auxiliar/ptrace dentro do namespace privado; esse perfil permite esses
recursos e nunca é usado para execução normal. Vazamentos não são desabilitados.

## Limites da evidência e aprovação

Fuzzing finito e sanitizers encontram falhas, mas não demonstram ausência de
comportamento indefinido para toda entrada. A análise estática cobre as entradas
de dados do runtime/codec; a análise integral do C do compilador excedeu o
orçamento e não é reivindicada. Paridade diferencial cobre os observáveis das
referências disponíveis, sem uma prova geral de equivalência de compiladores.
CUDA depende de GPU e é relatado separadamente quando indisponível.

Apenas os relatórios da execução atual sustentam contagens. A CI remota e uma
reprodução em ambiente limpo devem ser conferidas no PR. O próprio autor não
é o revisor independente: revisão externa e aprovação permanecem pendentes
até alguém independente realizá-las. Nada nesta entrega faz merge, promove
alterações no núcleo estável ou declara as OM-011 a OM-150 concluídas.

## Resultados locais em 24/10/2026

- Suite completa: 367 testes e 37 subtestes aprovados; um teste CUDA ignorado.
- Corpus: 24 exemplos aprovados e quatro rejeições previstas, sem falhas de
  infraestrutura ou diferenças contra as referências.
- Segurança: 250 casos aprovados, incluindo execução tensorial/AD instrumentada,
  validação Lean dessa saída, canário ASan e análise GCC do runtime.
- Build Python: wheel e sdist produzidos; manifesto verifica seus hashes e os
  binários dos estágios e dos dois kernels Lean.
- Preparação Bubblewrap 0.12.0 compilada e executada neste ambiente sem root,
  utilizando headers libcap obtidos de metadados Debian assinados. Runners da CI
  instalam seus pré-requisitos com apt.

Os resultados locais não contam como reprodução externa. O progresso continua
com revisão independente pendente em `roadmap/progress.json`.
