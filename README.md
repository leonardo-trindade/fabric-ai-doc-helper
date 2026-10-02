# fabric-ai-doc-helper

Assistente para gerar a **documentação técnica de arquiteturas Microsoft Fabric** com um
assistente de IA (hoje: Claude Code; preparado para outras ferramentas). O assistente lê o
workspace do cliente em **modo somente leitura** (Fabric CLI), analisa a arquitetura (camadas,
pipelines, notebooks, Materialized Lake Views, orquestração) e gera um documento Word no
**template padrão Bluer**, pronto para revisão humana.

O repositório é **neutro**: não contém dados de cliente. São três coisas separadas:

| | O que é | É repositório Git? |
|---|---|---|
| **Código-fonte** | este repositório: branches, PRs e versões publicadas (tags). Só para quem desenvolve. | Sim |
| **App instalado** | uma versão publicada, baixada pelo instalador para `%LOCALAPPDATA%\Programs\fabric-ai-doc-helper\versoes\<versão>`. | Não |
| **Pasta de projeto** | criada pelo app para cada cliente/fase: o assistente (instruções, skills, guarda, scripts, template) + `projeto/` com os dados do cliente. | Não, e não vai para o GitHub |

---

## 1. Início rápido

**1. Instale o app** (uma vez por computador). Cole no PowerShell:
```powershell
irm https://raw.githubusercontent.com/leonardo-trindade/fabric-ai-doc-helper/main/instalar.ps1 | iex
```
O instalador instala o uv se faltar, baixa a última versão publicada, prepara tudo e cria o
atalho **Fabric Doc Helper** no Menu Iniciar e na Área de Trabalho. Não é preciso Git, Python
nem o Fabric CLI.

**2. Crie um projeto** no app (**Novo projeto**): cliente, projeto/fase, workspace do Fabric,
autor, pasta e onde você vai conversar com o assistente: **VS Code** (com a extensão Claude Code)
ou **Claude Desktop**. Opções não instaladas no PC aparecem em cinza.

**3. Abra e converse.** O app abre o projeto na ferramenta escolhida. Diga *"vamos começar"*.
- **VS Code:** a pasta abre direto; use o painel do Claude Code.
- **Claude Desktop:** o app abre o Claude e copia o caminho da pasta; na aba **Code**, clique
  em *Select folder* e cole (Ctrl+V). (O Claude Desktop ainda não permite abrir uma pasta
  automaticamente.)

Na primeira conversa o assistente mostra a conta do Fabric logada e pergunta se é a do cliente:
- **É:** a conta fica registrada no projeto.
- **Não é / não há login:** com a sua permissão, ele sai da conta atual e abre a janela de
  login da Microsoft; você só escolhe a conta e entra.

Depois disso, **toda conversa e todo acesso ao Fabric conferem a conta**. Se você entrar em
outra conta no meio do caminho (por exemplo, para outro cliente), o assistente percebe, pede
permissão e refaz o login antes de continuar.

### Vários clientes no mesmo computador
- **Uma pasta por projeto.** Dados, análises, documentos e a memória do assistente ficam na
  pasta do projeto; o assistente não lê pastas de outros projetos.
- O login do Fabric CLI é um só para o computador, por isso a conta é **registrada em cada
  projeto e conferida sempre**: abrir o projeto do cliente B logado no cliente A é detectado.
- Projetos do mesmo cliente podem usar a mesma conta.
- Evite pastas no OneDrive: os dados do cliente seriam sincronizados (o app avisa).

