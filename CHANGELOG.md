# Changelog

Versões publicadas do Fabric Doc Helper. O app mostra a seção da versão nova ao avisar uma
atualização, então escreva para quem usa: o que muda no dia a dia e se é preciso fazer algo.

Formato: `## vX.Y.Z — AAAA-MM-DD` (X = muda o jeito de trabalhar · Y = novidade · Z = correção).

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
