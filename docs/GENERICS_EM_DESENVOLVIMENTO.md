# OM-018 em desenvolvimento

`omega.generics` especializa templates de expressões racionais/tensoriais
puros, com parâmetros de dimensão, resolução fechada, nomes higiênicos e
orçamentos explícitos. Argumentos são mantidos mesmo quando não usados pelo
corpo, preservando falhas como divisão por zero. Templates recursivos e
captura de variáveis externas são recusados.

A API `Registry.from_dict` aceita o esquema `omega-generics-1`; `expand`
produz fonte plana e um manifesto de instâncias. Não executa templates.
A fonte expandida pode ser compilada pelo frontend nativo e seus resultados
conferidos pelo Lean.

`project_ir` remove os nomes e comandos declarativos internos, preservando
exatamente todos os nós de cálculo e seus índices. Dessa forma o log completo
do interpretador coincide com a implementação de referência nos casos testados,
inclusive as declarações do usuário. Argumentos não usados continuam no grafo;
divisão por zero não desaparece com a especialização.

`generic-ir fonte.omega --templates templates.json --saida ir.json` emite a IR
canônica projetada. `generic-build` aceita os mesmos argumentos e produz o
binário, C, fonte expandida, fonte original, templates e manifesto de instâncias.
`native-run` reproduz a expansão e verifica hashes antes de executar. Artefatos
ausentes ou adulterados bloqueiam a execução. Os certificados precisam estar
vinculados ao grafo original antes de projetar as tabelas de nomes; depois da
projeção, o Lean reconfere os resultados e derivadas. Nenhum nó matemático,
estado, valor de gradiente ou enunciado é removido por essa projeção.

A API admite somente templates puros do núcleo racional/tensorial, com grafo
de chamadas acíclico e especializações concretas limitadas. Não fornece funções
de ordem superior nem polimorfismo irrestrito. Chamadas genéricas dentro de ASTs
de provas universais continuam recusadas. A emissão de vários artefatos não é
transacional. Hashes não substituem autenticação/revisão do código. Os testes
incluem comparação de logs/estados em 13 instâncias escalares/vetoriais, admissão
nativa pelo Lean, CLI e corrupção/remoção de proveniência antes da execução.
Não há alegação de prova formal geral da transformação; revisão independente
permanece necessária para aceite.
