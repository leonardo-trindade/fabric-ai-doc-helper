"""Lista os workspaces da conta do projeto e grava o escolhido pelo usuário no projeto.yaml.

Quem escolhe o workspace é sempre o usuário; este script só evita digitação: grava o nome exato
que vem do Fabric e o ID (para perceber renomeações). Um projeto documenta um único workspace;
para documentar outro (prod, outro ambiente…), cria-se um novo projeto no app.

Uso:
    uv run python scripts/escolher_workspace.py --listar [--filtro texto]
    uv run python scripts/escolher_workspace.py --definir <nº da lista | nome | ID>
    uv run python scripts/escolher_workspace.py --extra <nº | nome | ID>   # só leitura, para comparação
                                                                         # (SÓ com "sim" explícito do usuário)
    uv run python scripts/escolher_workspace.py --conferir                # o workspace ainda existe? foi renomeado?
    uv run python scripts/escolher_workspace.py --renomeado               # atualiza o nome (mesmo ID), após confirmação

Só lê nomes e IDs (GET /workspaces). Exige a conta do Fabric já registrada no projeto.
Códigos de saída: 0 ok · 1 erro de uso/dados · 6 renomeado (--conferir) · 7 não encontrado (--conferir).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import PROJETO, checar_login, config, fab_api  # noqa: E402

YAML = PROJETO / "projeto.yaml"


def listar() -> list[dict]:
    """Workspaces visíveis para a conta, ordenados por nome (a numeração da lista é estável)."""
    itens, endpoint = [], "workspaces"
    for _ in range(50):  # paginação da API do Fabric (continuationToken)
        dados = fab_api(endpoint)
        itens += dados.get("value", [])
        token = dados.get("continuationToken")
        if not token:
            break
        endpoint = f"workspaces?continuationToken={token}"
    return sorted(itens, key=lambda w: (w.get("type") == "Personal", w.get("displayName", "").lower()))


def resolver(escolha: str, wss: list[dict]) -> dict:
    e = escolha.strip()
    if e.isdigit() and 1 <= int(e) <= len(wss):
        return wss[int(e) - 1]
    for w in wss:
        if e.lower() in {w.get("id", "").lower(), w.get("displayName", "").lower()}:
            return w
    sys.exit(f"'{escolha}' não está na lista de workspaces desta conta. Rode --listar e use o número.")


def gravar(chave: str, valor: str) -> None:
    """Grava `chave: "valor"` no projeto.yaml (aspas em formato JSON, que é YAML válido)."""
    txt = YAML.read_text(encoding="utf-8")
    linha = f"{chave}: {json.dumps(valor, ensure_ascii=False)}"
    if re.search(rf"(?m)^{chave}:", txt):
        txt = re.sub(rf"(?m)^{chave}:.*$", lambda _: linha, txt)
    elif chave == "workspace_id" and re.search(r"(?m)^workspace_alvo:", txt):  # logo abaixo do nome
        txt = re.sub(r"(?m)^(workspace_alvo:.*)$", lambda m: f"{m.group(1)}\n{linha}", txt, count=1)
    else:
        txt = txt.rstrip() + f"\n{linha}\n"
    YAML.write_text(txt, encoding="utf-8")


def gravar_extras(nomes: list[str]) -> None:
    txt = YAML.read_text(encoding="utf-8")
    linha = "workspaces_leitura_extra: [" + ", ".join(json.dumps(n, ensure_ascii=False) for n in nomes) + "]"
    if re.search(r"(?m)^workspaces_leitura_extra:", txt):
        txt = re.sub(r"(?m)^workspaces_leitura_extra:.*$", lambda _: linha, txt)
    else:
        txt = txt.rstrip() + f"\n{linha}\n"
    YAML.write_text(txt, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--listar", action="store_true")
    g.add_argument("--definir", metavar="ESCOLHA")
    g.add_argument("--extra", metavar="ESCOLHA")
    g.add_argument("--conferir", action="store_true")
    g.add_argument("--renomeado", action="store_true")
    ap.add_argument("--filtro", default="", help="com --listar: só nomes que contêm este texto")
    a = ap.parse_args()

    cfg = config(exigir_workspace=False)
    if not (cfg.get("conta_fabric") or "").strip():
        sys.exit("A conta do Fabric ainda não foi registrada no projeto. Faça o Passo 1 da skill "
                 "iniciar-projeto antes de listar workspaces.")
    checar_login(cfg)
    alvo = (cfg.get("workspace_alvo") or "").strip()
    alvo_id = (cfg.get("workspace_id") or "").strip()
    wss = listar()
    if not wss:
        sys.exit("Nenhum workspace visível para esta conta (ou falha ao consultar a API do Fabric).")

    if a.listar:
        termo = a.filtro.lower()
        print(f"Workspaces da conta {cfg.get('conta_fabric')} ({len(wss)}):")
        for i, w in enumerate(wss, 1):
            if termo and termo not in w.get("displayName", "").lower():
                continue
            marca = "  <- workspace do projeto" if alvo and w.get("displayName", "").lower() == alvo.lower() else ""
            pessoal = " (pessoal)" if w.get("type") == "Personal" else ""
            cap = "" if w.get("capacityId") else " (sem capacidade)"
            print(f"{i:3}. {w.get('displayName')}{pessoal}{cap}  [id {w.get('id')}]{marca}")
        if not alvo:
            print("\nPeça ao usuário para escolher e grave com: uv run python scripts/escolher_workspace.py --definir <nº>")
        return

    if a.definir:
        w = resolver(a.definir, wss)
        nome = w["displayName"]
        if alvo and alvo.lower() != nome.lower():
            sys.exit(f"Este projeto já documenta o workspace '{alvo}'. Um projeto documenta um único workspace: "
                     "para documentar outro, crie um novo projeto no app Fabric Doc Helper.")
        gravar("workspace_alvo", nome)
        gravar("workspace_id", w["id"])
        print(f"Workspace do projeto: {nome} [id {w['id']}]. Gravado em projeto/projeto.yaml.")
        return

    if a.extra:
        if not alvo:
            sys.exit("Escolha primeiro o workspace do projeto (--definir).")
        w = resolver(a.extra, wss)
        if w["displayName"].lower() == alvo.lower():
            sys.exit("Esse já é o workspace do projeto.")
        extras = [x for x in (cfg.get("workspaces_leitura_extra") or []) if str(x).strip()]
        if w["displayName"].lower() not in {str(x).lower() for x in extras}:
            extras.append(w["displayName"])
        gravar_extras(extras)
        print(f"Liberado só para leitura (comparação): {w['displayName']}. Extras: {', '.join(extras)}")
        return

    # --conferir / --renomeado
    if not alvo:
        sys.exit("Workspace ainda não escolhido (--listar e --definir).")
    por_id = {w["id"].lower(): w for w in wss}
    atual = por_id.get(alvo_id.lower()) if alvo_id else None
    if atual is None:
        achado = next((w for w in wss if w["displayName"].lower() == alvo.lower()), None)
        if achado:
            gravar("workspace_id", achado["id"])  # projeto antigo, sem ID: completa
            print(f"OK: workspace '{alvo}' encontrado [id {achado['id']}].")
            return
        print(f"NÃO ENCONTRADO: o workspace '{alvo}' não aparece para esta conta (apagado, sem acesso ou outra conta).")
        sys.exit(7)
    if atual["displayName"].lower() == alvo.lower():
        print(f"OK: workspace '{alvo}' [id {alvo_id}].")
        return
    if a.renomeado:
        gravar("workspace_alvo", atual["displayName"])
        print(f"Nome atualizado: '{alvo}' -> '{atual['displayName']}' (mesmo workspace, id {alvo_id}).")
        return
    print(f"RENOMEADO: o workspace do projeto (id {alvo_id}) agora se chama '{atual['displayName']}' "
          f"(antes '{alvo}'). Confirme com o usuário e rode --renomeado.")
    sys.exit(6)


if __name__ == "__main__":
    main()
