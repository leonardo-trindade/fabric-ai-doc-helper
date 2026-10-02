"""Inventário (somente metadados) do workspace alvo — nenhum arquivo do workspace é copiado.

Uso:
    uv run python scripts/inventario.py                    # itens, pastas, tabelas por schema
    uv run python scripts/inventario.py --colunas ouro     # + colunas das tabelas dos schemas indicados
                                                           #   (vírgula para vários: ouro,prata)

Grava projeto/inventario/<AAAA-MM-DD_HHMM>.json (apenas nomes, tipos, IDs e colunas) e
imprime um resumo. Conteúdo de notebooks/pipelines NÃO entra aqui: leia sob demanda com
scripts/ler_item.py.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import PROJETO, checar_login, config, fab, fab_api  # noqa: E402

PARALELO = 6
PROFUNDIDADE_FILES = 2


def linhas(txt: str) -> list[str]:
    return [l.strip() for l in txt.splitlines() if l.strip()]


def colunas_tabela(caminho: str) -> list[dict]:
    txt = fab("table", "schema", caminho, check=False)
    cols, cab = [], False
    for l in txt.splitlines():
        if re.match(r"^\s*name\s+type\s+nullable", l):
            cab = True
            continue
        if cab and l.strip() and not re.match(r"^\s*-+\s*$", l):
            p = re.split(r"\s{2,}", l.strip())
            if len(p) >= 2:
                cols.append({"nome": p[0], "tipo": p[1]})
    return cols


def listar_files(remoto: str, nivel: int = 1) -> list[str]:
    out = []
    for l in fab("ls", remoto, "-l", check=False).splitlines():
        p = re.split(r"\s{2,}", l.strip())
        if len(p) < 3 or p[0].startswith(("permissions", "---")):
            continue
        nome, tipo = p[-2], p[-1].lower()
        if tipo in {"folder", "directory"}:
            out.append(f"{nome}/")
            if nivel < PROFUNDIDADE_FILES:
                out += [f"{nome}/{x}" for x in listar_files(f"{remoto}/{nome}", nivel + 1)]
        else:
            out.append(nome)
    return out


def lakehouse(ws: str, lh: str, schemas_colunas: set[str]) -> dict:
    base = f"{ws}.Workspace/{lh}.Lakehouse"
    info: dict = {"nome": lh, "schemas": {}, "files": []}
    for nome in linhas(fab("ls", f"{base}/Tables", check=False)):
        filhos = [f for f in linhas(fab("ls", f"{base}/Tables/{nome}", check=False)) if not f.endswith(".gz")]
        if filhos:  # Lakehouse com schemas
            info["schemas"][nome] = {t: None for t in filhos}
        else:
            info["schemas"].setdefault("(sem schema)", {})[nome] = None
    tarefas = [(s, t) for s, ts in info["schemas"].items() for t in ts if s.lower() in schemas_colunas]
    with ThreadPoolExecutor(PARALELO) as ex:
        res = ex.map(lambda st: colunas_tabela(
            f"{base}/Tables/{st[1]}" if st[0] == "(sem schema)" else f"{base}/Tables/{st[0]}/{st[1]}"), tarefas)
        for (s, t), cols in zip(tarefas, res):
            info["schemas"][s][t] = cols
    info["files"] = listar_files(f"{base}/Files")
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--colunas", default="", help="schemas cujas tabelas terão as colunas lidas (ex.: ouro,prata)")
    a = ap.parse_args()
    cfg = config()
    ws = cfg["workspace_alvo"].strip()
    login = checar_login(cfg)
    if "true" not in fab("exists", f"{ws}.Workspace", check=False).lower():
        sys.exit(f"Workspace '{ws}' não encontrado para a conta logada.")
    inicio = dt.datetime.now()

    ws_id = fab("get", f"{ws}.Workspace", "-q", "id").strip()
    props = fab_api(f"workspaces/{ws_id}")
    itens = fab_api(f"workspaces/{ws_id}/items").get("value", [])
    pastas = fab_api(f"workspaces/{ws_id}/folders").get("value", [])
    por_id = {p["id"]: p for p in pastas}

    def caminho_pasta(fid):
        partes = []
        while fid and fid in por_id:
            partes.insert(0, por_id[fid]["displayName"])
            fid = por_id[fid].get("parentFolderId")
        return "/".join(partes)

    for i in itens:
        i["pasta"] = caminho_pasta(i.get("folderId"))

    schemas_colunas = {s.strip().lower() for s in a.colunas.split(",") if s.strip()}
    lhs = [lakehouse(ws, i["displayName"], schemas_colunas) for i in itens if i.get("type") == "Lakehouse"]

    inv = {
        "workspace": ws, "workspace_id": ws_id, "capacity_id": props.get("capacityId"),
        "gerado_em": inicio.isoformat(timespec="seconds"), **login,
        "itens": [{k: i.get(k) for k in ("displayName", "type", "id", "pasta", "description")} for i in itens],
        "lakehouses": lhs,
    }
    destino = PROJETO / "inventario" / f"{inicio:%Y-%m-%d_%H%M}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")

    tipos: dict[str, int] = {}
    for i in itens:
        tipos[i["type"]] = tipos.get(i["type"], 0) + 1
    print(f"Workspace: {ws}  ({(dt.datetime.now() - inicio).seconds}s)")
    print("Itens por tipo: " + ", ".join(f"{t}={n}" for t, n in sorted(tipos.items())))
    for l in lhs:
        resumo = ", ".join(f"{s}={len(t)}" for s, t in l["schemas"].items())
        print(f"Lakehouse {l['nome']}: tabelas por schema: {resumo}; arquivos em Files: {len(l['files'])}")
    if schemas_colunas:
        print(f"Colunas lidas para os schemas: {', '.join(sorted(schemas_colunas))}")
    print(f"Salvo em {destino.relative_to(PROJETO.parent)}")


if __name__ == "__main__":
    main()
