"""Lê a definição de itens do workspace alvo SEM gravar nada (saída só na tela, segredos mascarados).

Uso:
    uv run python scripts/ler_item.py "mn_pl.DataPipeline" "ou_nb_vendas.Notebook"
    uv run python scripts/ler_item.py --tipo Notebook              # todos os notebooks
    uv run python scripts/ler_item.py --tipo DataPipeline --bruto  # JSON completo em vez do resumo

Formato de saída por tipo:
  Notebook      células (markdown resumido, código completo)
  DataPipeline  parâmetros e árvore de atividades (dependências, fonte/destino, alvos invocados)
  Environment   configuração Spark e bibliotecas
  outros        partes da definição em texto (truncadas em --max caracteres)
Agendamentos do item são exibidos quando existirem. Leituras rodam em paralelo.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import config, checar_login, fab, fab_api, json_da_saida, mascarar  # noqa: E402

PARALELO = 6
NOMES: dict[str, str] = {}  # id -> "nome.Tipo" (para resolver notebookId/pipelineId)


def ler(ws: str, item: str) -> dict:
    txt = fab("get", f"{ws}.Workspace/{item}", "-q", "{definition: definition, schedules: schedules}", "-f", check=False)
    try:
        return json_da_saida(txt)
    except json.JSONDecodeError:
        return {"erro": txt.strip()[:500]}


def notebook(payload: dict) -> list[str]:
    out = []
    for c in payload.get("cells", []):
        src = "".join(c.get("source", []))
        if not src.strip():
            continue
        if c.get("cell_type") == "markdown":
            out.append("  # " + " | ".join(l.strip("# *") for l in src.splitlines() if l.strip())[:160])
        else:
            out.append("  ```\n" + "\n".join("  " + l for l in src.splitlines()) + "\n  ```")
    return out


def _resumo_tp(tp: dict) -> str:
    partes = []
    for k in ("notebookId", "pipelineId"):
        if k in tp:
            partes.append(f"{k}={NOMES.get(tp[k], tp[k])}")
    if "parameters" in tp:
        partes.append(f"parâmetros={json.dumps(tp['parameters'], ensure_ascii=False)[:300]}")
    for k in ("items", "batchCount", "isSequential", "waitOnCompletion", "condition", "expression"):
        if k in tp:
            partes.append(f"{k}={json.dumps(tp[k], ensure_ascii=False)[:200]}")
    src, snk = tp.get("source"), tp.get("sink")
    if src:
        ds = src.get("datasetSettings", {}).get("typeProperties", {})
        partes.append(f"fonte={src.get('type')} {json.dumps(ds, ensure_ascii=False)[:250]}")
        if src.get("sqlReaderQuery"):
            partes.append(f"query={json.dumps(src['sqlReaderQuery'], ensure_ascii=False)[:300]}")
        extra = [c.get("name") for c in src.get("additionalColumns", [])]
        if extra:
            partes.append(f"colunas_extra={extra}")
    if snk:
        ds = snk.get("datasetSettings", {}).get("typeProperties", {})
        modo = snk.get("tableActionOption") or snk.get("writeBehavior")
        chaves = snk.get("upsertSettings", {}).get("keys")
        partes.append(f"destino={snk.get('type')} modo={modo} chaves={json.dumps(chaves, ensure_ascii=False)} {json.dumps(ds, ensure_ascii=False)[:250]}")
    ds = tp.get("datasetSettings", {}).get("typeProperties", {})
    if ds and not src:
        partes.append(f"dataset={json.dumps(ds, ensure_ascii=False)[:250]}")
    return "; ".join(partes)


def pipeline(payload: dict) -> list[str]:
    props = payload.get("properties", payload)
    out = []
    if props.get("parameters"):
        out.append("  parâmetros: " + json.dumps(props["parameters"], ensure_ascii=False))

    def walk(acts, nivel=1):
        for a in acts:
            dep = [f"{d['activity']}:{'/'.join(d.get('dependencyConditions', []))}" for d in a.get("dependsOn", [])]
            tp = a.get("typeProperties", {})
            out.append(f"{'  ' * nivel}- {a['name']} [{a['type']}]" + (f" após {dep}" if dep else ""))
            det = _resumo_tp(tp)
            if det:
                out.append(f"{'  ' * nivel}    {det}")
            for k in ("activities", "ifTrueActivities", "ifFalseActivities"):
                if k in tp:
                    out.append(f"{'  ' * nivel}  {k}:")
                    walk(tp[k], nivel + 2)
    walk(props.get("activities", []))
    return out


def formatar(item: str, dados: dict, bruto: bool, maximo: int) -> str:
    if "erro" in dados:
        return f"\n===== {item}\n  ERRO: {dados['erro']}"
    tipo = item.rsplit(".", 1)[-1]
    linhas = [f"\n===== {item}"]
    for parte in (dados.get("definition") or {}).get("parts", []):
        caminho, payload = parte.get("path", ""), parte.get("payload")
        if caminho == ".platform":
            continue
        if bruto or not isinstance(payload, dict):
            txt = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=1)
            linhas.append(f"--- {caminho}\n{txt[:maximo]}" + (" …(truncado)" if len(txt) > maximo else ""))
        elif tipo == "Notebook" and caminho.endswith(".ipynb"):
            linhas += notebook(payload)
        elif tipo == "DataPipeline" and caminho.endswith(".json"):
            linhas += pipeline(payload)
        else:
            txt = json.dumps(payload, ensure_ascii=False, indent=1)
            linhas.append(f"--- {caminho}\n{txt[:maximo]}" + (" …(truncado)" if len(txt) > maximo else ""))
    ag = [s for s in (dados.get("schedules") or []) if isinstance(s, dict)]
    for s in ag:
        cfg = s.get("configuration", {})
        linhas.append(f"  agendamento: ativo={s.get('enabled')} tipo={cfg.get('type')} "
                      f"horários={cfg.get('times') or cfg.get('interval')} dias={cfg.get('weekdays', '')} fuso={cfg.get('localTimeZoneId')}")
    return "\n".join(linhas)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("itens", nargs="*", help='itens no formato "nome.Tipo"')
    ap.add_argument("--tipo", help="lê todos os itens deste tipo (ex.: Notebook, DataPipeline, Environment)")
    ap.add_argument("--bruto", action="store_true", help="mostra o JSON completo das partes")
    ap.add_argument("--max", type=int, default=6000, help="limite de caracteres por parte não resumida")
    a = ap.parse_args()
    cfg = config()
    ws = cfg["workspace_alvo"].strip()
    checar_login(cfg)

    ws_id = fab("get", f"{ws}.Workspace", "-q", "id").strip()
    todos = fab_api(f"workspaces/{ws_id}/items").get("value", [])
    NOMES.update({i["id"]: f"{i['displayName']}.{i['type']}" for i in todos})
    itens = list(a.itens)
    if a.tipo:
        itens += [f"{i['displayName']}.{i['type']}" for i in todos if i["type"].lower() == a.tipo.lower()]
    if not itens:
        sys.exit("Informe itens (\"nome.Tipo\") ou --tipo.")

    ocorrencias = 0
    with ThreadPoolExecutor(PARALELO) as ex:
        for item, dados in zip(itens, ex.map(lambda it: ler(ws, it), itens)):
            texto, n = mascarar(formatar(item, dados, a.bruto, a.max))
            ocorrencias += n
            print(texto)
    if ocorrencias:
        print(f"\n[aviso] {ocorrencias} segredo(s) mascarado(s) na saída: registrar como ponto de atenção "
              "(credenciais em texto no código), sem reproduzir valores.")


if __name__ == "__main__":
    main()
