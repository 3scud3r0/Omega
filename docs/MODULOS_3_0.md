# OM-017 — módulos procedurais locais

Uma biblioteca declara explicitamente o que exporta. As demais funções são
privadas ao arquivo:

```omega
# dobro.omega
modulo aritmetica;
exportar dobro;
funcao dobro(x) { retornar x * 2; }
```

O módulo de entrada importa por caminho relativo e usa um alias:

```omega
# main.omega
importar "dobro.omega" como numeros;
funcao principal() {
  print(numeros::dobro(3));
  retornar 0;
}
```

```sh
omega module-link main.omega --raiz . --saida programa.omega
omega module-build main.omega --raiz . --saida programa
```

`module-link` produz uma fonte procedural plana e um manifesto
`programa.modules.json`. `module-build` também preserva a fonte efetivamente
compilada em `programa.linked.omega`, além do C, binário e proveniência.
Construir não executa nem promove o programa. Execução de programas
procedurais usa a API de sandbox com capacidades e limites; `native-run`
continua exigindo o protocolo de resultados/certificados tensoriais.

Os cabeçalhos (`modulo`, `importar`, `exportar`) precedem funções. `modulo` é
um rótulo opcional; a identidade real é o caminho normalizado relativo à raiz.
Não há busca implícita em diretórios globais, rede ou módulos Python.
`alias::funcao(...)` aceita chamadas; não existem variáveis globais importadas,
importação transitiva automática ou funções como valores. Bibliotecas não
definem `principal`; a entrada precisa defini-la. Exports inexistentes,
repetidos, chamadas a funções privadas e aliases desconhecidos são erros.

O linker parseia os arquivos, resolve chamadas e reemite a AST com nomes
qualificados internos injetivos. Ele não substitui texto dentro de strings,
comentários ou variáveis locais. Chamadas locais podem ser recursivas. O
grafo de importações precisa ser acíclico; erros mostram o ciclo. Dependências
são visitadas em ordem de caminho; ids de módulos, ordem de funções e
manifestos são determinísticos. Símbolos locais homônimos em arquivos
distintos permanecem separados. Toda a fonte ligada passa pela inferência
procedural antes da compilação C.

A API `omega.modules.link(entry, root)` interpreta entradas relativas a
`root`; a CLI resolve a entrada a partir do diretório atual. Imports são
normalizados lexicalmente em POSIX e não podem escapar da raiz. URLs,
caminhos absolutos em imports, barras invertidas e controles são recusados.
Um descritor aberto da raiz ancora leituras `openat` com `O_NOFOLLOW` em
cada componente. O arquivo final precisa ser regular e é aberto sem bloqueio;
symlinks, devices e FIFOs não servem como módulos. Isso evita a corrida entre
checar um symlink e abri-lo. A raiz é uma capacidade explícita de leitura;
o linker não concede seus arquivos ao candidato nem ao GCC.

Os limites são 64 módulos, um MiB de fontes no grafo, 256 Ki caracteres por
arquivo/fonte ligada, 120.000 tokens por módulo e limites explícitos de AST e
tipagem. São diagnósticos de orçamento, sem aceitação parcial. O manifesto
`omega-modules-1` contém hashes de cada fonte, imports resolvidos, exports,
origens de símbolos e hash da fonte ligada. `verify_manifest(manifest, root)`
refaz a resolução e a tipagem; mudanças na fonte ou no manifesto são rejeitadas.
O manifesto de build também vincula e confere a fonte e a closure modular
preservadas. Hashes conferem integridade; não substituem revisão/autorização.

Esta é uma etapa de ligação em Python que emite o dialeto procedural existente;
o frontend auto-hospedado continua compilando a fonte plana em Ômega. Não se
afirma que a nova sintaxe está implementada nos estágios nativos do bootstrap,
nem que houve prova formal de preservação do linker. O dialeto tensorial
permanece independente. Publicação de vários arquivos ainda não é transacional;
destinos existentes e colisões de nomes de artefatos são recusados.

Os testes compilam e executam em sandbox um projeto de três módulos, conferem
proveniência e privacidade de funções, diagnosticam ciclos e erros de resolução,
comparam ligação repetida, verificam alterações de closure e recusam escapes,
symlinks, FIFO e troca maliciosa por symlink exatamente no instante da abertura.
