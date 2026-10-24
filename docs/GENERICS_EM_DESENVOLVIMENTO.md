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

Esta tarefa ainda não tem aceite: declarações temporárias introduzidas pela
expansão aparecem no log do interpretador legado. Valores solicitados e
gradientes são comparados nos testes, mas equivalência de todo o log ainda
não está estabelecida. A CLI, proveniência integrada, validação completa de
regressão e revisão independente também permanecem pendentes.
