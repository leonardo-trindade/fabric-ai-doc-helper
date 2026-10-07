# Changelog

Versões publicadas do Fabric Doc Helper. O app mostra a seção da versão nova ao avisar uma
atualização, então escreva para quem usa: o que muda no dia a dia e se é preciso fazer algo.

Formato: `## vX.Y.Z — AAAA-MM-DD` (X = muda o jeito de trabalhar · Y = novidade · Z = correção).

## v1.0.0 — 2026-10-06
Primeira versão com a numeração atual. A numeração recomeçou: as versões anteriores (v1.x e v2.x,
publicadas enquanto o projeto tomava forma) foram retiradas.

**Quem tem o app instalado:** feche o app e rode o instalador uma vez. Seus projetos e a lista de
projetos são mantidos:
`irm https://raw.githubusercontent.com/leonardo-trindade/fabric-ai-doc-helper/main/instalar.ps1 | iex`.
Sem isso, o app instalado não recebe as próximas atualizações.

O que o Fabric Doc Helper faz:
- **App** para organizar a documentação por cliente: cada projeto é uma pasta própria (sem Git),
  com o assistente pronto e os dados do cliente separados dos demais. Abre o projeto no VS Code ou
  no Claude Desktop (o que não estiver instalado fica indisponível).
- **Tudo numa pasta só:** `C:\Users\<você>\FabricDocHelper`, com `app\`, `Projetos\` e `dados\`.
- **Referências por categoria:** anexe levantamento de requisitos, mapeamento ou outros arquivos
  pelo app; eles complementam a documentação.
- **Documento:** botão que abre a versão mais nova (a revisada por você tem prioridade) e menu com
  as anteriores.
- **Projetos:** marcar como revisado (pronto), remover da lista ou excluir a pasta.
- **Conta do Fabric conferida em toda conversa:** o assistente confirma a conta do cliente, registra
  no projeto e, se você entrar em outra conta, pede permissão antes de refazer o login.
- **Workspace escolhido numa lista** na 1ª conversa (um workspace por projeto).
- **Somente leitura:** o assistente só consulta o Fabric e não copia nada do workspace; uma guarda
  bloqueia comandos que alterariam o ambiente, arquivos fora da pasta e o uso do Git/GitHub.
- **Documento conferido antes da entrega:** estrutura fixa, nenhum segredo ou ID no texto, todo item
  citado existe no workspace e o dicionário de dados bate com as colunas reais; no Claude Code, um
  revisor independente confere as afirmações.
- **Atualizações pelo app:** aviso de versão nova com as novidades, atualização em um clique e volta
  para versões anteriores nas Configurações.
