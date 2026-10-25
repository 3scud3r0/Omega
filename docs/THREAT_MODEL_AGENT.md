# Fronteiras do agente e da autoedição

Este documento descreve o código-fonte proposto; não é um relatório de auditoria.
A compilação, execução, avaliação adversarial e revisão desta entrega foram
adiadas por solicitação do usuário. Nenhuma propriedade nova foi validada.

## Autoridades

O host confiável configura chaves públicas, papéis, objetivos e capacidades.
O modelo recebe problemas copiados e devolve propostas de dados. Documentos,
saídas de ferramentas e propostas não criam permissões. O verificador e o
promotor têm identidades distintas do proponente. Ativações exigem atestações
vinculadas ao digest exato da proposta. Chaves privadas não ficam no agente.
Essas fronteiras exigem processos/serviços separados em produção: nomes de
atributos Python e callbacks no mesmo processo não são uma barreira de segurança.

## Execução e arquivos

Candidatos nativos usam o sandbox existente com limites do sistema operacional,
seccomp e mounts explícitos. Jobs concorrentes não recebem diretórios graváveis.
Worktrees permitem edição isolada, com o arquivo `.git` protegido. Operações de
arquivo sensíveis têm utilitários ancorados em descritores e `O_NOFOLLOW`.
O backend WASM novo cobre apenas escalares i64 com operações checadas; não afirma
implementar a semântica racional GMP inteira. Parsers de PDF e bancos de dados
executam em workers isolados. Nenhum worker herda credenciais da sessão.

O modelo de C em Lean é uma interface de refinamento condicional. Sua hipótese
`NativeContract.implements` ainda precisa ser demonstrada para a implementação
C/GMP real; não é uma prova já concluída do compilador ou de machine code.
O núcleo tensorial formal novo é finito e intrinsecamente tipado, sem laços
ou divisão; os escopos são expressos nos próprios arquivos Lean.

## Dados e decisões

Fontes externas recebem origem, data e hash. A memória tem retenção e autorização
explícita de reutilização. Replay exige nova conferência do certificado. Separação
de datasets verifica ids e conteúdo; o fornecedor continua responsável por
atribuir a procedência verdadeira. Scores de modelos e estatísticas não são
aprovações de promoção. Remover um componente em uma ablação não autoriza uma
versão sem as suas verificações a entrar no núcleo confiável.

A auditoria encadeada detecta adulteração em relação a uma âncora externa.
Um atacante que reescreve toda a cadeia e a âncora não é impedido só por hashes.
Logs omitem segredos conhecidos e padrões comuns, mas a redação não demonstra
ausência universal de dados sensíveis. Não há publicação ou envio automático
para serviços externos durante importação dos módulos.

## Obrigações pendentes

Revisar isolamento, superfícies de parsing, concorrência, assinaturas, revogação,
rollback, preservação matemática, quotas, redaction e controle de objetivos.
Medir os adaptadores e algoritmos com casos adversariais e dados retidos.
Os módulos de avaliação não constituem uma avaliação externa por existirem.
