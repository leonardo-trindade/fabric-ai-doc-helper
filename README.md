# fabric-ai-doc-helper

Assistente para gerar a **documentação técnica de arquiteturas Microsoft Fabric** com o
Claude Code. O Claude lê o workspace do cliente em **modo somente leitura** (Fabric CLI),
analisa a arquitetura (camadas, pipelines, notebooks, Materialized Lake Views, orquestração)
e gera um documento Word no **template padrão Bluer**, pronto para revisão humana.

O repositório é **neutro**: não contém dados de cliente. Cada projeto usa um clone próprio,
e tudo do cliente fica na pasta `projeto/`, que nunca vai para o Git.

---

## 1. Pré-requisitos (uma vez por máquina)

| Ferramenta | Para quê | Instalação |
|---|---|---|
| Git | clonar o repositório | `winget install Git.Git` |
| uv | Python 3.12 + dependências (inclui o `fab`) | `winget install astral-sh.uv` |
| VS Code + extensão Claude Code | trabalhar com o Claude | [code.visualstudio.com](https://code.visualstudio.com) |
| Microsoft Word *(recomendado)* | atualizar sumário e exportar PDF | — |

Não é preciso instalar Python nem o Fabric CLI manualmente: o `uv` cuida disso.

## 2. Começar um projeto

```powershell
git clone <url-do-repositorio> "C:\Trabalho\<Cliente>-<Projeto>"
cd "C:\Trabalho\<Cliente>-<Projeto>"
uv sync                      # instala Python 3.12, Fabric CLI e bibliotecas (versões travadas)
uv run fab auth login        # login MANUAL com a conta fornecida pelo cliente (abre o navegador)
code .                       # abre no VS Code
```

No Claude Code, basta começar a conversa (ex.: *"vamos documentar o projeto"*).
Na primeira vez, o Claude faz uma **entrevista** rápida:

- **Obrigatório:** nome do cliente, nome do projeto, workspace do Fabric a documentar, autor.
- **Opcional:** participantes, workspace legado (comparativo), itens do escopo, renomeações
  de nomenclatura, classificação do documento.

As respostas ficam salvas em `projeto/projeto.yaml`. Você não precisa editar esse arquivo;
se algo mudar, é só avisar o Claude.

**Conta do Fabric:** o login do `fab` vale para o usuário do Windows, não para a pasta — a
máquina pode continuar logada no cliente anterior. No início de toda conversa o Claude mostra a
conta logada e pergunta se é a do cliente. Se não for, ele faz o logout e pede que você rode
`uv run fab auth login` com a conta certa. A conta confirmada fica registrada no projeto e, dali
em diante, os scripts param sozinhos se detectarem outra conta.

## 3. Arquivos de referência (opcionais)

Coloque em `projeto/referencias/` qualquer material que ajude a documentar. O Claude
pergunta o papel de cada arquivo e quais partes considerar.

| Tipo | Exemplo | O que acrescenta ao documento | Sem ele |
|---|---|---|---|
| Levantamento de requisitos | `.pptx`, `.docx`, `.pdf` | Escopo aprovado, relatórios atendidos, premissas, contexto | Escopo vem da entrevista; lacunas ficam marcadas |
| Mapeamento de tabelas | `.xlsx` | Relatório × tabelas Ouro e apêndice coluna a coluna | Seção de mapeamento simplificada; sem Apêndice B |
| Outros | atas, diagramas exportados, notas | Decisões e contexto adicionais | — |

Dica: em planilhas com abas de uso interno, diga ao Claude quais abas **não** considerar.

## 4. Fluxo de trabalho

| Passo | Peça ao Claude | O que acontece |
|---|---|---|
| 1 | *"levante o workspace"* | Inventário de metadados em `projeto/inventario/` (itens, tabelas, colunas da camada de consumo). Notebooks e pipelines são lidos **na tela**, sem cópia; segredos aparecem mascarados |
| 2 | *"analise a arquitetura"* | Resumo da arquitetura e pontos de atenção; o Claude confirma dúvidas com você |
| 3 | *"gere a documentação"* | Documento em `projeto/docs/DT_<cliente>_<projeto>_v0.1.docx` |
| 4 | Você | Revisão humana no Word e upload manual no Drive |

- O documento gerado **nunca é sobrescrito**; novas versões geram novos arquivos.
- O Claude mantém um **caderno de análise** (`projeto/analise/notas.md`) com o que entendeu de cada
  item. Em conversas futuras ele parte do caderno e só relê no Fabric o item que precisar.
- Depois da sua revisão, salve o .docx revisado em `projeto/docs/revisado/`. Ele passa a ser a
  fonte da verdade: novos pedidos de alteração são aplicados **nele** (gerando uma nova versão),
  preservando suas edições.
- Marcações em **dourado** `{{...}}` no documento são pendências para você completar.

## 5. Segurança (guarda)

O repositório traz um hook (`.claude/hooks/guard.py`) que bloqueia automaticamente:

- leitura/escrita de arquivos **fora da pasta do clone** (e de pastas sensíveis como `~/.config/fab`, `~/.ssh`, `.env`);
- comandos `fab` de **escrita** (`rm`, `mv`, `import`, `run`, `set`, `mkdir`, `api` não-GET…);
- **cópias do workspace**: `fab export`, `fab cp`, `fab get -o` e leituras de itens redirecionadas para arquivo;
- **alteração dos arquivos do assistente** (CLAUDE.md, README, `.claude/`, `scripts/`, `templates/`,
  dependências) e dos seus originais em `projeto/referencias/`;
- acesso a **workspaces diferentes** do informado na entrevista.

O login no Fabric é sempre feito por você; o Claude nunca vê senhas. O token fica no cache
local do `fab` (fora da pasta do projeto, protegido pela guarda).

> Limite: para comandos de terminal a guarda analisa o texto do comando; ela evita erros e
> desvios do modelo, mas não é um isolamento de sistema operacional. Para isolamento total,
> use o Claude Code no WSL2 com o sandbox (`/sandbox`) ou um container.

### Modo manutenção (evoluir o próprio assistente)

Para permitir que o Claude altere skills, scripts, template ou instruções, crie **você mesmo**
o arquivo de manutenção e apague-o ao terminar (o Claude não consegue criá-lo):

```powershell
New-Item -ItemType File .claude\MANUTENCAO     # libera alterações no assistente
Remove-Item .claude\MANUTENCAO                 # volta a proteger
```
As demais regras (pasta, somente leitura no Fabric, sem cópias) continuam valendo.

## 6. Atualizar o assistente

```powershell
git pull        # novas skills, scripts e ajustes do template
uv sync         # se o pyproject.toml mudou
```
A pasta `projeto/` não é afetada.

## 7. Problemas comuns

| Sintoma | Solução |
|---|---|
| `CERTIFICATE_VERIFY_FAILED` / `SSLError` no `fab` | Antivírus/proxy com inspeção HTTPS. Adicione exceções (ex.: Avast → Web Shield → Exceções) para `https://login.microsoftonline.com/*`, `https://api.fabric.microsoft.com/*`, `https://*.dfs.fabric.microsoft.com/*` |
| MCP `microsoft-learn` não conecta (`/mcp`) | Mesma causa: exceção para `https://learn.microsoft.com/*` e reconecte em `/mcp` |
| `Logged In: False` | `uv run fab auth login` |
| Trocou de cliente na mesma máquina | `uv run fab auth logout` e `uv run fab auth login` com a conta do novo cliente (o login do `fab` é por usuário do Windows, não por pasta) |
| Sumário do Word desatualizado | `powershell -ExecutionPolicy Bypass -File scripts/finalizar_docx.ps1 projeto/docs/<arquivo>.docx` ou, no Word, botão direito no sumário → Atualizar campo |
| Consumo de capacidade (CU) | Não é acessível pelo Fabric CLI; depende do app *Microsoft Fabric Capacity Metrics* e de permissão na capacidade |

## 8. Estrutura do repositório

```
CLAUDE.md                   instruções para o modelo
README.md                   este guia
pyproject.toml / uv.lock    dependências (Python 3.12, ms-fabric-cli…)
.mcp.json                   MCP microsoft-learn (documentação oficial)
.claude/
  settings.json             hook de guarda e permissões
  hooks/guard.py            guarda: pasta, fab somente leitura, sem cópias, arquivos protegidos
  skills/                   iniciar-projeto, fabric-cli, fabric-inventario, fabric-analise, fabric-documentacao
templates/
  template-bluer.docx       identidade visual (fixa)
  estrutura-documento.yaml  estrutura fixa das seções do documento
scripts/
  verificar_login.py        confere se a conta logada no fab é a do projeto
  inventario.py             inventário de metadados do workspace (sem copiar itens)
  ler_item.py               lê notebooks/pipelines/environments na tela, com segredos mascarados
  _comum.py                 funções compartilhadas
  ler_referencia.py         converte referências (pptx/xlsx/docx/pdf) em texto
  build_doc.py              gera o .docx a partir da especificação
  editar_docx.py            aplica alterações pontuais em um .docx já revisado
  finalizar_docx.ps1        atualiza sumário no Word e exporta PDF
projeto/                    (criado no uso; ignorado pelo Git) dados do cliente
```
