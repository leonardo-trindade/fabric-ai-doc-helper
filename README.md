# fabric-ai-doc-helper

Assistente para gerar a **documentação técnica de arquiteturas Microsoft Fabric** com um
assistente de IA (hoje: Claude Code; preparado para outras ferramentas). O assistente lê o
workspace do cliente em **modo somente leitura** (Fabric CLI), analisa a arquitetura (camadas,
pipelines, notebooks, Materialized Lake Views, orquestração) e gera um documento Word no
**template padrão Bluer**, pronto para revisão humana.

O repositório é **neutro**: não contém dados de cliente. Cada projeto usa um clone próprio,
e tudo do cliente fica na pasta `projeto/`, que nunca vai para o Git.

---

## 1. Pré-requisitos (uma vez por máquina)

| Ferramenta | Para quê | Instalação |
|---|---|---|
| Git | clonar o repositório | `winget install Git.Git` |
| uv | Python 3.12 + dependências (inclui o `fab`) | `winget install astral-sh.uv` |
| VS Code + extensão Claude Code | trabalhar com o assistente (outras ferramentas: seção 6) | [code.visualstudio.com](https://code.visualstudio.com) |
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

No assistente, basta começar a conversa (ex.: *"vamos documentar o projeto"*).
Na primeira vez, o assistente faz uma **entrevista** rápida:

- **Obrigatório:** nome do cliente, nome do projeto, workspace do Fabric a documentar, autor.
- **Opcional:** participantes, workspace legado (comparativo), itens do escopo, renomeações
  de nomenclatura, classificação do documento.

As respostas ficam salvas em `projeto/projeto.yaml`. Você não precisa editar esse arquivo;
se algo mudar, é só avisar o assistente.

**Conta do Fabric:** o login do `fab` vale para o usuário do Windows, não para a pasta — a
máquina pode continuar logada no cliente anterior. No início de toda conversa o assistente mostra
a conta logada e pergunta se é a do cliente. Se não for, ele faz o logout e pede que você rode
`uv run fab auth login` com a conta certa. A conta confirmada fica registrada no projeto e, dali
em diante, os scripts param sozinhos se detectarem outra conta.

## 3. Arquivos de referência (opcionais)

Coloque em `projeto/referencias/` qualquer material que ajude a documentar. O assistente
pergunta o papel de cada arquivo e quais partes considerar.

| Tipo | Exemplo | O que acrescenta ao documento | Sem ele |
|---|---|---|---|
| Levantamento de requisitos | `.pptx`, `.docx`, `.pdf` | Escopo aprovado, relatórios atendidos, premissas, contexto | Escopo vem da entrevista; lacunas ficam marcadas |
| Mapeamento de tabelas | `.xlsx` | Relatório × tabelas Ouro e apêndice coluna a coluna | Seção de mapeamento simplificada; sem Apêndice B |
| Outros | atas, diagramas exportados, notas | Decisões e contexto adicionais | — |

Dica: em planilhas com abas de uso interno, diga ao assistente quais abas **não** considerar.

## 4. Fluxo de trabalho

| Passo | Peça ao assistente | O que acontece |
|---|---|---|
| 1 | *"levante o workspace"* | Inventário de metadados em `projeto/inventario/` (itens, tabelas, colunas da camada de consumo). Notebooks e pipelines são lidos **na tela**, sem cópia; segredos aparecem mascarados |
| 2 | *"analise a arquitetura"* | Resumo da arquitetura e pontos de atenção; o assistente confirma dúvidas com você |
| 3 | *"gere a documentação"* | Documento em `projeto/docs/DT_<cliente>_<projeto>_v0.1.docx` |
| 4 | Você | Revisão humana no Word e upload manual no Drive |

- O documento gerado **nunca é sobrescrito**; novas versões geram novos arquivos.
- O assistente mantém um **caderno de análise** (`projeto/analise/notas.md`) com o que entendeu de
  cada item. Em conversas futuras ele parte do caderno e só relê no Fabric o item que precisar.
- Depois da sua revisão, salve o .docx revisado em `projeto/docs/revisado/`. Ele passa a ser a
  fonte da verdade: novos pedidos de alteração são aplicados **nele** (gerando uma nova versão),
  preservando suas edições.
- Marcações em **dourado** `{{...}}` no documento são pendências para você completar.

## 5. Segurança (guarda)

As regras ficam em `scripts/guarda.py` (independente de ferramenta) e são aplicadas em duas camadas:

| Camada | Onde vale | O que bloqueia |
|---|---|---|
| `scripts/fab_ro.py` e scripts do projeto | **qualquer ferramenta** | `fab` de escrita (`rm`, `mv`, `import`, `run`, `set`, `mkdir`, `api` não-GET…), cópias (`export`, `cp`, `-o`), `auth login` pelo assistente, workspaces fora do projeto e conta logada diferente da registrada |
| Adaptador de hook (`scripts/adaptadores/`) | ferramentas com adaptador (hoje: Claude Code) | Tudo acima, mais: arquivos **fora da pasta do clone** e pastas sensíveis (`~/.config/fab`, `~/.ssh`, `~/.azure`, `.env`); leituras de itens redirecionadas para arquivo; **alteração dos arquivos do assistente** (AGENTS.md, CLAUDE.md, README, `.agents/`, `.claude/`, `scripts/`, `templates/`, dependências) e dos seus originais em `projeto/referencias/` |

O login no Fabric é sempre feito por você; o assistente nunca vê senhas. O token fica no cache
local do `fab` (fora da pasta do projeto, protegido pela guarda).

> **Limites.** Para comandos de terminal a guarda analisa o texto do comando: ela evita erros e
> desvios do modelo, mas não é um isolamento de sistema operacional. Em ferramentas **sem
> adaptador**, só a primeira camada é automática; o restante depende das instruções do
> `AGENTS.md`. Para isolamento total, use um sandbox (ex.: Claude Code no WSL2 com `/sandbox`)
> ou um container.
>
> Uma conta com papel **Viewer** no workspace não resolve: a API de definição de itens
> (`getDefinition`) exige permissão de leitura **e escrita**, então notebooks e pipelines não
> poderiam ser lidos. Por isso a proteção de somente leitura fica na guarda.

### Modo manutenção (evoluir o próprio assistente)

Para permitir que o assistente altere skills, scripts, template ou instruções, crie **você mesmo**
o arquivo de manutenção e apague-o ao terminar (o assistente não consegue criá-lo nem apagá-lo):

```powershell
New-Item -ItemType File .agents\MANUTENCAO     # libera alterações no assistente
Remove-Item .agents\MANUTENCAO                 # volta a proteger
```
As demais regras (pasta, somente leitura no Fabric, sem cópias) continuam valendo.

## 6. Ferramentas de IA (agnóstico)

| Peça | Fonte única (agnóstica) | Claude Code |
|---|---|---|
| Instruções | `AGENTS.md` | `CLAUDE.md` importa o `AGENTS.md` (`@AGENTS.md`) + notas próprias |
| Skills | `.agents/skills/` (formato aberto Agent Skills) | `.claude/skills/`: cópia gerada por `scripts/sincronizar_skills.py` |
| Guarda | `scripts/guarda.py` + `scripts/fab_ro.py` | hook em `.claude/settings.json` → `scripts/adaptadores/claude_code.py` |
| MCP `microsoft-learn` | `https://learn.microsoft.com/api/mcp` (HTTP) | `.mcp.json` |

**Alterar uma skill:** edite em `.agents/skills/<nome>/SKILL.md` (modo manutenção) e rode
`uv run python scripts/sincronizar_skills.py`. Para conferir se as cópias estão em dia:
`uv run python scripts/sincronizar_skills.py --verificar`.

**Incluir outra ferramenta:**
1. Instruções: a maioria lê `AGENTS.md` nativamente; se não, crie o arquivo dela apontando para ele.
2. Skills: se ela lê `.agents/skills/`, nada a fazer; senão, acrescente a pasta dela em
   `DESTINOS` de `scripts/sincronizar_skills.py`.
3. Guarda: se ela tiver hooks antes da execução de ferramentas, crie
   `scripts/adaptadores/<ferramenta>.py` no molde de `claude_code.py` (ou chame direto
   `python scripts/guarda.py comando|arquivo ...`, que responde com código 2 para bloquear).
   Sem hooks, vale só a primeira camada (seção 5).
4. MCP: configure o `microsoft-learn` no formato da ferramenta.
5. Inclua a ferramenta na tabela acima.

## 7. Atualizar o assistente

```powershell
git pull        # novas skills, scripts e ajustes do template
uv sync         # se o pyproject.toml mudou
```
A pasta `projeto/` não é afetada.

## 8. Problemas comuns

| Sintoma | Solução |
|---|---|
| `CERTIFICATE_VERIFY_FAILED` / `SSLError` no `fab` | Antivírus/proxy com inspeção HTTPS. Adicione exceções (ex.: Avast → Web Shield → Exceções) para `https://login.microsoftonline.com/*`, `https://api.fabric.microsoft.com/*`, `https://*.dfs.fabric.microsoft.com/*` |
| MCP `microsoft-learn` não conecta | Mesma causa: exceção para `https://learn.microsoft.com/*` e reconecte o MCP na ferramenta (Claude Code: `/mcp`) |
| `Logged In: False` | `uv run fab auth login` |
| Trocou de cliente na mesma máquina | `uv run fab auth logout` e `uv run fab auth login` com a conta do novo cliente (o login do `fab` é por usuário do Windows, não por pasta) |
| Sumário do Word desatualizado | `powershell -ExecutionPolicy Bypass -File scripts/finalizar_docx.ps1 projeto/docs/<arquivo>.docx` ou, no Word, botão direito no sumário → Atualizar campo |
| Consumo de capacidade (CU) | Não é acessível pelo Fabric CLI; depende do app *Microsoft Fabric Capacity Metrics* e de permissão na capacidade |

## 9. Estrutura do repositório

```
AGENTS.md                   instruções para qualquer assistente (fonte única)
CLAUDE.md                   importa o AGENTS.md + notas do Claude Code
README.md                   este guia
pyproject.toml / uv.lock    dependências (Python 3.12, ms-fabric-cli…)
.mcp.json                   MCP microsoft-learn para o Claude Code
.agents/
  skills/                   fonte das skills: iniciar-projeto, fabric-cli, fabric-inventario,
                            fabric-analise, fabric-documentacao
.claude/
  settings.json             hook de guarda e permissões do Claude Code
  skills/                   cópia gerada de .agents/skills (não editar)
templates/
  template-bluer.docx       identidade visual (fixa)
  estrutura-documento.yaml  estrutura fixa das seções do documento
scripts/
  guarda.py                 regras da guarda (pasta, fab somente leitura, sem cópias, arquivos protegidos)
  fab_ro.py                 executa o fab só com comandos de leitura permitidos (qualquer ferramenta)
  adaptadores/claude_code.py  hook do Claude Code → guarda.py
  sincronizar_skills.py     copia .agents/skills para as pastas de cada ferramenta
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
