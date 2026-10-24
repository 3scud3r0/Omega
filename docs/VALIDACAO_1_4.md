# Validação da integração 1.4.0

Ambiente: Linux x86_64, Python 3.12.14, PyTorch 2.5.1+cpu, Lean 4.19.0,
compilador C do sistema. O arquivo de dependências registra as versões instaladas.

## Verificado nesta entrega

- `bash scripts/setup.sh`: instalação repetida com sucesso, incluindo compilação
  do executável Lean; `pip check` sem incompatibilidades.
- `bash scripts/test.sh -q`: **337 testes passaram, 1 ignorado, 26 subtestes
  passaram**. O único teste ignorado exige CUDA, indisponível neste ambiente.
  Três avisos de dependências: duas depreciações Orange e um aviso de UMAP
  sobre paralelismo com seed fixo. Nenhum teste de Lean foi ignorado.
- A suíte inclui os 226 testes históricos, testes originais do Nextorch, widgets
  Orange reais em modo offscreen, t-SNE/UMAP, rejeição de certificados adulterados,
  contrapropostas neurais erradas, falha fechada sem Lean, provas falsas recusadas
  pelo Lean, execução C de todos os operadores e revalidação independente.
- `omega intuition exemplos/tarefas_abertas.json --saida artifacts/intuicao
  --lean --native`: cinco tarefas, com 64 linhas no total; cinco provas Lean e
  cinco executáveis C. A auditoria refez as provas e recompilou/testou os binários.
  As cinco tabelas previstas pelo modelo nessa execução coincidiram com a
  especificação; isso mede ajuste ao domínio conhecido, não generalização.
- `omega_kernel` aceitou o certificado e emitiu o bytecode; também foi executado
  com ambiente vazio e `PATH=/usr/bin:/bin`, sem Python ou Lean no PATH. Seus testes
  rejeitam uma tabela/circuito inconsistente. O binário usa bibliotecas Linux
  usuais, não a instalação Python ou o processo neural.
- `python -m nextorch demo --lean --cycles 1 --problems 4 --width 16`: quatro
  propostas do modelo rejeitadas; quatro exemplos do especialista simbólico
  admitidos com certificação. Relatório, replay e checkpoint foram produzidos.
- Pacotes wheel e sdist construídos; o wheel inclui o Nextorch, o núcleo Lean,
  os widgets e os ícones. O wheel foi instalado em diretório isolado e executado
  fora dos dois checkouts; a prova Lean empacotada também foi conferida.

Os resultados são locais. Não há alegação de execução de CI remota, publicação
no GitHub, validação CUDA, auto-hospedagem completa ou prova do núcleo tensorial.
O escopo formal e as etapas pendentes estão em `ESTADO_DOS_TRES_PASSOS.md`.
