# Validação executada dos seis componentes

Arquivo: `omega_singularity.omega`, **15,177 linhas**,
52 fontes; SHA-256 `c6a83088a18932e8cfbd8ef2c54fefed7bf36daae40553cc584f0c35477c26e7`.
As linhas incluem prefixo Ômega ligado, módulos originais, adaptadores e
bibliotecas reutilizadas. O manifesto distingue essas categorias.

- Suíte dos novos componentes: **26 testes passaram**.
- Regressão selecionada: **71 testes e 99 subtestes passaram**, sem falhas.
- A rodada selecionada registrou dois skips do caso QEMU sem configuração;
  o caso foi repetido com os emuladores explícitos: **1 teste e 2 subtestes
  passaram** em AArch64/RISC-V sob QEMU. Não ficam pendências desses casos.
- A seleção inclui kernel anterior, ASan/UBSan e fuzzing existentes, extração,
  distribuição antiga e instalação offline dos wheels científico e de engines.
- O grande arquivo misto foi realmente compilado para C e executado no sandbox.
- Busca afim e quadrática, previsão ambígua, separação treino/holdout,
  falsificação de certificados, custo estrito, parada por estagnação, rejeição
  de ativação sem autorização e quotas foram exercitados.
- P2P: assinaturas Ed25519, replay persistente SQLite, TTL, limite de bytes,
  quota de armazenamento e taxa foram testados; o transporte usou apenas loopback.
- WebGPU: shader real via Vulkan em **llvmpipe/CPU**, Mesa 25.0.7 e wgpu 0.28.1.
  Operadores racionais e overflow intermediário explícito foram comparados ao
  oráculo CPU. Falsos positivos GPU foram rejeitados pela CPU/kernel.
- CLI completo: duas tarefas sintéticas foram aprendidas e certificadas via
  self-play com o adaptador de software. O ciclo de reescrita reduziu o custo
  de nós aritméticos de **3 para 1**, gerou ELF e parou por estagnação.
  O compilador instalado e a versão estável permaneceram inalterados.

## Reprodução

```sh
python -m omega_recursive.amalgamation --check
python -m pytest testes/recursive -q
python -m omega_recursive self-play omega_singularity/examples/self-play.json
python -m omega_recursive cycle omega_singularity/examples/cycle.json
```

Para repetir o caminho do shader, instale o extra `webgpu`, selecione um ICD
Vulkan válido e rode com `--backend gpu`. Nesta máquina o teste usou um ICD
Mesa extraído de pacote Debian oficial, com o hash registrado em
`evidencias/resultados.json`, e `LP_NUM_THREADS=2`. É software, não GPU física.
A CI adicionada exige executar o shader em Vulkan de software antes dos testes;
a execução remota dessa CI não foi alegada como concluída.

A suíte completa do repositório não foi repetida nesta alteração; o conjunto
selecionado cobre os novos componentes, o kernel e as distribuições afetadas.
JUnit e logs locais estão em `artifacts/recursive-*.xml` e `.log`.

## Correções e limites

O primeiro teste do ciclo encontrou uso do codec de entrada estrito para
metadados booleanos; o hash de eventos passou a usar JSON canônico limitado.
A execução real encontrou nomes reservados no WGSL e o limite inadequado de
arquivo/memfd do driver de software. Foram corrigidos e os testes repetidos.
Falhas de execução do shader não viram fallback silencioso de indisponibilidade.

Solomonoff geral continua incomputável. O sistema faz busca finita, não demonstra
superinteligência e não executa uma Máquina de Gödel universal. Os fatos formais
são resultados particulares e aritmética de coeficientes/custo; a reflexão do
DAG permanece na base confiável. Não foi provado aumento geral de inteligência,
velocidade, segurança de hardware ou eficiência energética. GPU física,
Metal/macOS e execução integral em host ARM permanecem não validados.
