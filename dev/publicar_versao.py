"""Publica uma versão do Fabric Doc Helper (tag vX.Y.Z) com as conferências que faltaram antes.

Uso, no código-fonte (repositório fabric-ai-doc-helper), com o modo manutenção ligado:
    uv run python dev/publicar_versao.py v1.1.0             # cria e envia a tag
    uv run python dev/publicar_versao.py v1.1.0 --release   # e cria a página de release no GitHub

Antes de criar a tag, confere:
  - código-fonte em modo manutenção (o script faz `git push`; nunca roda numa pasta de projeto);
  - árvore sem alterações e o commit local igual ao `origin/main` (a tag vai no commit publicado);
  - versão no formato vX.Y.Z, maior que a última tag e ainda não usada;
  - seção `## vX.Y.Z — AAAA-MM-DD` no topo do CHANGELOG do `origin/main` (o app mostra essas notas).
Mostra o commit e as notas e pede confirmação. A tag não pode ser movida depois (regra do GitHub).
Fica fora das pastas de projeto (não faz parte do harness).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
for _fluxo in (sys.stdout, sys.stderr):  # acentos corretos quando a saída vai para outro programa
    if _fluxo is not None and hasattr(_fluxo, "reconfigure"):
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
SEMVER = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
CABECALHO = re.compile(r"^## (v\d+\.\d+\.\d+) — \d{4}-\d{2}-\d{2}\s*$", re.M)


class Recusa(Exception):
    """Conferência que impede a publicação (a mensagem diz o que corrigir)."""


def git(*args: str, raiz: Path = RAIZ, checar: bool = True) -> str:
    r = subprocess.run(["git", "-c", "http.sslBackend=schannel", *args], cwd=raiz, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if checar and r.returncode != 0:
        raise Recusa(f"git {' '.join(args)}: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def versao(tag: str) -> tuple[int, int, int]:
    m = SEMVER.match(tag)
    if not m:
        raise Recusa(f"Versão '{tag}' fora do formato vX.Y.Z.")
    return tuple(int(x) for x in m.groups())  # type: ignore[return-value]


def notas(changelog: str, tag: str) -> str:
    m = re.search(rf"(?ms)^## {re.escape(tag)} — .*?(?=^## |\Z)", changelog)
    return m.group(0).strip() if m else ""


def conferir(tag: str, raiz: Path = RAIZ, buscar: bool = True) -> tuple[str, str]:
    """Faz todas as conferências; devolve (commit do origin/main, notas da versão)."""
    if (raiz / ".fabric-doc-helper.json").exists():
        raise Recusa("Esta é uma pasta de projeto. Versões são publicadas só no código-fonte.")
    if not (raiz / ".agents" / "MANUTENCAO").exists():
        raise Recusa("Modo manutenção desligado. Crie manualmente `.agents/MANUTENCAO` para publicar.")
    nova = versao(tag)
    if buscar:
        git("fetch", "--quiet", "--tags", "origin", raiz=raiz)
    if git("status", "--porcelain", "--untracked-files=no", raiz=raiz):
        raise Recusa("Há alterações não commitadas. Publique só o que está na main do GitHub.")
    local, remoto = git("rev-parse", "HEAD", raiz=raiz), git("rev-parse", "origin/main", raiz=raiz)
    if local != remoto:
        raise Recusa(f"O commit local ({local[:7]}) não é o da origin/main ({remoto[:7]}). "
                     "Rode `git switch main` e `git pull` antes de publicar.")
    tags = [t for t in git("tag", "-l", "v*", raiz=raiz).split() if SEMVER.match(t)]
    if tag in tags:
        raise Recusa(f"A versão {tag} já existe. Tags publicadas não podem ser movidas: use a próxima versão.")
    if tags and nova <= max(versao(t) for t in tags):
        raise Recusa(f"{tag} não é maior que a última versão publicada ({max(tags, key=versao)}).")
    changelog = git("show", "origin/main:CHANGELOG.md", raiz=raiz)
    topo = CABECALHO.search(changelog)
    if not topo or topo.group(1) != tag:
        raise Recusa(f"O topo do CHANGELOG.md da main não é a seção `## {tag} — AAAA-MM-DD` "
                     f"(encontrado: {topo.group(1) if topo else 'nenhuma'}). Inclua as notas num PR antes.")
    return remoto, notas(changelog, tag)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("versao", help="ex.: v1.1.0")
    ap.add_argument("--release", action="store_true", help="também cria a página de release no GitHub")
    ap.add_argument("--sim", action="store_true", help="não pergunta (uso em automação)")
    a = ap.parse_args()
    try:
        commit, texto = conferir(a.versao)
    except Recusa as e:
        sys.exit(f"NÃO PUBLICADO: {e}")

    print(f"Versão : {a.versao}\nCommit : {git('log', '-1', '--format=%h %s', commit)}\n\n{texto}\n")
    if not a.sim and input("Publicar? Digite a versão para confirmar: ").strip() != a.versao:
        sys.exit("Cancelado.")
    git("tag", "-a", a.versao, "-m", a.versao, commit)
    git("push", "origin", a.versao)
    print(f"Tag {a.versao} publicada no commit {commit[:7]}.")
    if a.release:
        corpo = texto.split("\n", 1)[1].strip() if "\n" in texto else texto
        r = subprocess.run(["gh", "release", "create", a.versao, "--verify-tag", "--latest",
                            "--title", a.versao, "--notes", corpo], cwd=RAIZ)
        if r.returncode != 0:
            sys.exit("A tag foi publicada, mas a página de release não. Crie pelo GitHub ou rode o gh de novo.")
    print("Pronto: os apps instalados avisam a nova versão na próxima abertura.")


if __name__ == "__main__":
    main()
