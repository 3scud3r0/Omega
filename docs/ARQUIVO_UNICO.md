# Distribuição em arquivo único

`omega/omega_3_monolith.py` é uma distribuição legível com mais de 10.000
linhas de implementações existentes incorporadas. Não são 10.000 linhas novas:
o conteúdo reúne compilador, runtime C/GMP, módulos Python, Nextorch, provas
Lean, testes, scripts, documentação e o backlog. O gerador publica separadamente
a contagem de linhas de código incorporado e o número físico de linhas do
arquivo. Strings adjacentes preservam cada linha original, sem padding.

```sh
python omega/omega_3_monolith.py verify
python omega/omega_3_monolith.py self-test
python omega/omega_3_monolith.py coverage
python omega/omega_3_monolith.py extract /tmp/omega-fontes-novas
python omega/omega_3_monolith.py omega --versao
python omega/omega_3_monolith.py omega native-types exemplos/rede_profunda.omega
```

Verificação e extração usam a biblioteca padrão Python. O comando `verify`
confere SHA-256 e comprimento de todos os arquivos e analisa a sintaxe de todos
os módulos Python. Extração só publica em um destino novo, com rename exclusivo
atômico no Linux; diretórios, arquivos e symlinks existentes são preservados.
Nenhum programa candidato é executado durante essas operações.

`omega` encaminha explicitamente argumentos à aplicação incorporada. As
dependências de Python, GCC/GMP, Bubblewrap e Lean continuam necessárias para
os comandos que as utilizam. O bundle não contém SDKs, bibliotecas binárias,
pesos treinados, credenciais nem caches `.lake`; não baixa dependências
automaticamente. O isolamento e a admissão de certificados permanecem nos
componentes existentes. `self-test` executa seis testes de componentes confiáveis;
não representa a suíte completa nem revisão independente.

O digest detecta alterações quando comparado a uma referência confiável. Não
autentica um arquivo cujo próprio manifesto também foi substituído: confira o
commit/revisão do PR. O pacote é extraído em diretório temporário para executar
a aplicação; ferramentas que exigem artefatos de build persistentes devem usar
`extract` e a preparação normal naquele diretório. Códigos de saída da aplicação
são propagados, sem promover alterações ou desabilitar verificações.

Para regenerar após editar fontes rastreados:

```sh
python scripts/build-monolith.py
python scripts/build-monolith.py --check
```

O template `scripts/monolith-components.py.txt` mantém os pequenos componentes
adicionais; os demais fontes são selecionados do índice Git, com conteúdo do
workspace. O próprio bundle é excluído da seleção para evitar recursão. Novos
arquivos precisam estar rastreados antes da geração. Não edite fontes dentro
das strings geradas: altere os originais e regenere.

## Cobertura real

A entrega de fontes **não demonstra os aceites OM-019 a OM-150**. OM-018 tem implementação limitada ao núcleo puro e aguarda revisão;
`coverage` preserva cada critério de aceite e o estado real do backlog. Não há
stubs declarados como funcionalidades concluídas. A distribuição reaproveita
capacidades existentes, mas não produz as novas provas, pesquisas, treinamento,
ganhos em tarefas retidas ou revisão externa exigidos pelas tarefas restantes.
O número de linhas, isoladamente, não satisfaz esses critérios. A versão
continua 2.0.0. O PR novo substitui a tentativa de enviar os commits posteriores
à aprovação do PR #3 pela sua branch antiga.

Os novos pacotes de implementação foram acrescentados ao inventário. Nesta revisão, testes, compilação e relatórios novos foram adiados pelo usuário; o bundle apenas incorpora os fontes escritos, sem certificá-los.
