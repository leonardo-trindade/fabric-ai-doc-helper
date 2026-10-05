# Changelog

Versões publicadas do Fabric Doc Helper. O app mostra a seção da versão nova ao avisar uma
atualização, então escreva para quem usa: o que muda no dia a dia e se é preciso fazer algo.

Formato: `## vX.Y.Z — AAAA-MM-DD` (X = muda o jeito de trabalhar · Y = novidade · Z = correção).

## v2.2.0 — 2026-10-05
Documento conferido antes da entrega.
- Antes de gerar o Word, o assistente roda uma verificação automática: estrutura fixa das seções,
  nenhum segredo, ID do ambiente ou conta técnica no texto, todo item e tabela citados existem no
  workspace, e o dicionário de dados (Apêndice A) bate com as colunas e tipos reais.
- Cada seção passa a registrar de onde veio o conteúdo (itens lidos e data, inventário, referência
  ou decisão sua). Isso não aparece no documento, mas permite conferir qualquer afirmação.
- No Claude Code, um revisor independente (que só lê) confere as afirmações contra o caderno de
  análise e aponta o que não tem respaldo.
- A mesma verificação vale para o documento revisado por você no Word (estrutura, sigilo, nomes e
  pendências).

## v2.1.2 — 2026-10-05
Correção importante. Atualize assim que o app avisar.
- O login pelo assistente (trocar de conta ou entrar quando não há login) falhava na v2.1.1 antes
  de abrir a janela da Microsoft. Corrigido: a janela abre uma vez só.
- Por dentro: o assistente agora tem testes automáticos que rodam a cada mudança, para evitar que
  problemas como esse cheguem até você.

## v2.1.1 — 2026-10-05
Publica as mudanças anunciadas na v2.1.0 (a tag v2.1.0 saiu com o código da v2.0.1). Veja a v2.1.0.

## v2.1.0 — 2026-10-05
Novo jeito de escolher o workspace, e correções no login e na guarda.
- **Workspace escolhido numa lista:** o app não pede mais o nome do workspace. Na 1ª conversa,
  depois de confirmar a conta, o assistente lista os workspaces dessa conta e você escolhe qual
  documentar. O nome é gravado exatamente como está no Fabric, com o ID; se o workspace for
  renomeado depois, o assistente percebe e pergunta antes de atualizar.
- Um projeto documenta um único workspace; para documentar outro (prod, outro ambiente), crie
  outro projeto no app.
- Workspaces com espaço, `#`, aspas ou vírgula no nome eram bloqueados pela guarda como "não
  autorizados". Agora o nome é lido inteiro, seja qual for.
- Ao trocar de conta, a janela de login da Microsoft abre uma vez só (antes podia abrir duas).
- Se algum token secundário não vier no login, o aviso explica o que isso afeta (o do Azure não é
  usado neste projeto).
- A verificação no início da conversa podia falhar no Windows por causa de acentos, e o assistente
  lia "�" no lugar de letras acentuadas. Corrigido.

## v2.0.1 — 2026-10-03
Ajustes nas instruções do assistente. Nada muda no seu dia a dia.
- Instruções atualizadas para o formato da v2: a pasta de projeto não é repositório, e
  melhorias no assistente são feitas no código-fonte, não na pasta do projeto.
- Em projetos criados pelo app, a primeira conversa completa a entrevista em vez de pulá-la.
- A guarda passa a permitir que o Claude Code leia as próprias skills embutidas (só leitura).

## v2.0.0 — 2026-10-02
Muda o jeito de instalar: o app e as pastas de projeto deixam de ser repositórios Git.

**Quem tem a v1 instalada:** rode o comando de instalação de novo (feche o app antes):
`irm https://raw.githubusercontent.com/leonardo-trindade/fabric-ai-doc-helper/main/instalar.ps1 | iex`.
Seus projetos e configurações são mantidos.

- Não precisa mais de Git: o instalador baixa a versão publicada e só exige o uv.
- Cada projeto é uma pasta comum (sem `.git`) com o assistente, um `LEIA-ME.md` e os seus dados
  em `projeto/`. Não é para ir ao GitHub.
- Ao abrir um projeto, o app atualiza o assistente para a versão instalada, sem mexer nos seus
  dados; se o assistente da pasta tiver sido editado à mão, ele avisa em vez de sobrescrever.
- As 3 versões mais novas ficam guardadas: voltar atrás nas Configurações é imediato.
- A janela do app volta a abrir no tamanho certo.

## v1.0.1 — 2026-10-02
Correção de segurança. Atualize assim que o app avisar.
- O assistente não consegue mais usar o Git para alterar nada (commit, push, tag…) nem o GitHub
  CLI (`gh`) nas pastas de projeto. Isso impede que instruções escondidas em material do cliente
  usem as credenciais do GitHub da máquina. Consultas ao Git continuam funcionando.
- Nada muda no seu dia a dia.

## v1.0.0 — 2026-10-02
Primeira versão publicada.
- App **Fabric Doc Helper**: cria um projeto por cliente/fase (cada um na sua pasta) e abre no
  VS Code ou no Claude Desktop.
- Instalação em um comando (`instalar.ps1`), com atalhos no Menu Iniciar e na Área de Trabalho.
- Conta do Fabric conferida em toda conversa: o assistente confirma a conta na 1ª conversa,
  registra no projeto e, se você entrar em outra conta, pede permissão e refaz o login.
- Atualizações pelo app: aviso de versão nova, atualização em um clique e volta para versões anteriores.