### A pasta do projeto
```
C:\Fabric\<Cliente>-<Projeto>\
  LEIA-ME.md                 o que é esta pasta
  AGENTS.md, CLAUDE.md       instruções do assistente   ┐
  .agents\ .claude\          skills, hooks e guarda      │ o "assistente": não edite,
  scripts\ templates\        scripts e template Bluer    │ o app atualiza ao abrir
  pyproject.toml, uv.lock    ambiente Python             ┘
  .fabric-doc-helper.json    versão do assistente nesta pasta (controle do app)
  .venv\                     ambiente Python instalado
  projeto\                   SEUS DADOS: referências, inventário, análise, documentos
```
Ao abrir o projeto, o app atualiza o assistente para a versão instalada, sem tocar em `projeto\`.
Se algum arquivo do assistente tiver sido editado à mão, o app não sobrescreve e avisa.

> Abra o assistente **já na pasta do projeto** (o botão **Abrir** faz isso). Uma conversa
> iniciada em outra pasta não carrega as instruções, o hook de início nem a guarda.

O que o assistente pode perguntar na entrevista (o app já preenche os obrigatórios):
- **Obrigatório:** nome do cliente, nome do projeto, workspace do Fabric a documentar, autor.
- **Opcional:** participantes, workspace legado (comparativo), itens do escopo, renomeações
  de nomenclatura, classificação do documento.

## 2. Arquivos de referência (opcionais)

Coloque em `projeto/referencias/` qualquer material que ajude a documentar. O assistente
pergunta o papel de cada arquivo e quais partes considerar.

| Tipo | Exemplo | O que acrescenta ao documento | Sem ele |
|---|---|---|---|
| Levantamento de requisitos | `.pptx`, `.docx`, `.pdf` | Escopo aprovado, relatórios atendidos, premissas, contexto | Escopo vem da entrevista; lacunas ficam marcadas |
| Mapeamento de tabelas | `.xlsx` | Relatório × tabelas Ouro e apêndice coluna a coluna | Seção de mapeamento simplificada; sem Apêndice B |
| Outros | atas, diagramas exportados, notas | Decisões e contexto adicionais | — |

Dica: em planilhas com abas de uso interno, diga ao assistente quais abas **não** considerar.

## 3. Fluxo de trabalho

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

## 4. Segurança (guarda)

As regras ficam em `scripts/guarda.py` (independente de ferramenta) e são aplicadas em duas camadas:

| Camada | Onde vale | O que bloqueia |
|---|---|---|
| `scripts/fab_ro.py` e scripts do projeto | **qualquer ferramenta** | `fab` de escrita (`rm`, `mv`, `import`, `run`, `set`, `mkdir`, `api` não-GET…), cópias (`export`, `cp`, `-o`), `auth login/logout` direto (o login passa por `scripts/entrar.py`), workspaces fora do projeto e conta logada diferente da registrada |
| Adaptador de hook (`scripts/adaptadores/`) | ferramentas com adaptador (hoje: Claude Code) | Tudo acima, mais: arquivos **fora da pasta do clone** (inclusive memória e rascunhos do assistente de outros projetos) e pastas sensíveis (`~/.config/fab`, `~/.ssh`, `~/.azure`, `.env`); leituras de itens redirecionadas para arquivo; **alteração dos arquivos do assistente** (AGENTS.md, CLAUDE.md, README, `.agents/`, `.claude/`, `scripts/`, `templates/`, dependências) e dos seus originais em `projeto/referencias/`; **Git de escrita** (commit, push, tag, remote, config…) e **qualquer comando `gh`**, também dentro de `cmd /c`, `powershell -Command` e `bash -c` |

O assistente abre a janela de login (`scripts/entrar.py`), mas quem escolhe a conta e entra é você;
ele nunca vê senhas e só faz logout com a sua permissão. O token fica no cache local do `fab`
(fora da pasta do projeto, protegido pela guarda).

**Por que bloquear Git e GitHub?** O assistente lê material do cliente (notebooks, pipelines,
documentos). Um texto malicioso ali poderia tentar fazê-lo usar as credenciais do GitHub desta
máquina para alterar o repositório ou publicar uma versão. Nos projetos ele nunca precisa disso;
o Git fica só para leitura e o `gh` bloqueado. Mantenha o modo manutenção desligado fora do
desenvolvimento: é ele que libera esses comandos.

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

Para permitir que o assistente altere skills, scripts, template ou instruções (e use Git de
escrita e o `gh` para branches, PRs e versões), crie **você mesmo** o arquivo de manutenção e
apague-o ao terminar (o assistente não consegue criá-lo nem apagá-lo):

```powershell
New-Item -ItemType File .agents\MANUTENCAO     # libera alterações no assistente
Remove-Item .agents\MANUTENCAO                 # volta a proteger
```
As demais regras (pasta, somente leitura no Fabric, sem cópias) continuam valendo.

## 5. Ferramentas de IA (agnóstico)

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
   Sem hooks, vale só a primeira camada (seção 4).
4. MCP: configure o `microsoft-learn` no formato da ferramenta.
5. Inclua a ferramenta na tabela acima.

## 6. Versões e atualizações

Quem usa o app recebe só **versões publicadas** (tags `vX.Y.Z`, a partir da v2.0.0), nunca o
que acabou de entrar na `main`.

- **Aviso automático:** ao abrir, o app verifica se há versão nova e mostra as novidades
  (do `CHANGELOG.md`) com o botão **Atualizar agora**.
- **Manual:** Configurações → **Atualizar para a mais nova**.
- **Voltar atrás:** Configurações → escolha a versão → **Instalar versão escolhida**
  (ou `$env:FDH_VERSAO = 'v2.0.0'` antes do comando de instalação). As 3 versões mais novas
  ficam guardadas em `versoes\`, então voltar para uma delas é imediato.
- **Projetos:** cada um recebe a versão em uso ao ser aberto pelo app. A pasta `projeto/`
  nunca é tocada; uma pasta com o assistente editado à mão não é atualizada (o app avisa).
- Depois de atualizar, feche e abra o app pelo atalho (ele passa a apontar para a versão nova).

### Desenvolvimento (testar sem afetar o uso real)
| | Desenvolvimento | Uso real (produção) |
|---|---|---|
| Código | o código-fonte (clone deste repositório), em branches | `%LOCALAPPDATA%\Programs\fabric-ai-doc-helper\versoes\<versão>` (sem Git) |
| Abrir o app | atalho **Fabric Doc Helper (dev)** (criado por `powershell -ExecutionPolicy Bypass -File instalar.ps1` dentro do clone) ou `uv run python app/main.py` | atalho **Fabric Doc Helper** |
| Lista de projetos | `%LOCALAPPDATA%\fabric-ai-doc-helper\dev\app.json` | `%LOCALAPPDATA%\fabric-ai-doc-helper\app.json` |
| Pasta padrão | `C:\Fabric-teste` | `C:\Fabric` |
| Projetos recebem | o assistente da **árvore de trabalho** (inclusive o que não foi commitado; nunca o `.agents\MANUTENCAO`) | a versão instalada |

O app em desenvolvimento mostra a faixa laranja **DESENVOLVIMENTO** e "(dev)" no título.
O Fabric é só leitura, então testar contra um workspace real não altera nada nele; se o teste
trocar a conta logada, o projeto real detecta e pede para refazer o login.

Ciclo: branch → alterar → testar no app (dev) com um projeto em `C:\Fabric-teste` → PR → merge → publicar.

### Publicar uma versão
1. Num branch, acrescente a seção da versão no topo do `CHANGELOG.md` e faça o merge por PR
   (a `main` é protegida: só aceita PR).
2. Na `main` atualizada, crie e envie a tag:
   ```powershell
   git switch main
   git pull
   git tag -a v2.1.0 -m "v2.1.0"
   git push origin v2.1.0
   ```
3. Pronto: os apps instalados avisam a nova versão na próxima abertura. Tags `v*` são
   protegidas: depois de publicadas não podem ser apagadas nem movidas (correção = nova versão).

## 7. Problemas comuns

| Sintoma | Solução |
|---|---|
| `CERTIFICATE_VERIFY_FAILED` / `SSLError` no `fab` | Antivírus/proxy com inspeção HTTPS. Adicione exceções (ex.: Avast → Web Shield → Exceções) para `https://login.microsoftonline.com/*`, `https://api.fabric.microsoft.com/*`, `https://*.dfs.fabric.microsoft.com/*` |
| MCP `microsoft-learn` não conecta | Mesma causa: exceção para `https://learn.microsoft.com/*` e reconecte o MCP na ferramenta (Claude Code: `/mcp`) |
| `Logged In: False` | Login ausente ou expirado: o assistente abre o login (`uv run python scripts/entrar.py`) |
| Trocou de cliente na mesma máquina | Nada a fazer: ao abrir o projeto, o assistente detecta a conta diferente e, com sua permissão, refaz o login |
| Botão do VS Code/Claude Desktop cinza no app | Ferramenta não instalada (o app procura no Menu Iniciar e no registro). Instale e reabra o app |
| VS Code sem a extensão Claude Code | App → Configurações → **Instalar extensão Claude Code** |
| App não abre pelo atalho | Veja `%LOCALAPPDATA%\fabric-ai-doc-helper\app.log` ou rode o instalador de novo (se o app estiver aberto, feche antes) |
| Faixa "Instalação antiga (v1)" no app | Rode o instalador de novo: ele troca a instalação baseada em Git pela atual, mantendo projetos e configurações |
| "Assistente desta pasta foi editado localmente" | Alguém alterou arquivos do assistente na pasta do projeto. Desfaça a alteração (ou apague o arquivo citado) e abra o projeto de novo |
| Sumário do Word desatualizado | `powershell -ExecutionPolicy Bypass -File scripts/finalizar_docx.ps1 projeto/docs/<arquivo>.docx` ou, no Word, botão direito no sumário → Atualizar campo |
| Consumo de capacidade (CU) | Não é acessível pelo Fabric CLI; depende do app *Microsoft Fabric Capacity Metrics* e de permissão na capacidade |

