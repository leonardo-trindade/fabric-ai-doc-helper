---
name: fabric-documentacao
description: Escreve e gera o documento técnico (.docx) da arquitetura Fabric no template fixo (visual Bluer e estrutura de seções fixa), usando o inventário, a leitura dos itens, o projeto.yaml e referências opcionais. Use quando o usuário pedir a documentação, uma nova versão dela, ou o que mudou desde a última versão.
---

# Documentação técnica (template fixo)

## Fluxo
1. Garanta: `projeto/projeto.yaml` (skill `iniciar-projeto`), inventário recente
   (skill `fabric-inventario`) e análise feita (skill `fabric-analise`).
2. Copie `templates/estrutura-documento.yaml` para
   `projeto/docs/DT_<cliente>_<projeto>_v<versão>.yaml` (sem espaços/acentos no nome).
3. Preencha a especificação seção a seção (formato dos blocos no cabeçalho do template).
4. Gere: `uv run python scripts/build_doc.py projeto/docs/<arquivo>.yaml`
5. Finalize (sumário e, se pedido, PDF):
   `powershell -ExecutionPolicy Bypass -File scripts/finalizar_docx.ps1 projeto/docs/<arquivo>.docx [-Pdf]`
6. Revise o resultado renderizado (PDF → imagens) antes de entregar: sumário, tabelas
   cortadas, títulos órfãos, marcadores `{{...}}` restantes.
7. Entregue: caminho do .docx, lista de pendências `{{...}}` e decisões que o usuário precisa tomar.

## Estrutura fixa
Seções 1–15 e Apêndice A **sempre**, nesta ordem (títulos iguais aos do template).
Nunca remova uma seção: sem conteúdo, escreva uma frase dizendo por quê.
Não copie a estrutura de seções de documentos de referência: eles orientam conteúdo, não estrutura.

| # | Seção | Fonte principal | Referência opcional que enriquece |
|---|---|---|---|
| 1 | Controle do Documento | projeto.yaml | — |
| 2 | Visão Geral | projeto.yaml + inventário | Levantamento (contexto/objetivo) |
| 3 | Escopo Técnico | projeto.yaml (`escopo`) | **Levantamento** (itens aprovados, premissas) |
| 4 | Arquitetura da Solução | inventário + itens | — |
| 5 | Fontes de Dados e Ingestão (Camada Bronze) | pipelines/notebooks | — |
| 6 | Camada Prata | notebooks/MLVs | — |
| 7 | Camada Ouro – Modelo Analítico | notebooks/MLVs + inventário | — |
| 8 | Materialized Lake Views (MLV) | notebooks + MCP microsoft-learn | — |
| 9 | Orquestração e Operação | pipelines (atividades, agendamentos) | — |
| 10 | Consumo: Power BI e Machine Learning | inventário + análise | **Mapeamento** (relatório × tabelas) |
| 11 | Implantação, Governança e Manutenção | análise + boas práticas | — |
| 12 | Ganhos de Performance e Redução de Capacidade | análise | Métricas fornecidas pelo usuário |
| 13 | Pontos de Atenção e Pendências Técnicas | análise (checklist) | — |
| 14 | Entrega para o Time de BI | análise | Mapeamento |
| 15 | Aprovação | fixo | — |
| A | Dicionário de Dados da Camada Ouro | inventário (`--colunas`) | — |
| B | Mapeamento de Colunas (somente com planilha) | **Mapeamento** | — |

## Referências opcionais
- Use apenas as declaradas em `projeto.yaml → referencias` (ou confirmadas pelo usuário).
- Converta com `uv run python scripts/ler_referencia.py [arquivo] [--abas ...]` e leia o `.md` gerado.
- Sem a referência: escreva a seção com o que o inventário/projeto.yaml permite e marque lacunas
  com `{{...}}`. Nunca invente o que viria dela (itens de escopo, mapeamentos, métricas).
- Em "Documentos de referência" (seção 1), liste só o que foi efetivamente usado.

## Regras de escrita
- Português (pt-BR), técnico e objetivo, frases curtas; público: equipe técnica do cliente
  e times de BI/ML. Tom do template Bluer: direto, sem marketing.
- Nomes técnicos (tabelas, colunas, itens, parâmetros) entre crases.
- Aplique as renomeações de `nomenclatura` exatamente onde o usuário indicou.
- Respeite `decisoes` (ex.: bugs já corrigidos não entram; fontes descartadas são omitidas).
- Nunca inclua segredos, tokens, senhas ou e-mails de contas técnicas; segredos detectados
  aparecem só como "credenciais em texto no código de <item>".
- Números e afirmações de desempenho só com dado medido/fornecido; sem dado, explique como medir.
- `{{...}}` = pendência visível (dourado). Use-o em vez de supor.

## Pedidos de alteração: qual caminho usar
| Situação | Caminho |
|---|---|
| Existe versão revisada pelo usuário em `projeto/docs/revisado/` (ou ele indicar um .docx revisado) | **Editar o .docx revisado** (abaixo). Nunca regenerar a partir da especificação — as edições humanas seriam perdidas. |
| Ainda não houve revisão humana | Editar a especificação `.yaml`, salvar como nova versão e gerar com `build_doc.py`. |
| O pedido depende de um fato do workspace | Consultar o caderno de análise; reler só o item necessário (skill `fabric-analise`). |

### Editar o .docx revisado
1. Localize os trechos: `uv run python scripts/editar_docx.py --listar <docx revisado> --filtro "<texto>"`.
2. Escreva `projeto/docs/alteracoes_v<nova versão>.yaml` com `origem`, `saida` (novo arquivo em
   `projeto/docs/`) e as operações: `substituir`, `substituir_paragrafo`, `inserir_apos`,
   `remover_paragrafo`, `historico` (sempre inclua uma linha de histórico).
3. Aplique: `uv run python scripts/editar_docx.py projeto/docs/alteracoes_v<versão>.yaml`.
   Se um trecho for ambíguo, nada é gravado: torne o `contendo` mais específico.
4. Finalize com `finalizar_docx.ps1` e revise a renderização das partes alteradas.
5. Para mudanças grandes (nova seção inteira, reestruturação), explique ao usuário que o caminho
   seguro é ele aplicar no Word, ou combine com ele regenerar a partir da especificação ciente de
   que as edições manuais precisarão ser refeitas.

## Versões e revisões humanas
- O gerador nunca sobrescreve. Nova versão = novo arquivo (`..._v0.2.yaml` → `..._v0.2.docx`)
  com linha nova no histórico de versões.
- Depois que o usuário revisar o .docx manualmente, o .docx revisado é a fonte da verdade:
  não regenere por cima. Peça ao usuário para salvá-lo em `projeto/docs/revisado/` e aplique
  alterações nele com `editar_docx.py`. Para atualizações do workspace, gere novo inventário,
  compare com o anterior, releia só os itens novos/alterados e aplique no revisado.
