---
name: fabric-analise
description: Como analisar a arquitetura de um workspace Fabric (medalhão, Lakehouses, notebooks, pipelines, Materialized Lake Views, orquestração, cargas, regras de negócio) a partir do inventário e da leitura de itens, e levantar pontos de atenção. Use depois do inventário e antes de escrever a documentação.
---

# Análise da arquitetura

Fontes: o inventário mais recente (`projeto/inventario/*.json`) e a leitura de itens na tela
com `uv run python scripts/ler_item.py` (skill `fabric-inventario`). Nada é copiado do workspace.
Consulte o MCP `microsoft-learn` antes de afirmar comportamento de produto (MLV, Lakehouse,
pipelines, Direct Lake) de memória. O objetivo é o documento: levante só o que será documentado.

## Roteiro
1. **Inventário**: itens por tipo e organização em pastas (campo `pasta`).
2. **Convenções de nome**: prefixos de camada (ex.: `br_`, `pr_`, `ou_`), de tipo (`pl`, `nb`),
   de tabela (`tf_` fato, `td_` dimensão, `ts_` suporte) e de fonte. Documente o padrão encontrado,
   não um padrão ideal.
3. **Lakehouses** (inventário): schemas, contagem de tabelas, tabelas de sistema
   (`_mlv_system`, `dbo.sys_*`), nomes de arquivos de configuração em Files.
4. **Ingestão (Bronze)**: `ler_item.py --tipo DataPipeline` → fontes (conector, banco/URL),
   modo de carga do destino (`OverwriteSchema` = full, `Upsert` + chaves, `Append`), parâmetros,
   `ForEach` (paralelismo `batchCount`), leitura de config (`Lookup`), colunas técnicas
   adicionadas. Notebooks de ingestão (APIs): endpoint, janelas de data, MERGE, tratamento de erro.
5. **Transformações (Prata/Ouro)**: `ler_item.py` nos notebooks de transformação. Para MLV, cada
   `CREATE [OR REPLACE] MATERIALIZED LAKE VIEW schema.nome AS ...`. Registre por tabela:
   origem(ns), filtros, joins, colunas derivadas e regras (CASE, faixas, datas de corte).
6. **Linhagem**: monte a dependência entre MLVs/tabelas (inclusive Ouro → Ouro) a partir dos
   `FROM`/`JOIN`. Aponte o nó mais crítico (maior número de dependentes).
7. **Orquestração**: pipeline mestre (atividades `InvokePipeline`, `TridentNotebook`,
   `RefreshMaterializedLakeView`, `RefreshSqlEndpoint`), paralelismo, condições de
   dependência (`Succeeded` vs `Completed`), parâmetros e valores padrão.
8. **Ambiente Spark** (`ler_item.py --tipo Environment`): runtime, tamanho de driver/executor,
   alocação dinâmica, configurações relevantes (ex.: `spark.sql.caseSensitive`).
9. **Modelo para consumo**: tabelas Ouro por tipo, granularidade, chaves de relacionamento,
   colunas com cara de atributo/rótulo para ML (ex.: flags de conformidade).
10. **Referências opcionais** (se existirem em `projeto/referencias/`): converta com
    `uv run python scripts/ler_referencia.py` e cruze com o inventário (escopo aprovado,
    mapeamento relatório × tabela). Respeite abas/partes marcadas como internas em `decisoes`.

## Checklist de pontos de atenção
Verifique e registre (com arquivo/atividade de origem) para a seção de pendências:
- [ ] Segredos no código (avisos `***MASCARADO***` do `ler_item.py`): impacto **Alto**;
      recomendar cofre de segredos (ex.: Azure Key Vault). Nunca reproduza valores.
- [ ] Atividade de pipeline invocando o pipeline/notebook errado (IDs × nomes × parâmetros como `prefix`).
- [ ] Nomes de tabela no código diferentes das tabelas publicadas (ex.: prefixo antigo).
- [ ] Refresh/publicação dependente de `Completed` (roda mesmo com falha a montante).
- [ ] Pipelines ou notebooks não orquestrados (órfãos) e cargas `Append` sem chave (duplicidade).
- [ ] Itens configurados (config/parâmetros) sem tabela correspondente, ou o inverso.
- [ ] Datas de corte, códigos de clientes/fornecedores e limites fixos no SQL.
- [ ] Filtros de exclusão lógica ausentes (ex.: `D_E_L_E_T_` no Protheus) ou precedência
      AND/OR sem parênteses em filtros.
- [ ] Rótulos/flags com polaridade inconsistente entre colunas (ex.: 1 = OK numa, 1 = NG noutra).
- [ ] Dependência de fonte citada no escopo mas sem ingestão no workspace.

Antes de colocar um ponto no documento, **confirme com o usuário** quando houver dúvida
(ex.: pode já estar corrigido, ou ser uma decisão). Registre a resposta em `decisoes` do
projeto.yaml — itens que o usuário mandar não documentar não entram.

## Caderno de análise (`projeto/analise/notas.md`)
É a memória do projeto entre conversas: registra **o que foi entendido**, não o conteúdo dos
itens. Escreva/atualize durante a análise; leia-o no início de cada conversa antes de ir ao Fabric.

```markdown
# Caderno de análise — <cliente> · <workspace>
## Visão geral            (camadas, fontes, orquestração — atualizado em AAAA-MM-DD)
## Itens
### `<nome.Tipo>` · lido em AAAA-MM-DD
- Papel: o que faz na arquitetura
- Entradas → saídas: tabelas/itens lidos e gravados (`schema.tabela`)
- Regras relevantes: filtros, cálculos, faixas, datas de corte (texto curto) — onde estão
  (célula/atividade), para poder conferir depois
- Dependências: quem chama / de quem depende
- Pontos de atenção: (se houver)
## Esclarecimentos do usuário   (respostas a dúvidas, com data; decisões de escopo vão para projeto.yaml)
```
Regras: nada de código colado além de trechos curtos essenciais; nunca segredos; sempre a data
de leitura de cada item; itens (`Nome.Tipo`) e tabelas (`schema.tabela`) entre crases, com o nome
exato do inventário. Cada afirmação do documento vai citar estas entradas em `fontes:` — o que
não estiver aqui (ou no inventário, numa referência ou numa decisão do usuário) não entra.

## Quando reler um item do workspace
- Pedido de **texto/estrutura** (reescrever, resumir, reorganizar, mudar tom): use o caderno e o
  documento; **não** acesse o Fabric.
- Pedido que depende de um **fato de um item** (regra, tabela, dependência) e a nota é antiga,
  incompleta ou o usuário diz que mudou: releia **só aquele item** com `scripts/ler_item.py` e
  atualize a nota.
- Workspace pode ter mudado (novo ciclo de documentação): gere novo inventário, compare com o
  anterior e releia apenas itens novos ou apontados pelo usuário.

## Saída da análise
Atualize o caderno, resuma para o usuário em tópicos (arquitetura, números, pontos de atenção,
dúvidas) e só então siga para a skill `fabric-documentacao`.