## 8. Estrutura do repositório

```
AGENTS.md                   instruções para qualquer assistente (fonte única)
CLAUDE.md                   importa o AGENTS.md + notas do Claude Code
README.md                   este guia
instalar.ps1                instalador do app (uv, download da versão, ambiente e atalhos)
CHANGELOG.md                novidades de cada versão publicada (mostradas pelo app ao atualizar)
app/                        app Fabric Doc Helper: main.py (interface) e servicos.py (projetos,
                            harness, ferramentas, versões). Não vai para as pastas de projeto
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
  adaptadores/claude_code_inicio.py  hook de início: prepara o ambiente e confere a conta
  entrar.py                 login pelo navegador (opção já escolhida) + conferência da conta
  sincronizar_skills.py     copia .agents/skills para as pastas de cada ferramenta
  verificar_login.py        confere se a conta logada no fab é a do projeto
  inventario.py             inventário de metadados do workspace (sem copiar itens)
  ler_item.py               lê notebooks/pipelines/environments na tela, com segredos mascarados
  _comum.py                 funções compartilhadas
  ler_referencia.py         converte referências (pptx/xlsx/docx/pdf) em texto
  build_doc.py              gera o .docx a partir da especificação
  editar_docx.py            aplica alterações pontuais em um .docx já revisado
  finalizar_docx.ps1        atualiza sumário no Word e exporta PDF
projeto/                    (só nas pastas de projeto; ignorado pelo Git) dados do cliente
```
Vão para cada pasta de projeto (o "harness"): `AGENTS.md`, `CLAUDE.md`, `.mcp.json`,
`pyproject.toml`, `uv.lock`, `.python-version`, `.agents/`, `.claude/`, `scripts/` e `templates/`
(lista em `HARNESS_*` de `app/servicos.py`).
