# OM-016 — resultados e falhas explícitos

`omega_platform.results` define variantes `Ok(value)` e `Err(Problem)`.
`Ok(None)` é um sucesso explícito, distinto de qualquer erro. Conversão
implícita para bool é recusada; o consumidor inspeciona `result.is_ok`.
Desembrulhar um `Err` levanta `PipelineFailure`, preservando a exceção original
como causa. Erros inesperados também geram falha, com sua causa disponível
para diagnóstico; nunca se tornam um valor de sucesso. Interrupções do
operador (`KeyboardInterrupt`/`SystemExit`) se propagam.

```python
from omega_selfhost.driver import build_checked, run_checked
from omega_platform.results import Err
result = build_checked('entrada.omega', 'programa')
if isinstance(result, Err):
    print(result.problem.code, result.problem.stage)
else:
    print(run_checked('programa').is_ok)
```

`compile_ir_checked`, `build_checked` e `run_checked` identificam a etapa
relevante: tipos, IR/build, execução, prova ou gravação de arquivos. Os
campos de `Problem` são imutáveis. A API legada continua devolvendo seus
valores ou levantando exceções; `run` compartilha a implementação conferida
e preserva a causa para compatibilidade. Não se usa um inteiro/None como
substituto ambíguo de uma falha. Erros de tipos de `build_checked` antecedem
qualquer invocação da compilação nativa.

Falhas dos comandos nativos da CLI agora usam stderr JSON `omega-result-1`,
`ok: false` e `error: {code, stage, message, details}`, com status de saída 1.
Os formatos de sucesso existentes são preservados. Código que consumia o
texto de erro anterior deve migrar para esse esquema. A saída de candidatos
e os formatos de certificados matemáticos não mudam.

Os códigos distinguem dados/tipos inválidos, arquivos, isolamento ausente,
orçamentos de tempo/saída, saída de processo, sinais observados diretamente,
falhas de prova e erros internos. Diagnósticos estruturados de subprocessos
não incluem argv, stdout ou stderr. As causas em memória continuam contendo
os diagnósticos completos; mensagens de validação local podem conter nomes
e caminhos fornecidos pelo usuário, e não são um mecanismo geral de redação
de dados sensíveis.

O supervisor registra tempo e limite de saída por observação própria. A
existência do processo isolado é conferida pelo canal `--json-status-fd` do
Bubblewrap, cujos descritores não ficam expostos no namespace. Texto de
stderr como `bwrap:`, `prlimit:`, `timeout` ou `MemoryError` é dado não confiável
e não determina a classificação da falha. Sem status de lançamento válido,
o sistema falha fechado, mesmo que o código de saída diga sucesso.

Há um limite observável: Bubblewrap pode converter morte por sinal em saída
`128 + sinal`. Esse código é indistinguível de uma saída explícita com o mesmo
valor e é reportado como `process.exit`. Um status negativo observado pelo
supervisor é `process.signal`; SIGKILL não demonstra esgotamento de memória.
O sistema não inventa essa causa. `memory.exhausted` corresponde a uma falha
de alocação Python efetivamente observada, não a uma inferência sobre OOM no
candidato. Limites detalhados de combustível/profundidade no runtime ainda
encerram o programa com erro; não há exceções recuperáveis na sintaxe Ômega.

No runtime C, `len` aplicado a um número passa a produzir erro, em vez de
retornar zero. `print` confere `puts` e `fflush`, evitando sucesso aparente
quando a escrita falha. Retornos zero documentados de operações concluídas
como `write`/`print` continuam compatíveis; falhas não retornam esse valor.

Publicação opcional de resultados verifica destinos e expõe falhas de I/O.
Não é uma transação de vários arquivos: um erro tardio pode deixar artefatos
parciais, e o chamador deve tratar `Err`. Rollback transacional pertence às
entregas posteriores. Nenhuma falha de prova promove ou aprova um candidato.

Os testes exercitam processos reais em sandbox: timeout, limite de saída,
saída/sinal normalizado, stderr adversarial, privacidade dos descritores,
ausência de status, rejeição Lean/protocolo após execução e falhas de I/O do C.
