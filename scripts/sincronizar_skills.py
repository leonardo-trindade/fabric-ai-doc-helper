"""Copia as skills da fonte única (.agents/skills/) para as pastas de cada ferramenta.

Hoje o único destino é o Claude Code (.claude/skills/). Para outra ferramenta que não leia
.agents/skills/ diretamente, acrescente a pasta dela em DESTINOS.

Uso:
    uv run python scripts/sincronizar_skills.py              # copia (exige modo manutenção)
    uv run python scripts/sincronizar_skills.py --verificar  # só confere; código 1 se houver diferença

Cada SKILL.md copiado recebe um aviso logo após o frontmatter. Skills removidas da fonte são
removidas do destino apenas se a cópia tiver esse aviso (skills próprias de uma ferramenta ficam).
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guarda import MANUTENCAO, RAIZ, em_manutencao  # noqa: E402

FONTE = RAIZ / ".agents" / "skills"
DESTINOS = [RAIZ / ".claude" / "skills"]
MARCA = "<!-- Cópia gerada de .agents/skills/"


def com_aviso(texto: str, nome: str) -> str:
    fim = "\r\n" if "\r\n" in texto else "\n"  # mesmo fim de linha do arquivo (o Git no Windows usa CRLF)
    aviso = (f"{MARCA}{nome}/SKILL.md por scripts/sincronizar_skills.py. "
             f"Edite a fonte, não esta cópia. -->{fim}")
    m = re.match(r"---\r?\n.*?\r?\n---\r?\n", texto, flags=re.S)
    if not m:  # sem frontmatter reconhecível: o aviso vai ao final para não quebrá-lo
        return texto.rstrip("\r\n") + fim * 2 + aviso
    return texto[:m.end()] + aviso + texto[m.end():]


def esperado(destino: Path) -> dict[Path, bytes]:
    """Conteúdo que cada arquivo do destino deve ter."""
    out: dict[Path, bytes] = {}
    for skill in sorted(p for p in FONTE.iterdir() if (p / "SKILL.md").exists()):
        for arq in skill.rglob("*"):
            if not arq.is_file():
                continue
            dados = arq.read_bytes()
            if arq.name == "SKILL.md" and arq.parent == skill:
                dados = com_aviso(dados.decode("utf-8"), skill.name).encode("utf-8")
            out[destino / arq.relative_to(FONTE)] = dados
    return out


def lf(dados: bytes) -> bytes:
    """Compara ignorando CRLF × LF: o Git converte o fim de linha no checkout e isso não é diferença."""
    return dados.replace(b"\r\n", b"\n")


def geradas(destino: Path) -> list[Path]:
    if not destino.exists():
        return []
    return [p for p in destino.iterdir()
            if (p / "SKILL.md").exists() and MARCA in (p / "SKILL.md").read_text(encoding="utf-8")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verificar", action="store_true")
    a = ap.parse_args()
    if not FONTE.exists():
        sys.exit(f"Fonte não encontrada: {FONTE}")
    if not a.verificar and not em_manutencao():
        sys.exit(f"Modo manutenção desligado. O usuário deve criar manualmente `{MANUTENCAO}`.")

    diferencas = 0
    for destino in DESTINOS:
        alvo = esperado(destino)
        nomes_fonte = {p.relative_to(destino).parts[0] for p in alvo}
        sobras = [p for p in geradas(destino) if p.name not in nomes_fonte]
        mudados = [p for p, dados in alvo.items() if not p.exists() or lf(p.read_bytes()) != lf(dados)]
        extras = [p for skill in geradas(destino) if skill.name in nomes_fonte
                  for p in skill.rglob("*") if p.is_file() and p not in alvo]
        rel = lambda p: p.relative_to(RAIZ).as_posix()  # noqa: E731
        for p in mudados:
            print(f"{'diferente' if a.verificar else 'copiado'}: {rel(p)}")
        for p in [*sobras, *extras]:
            print(f"{'sobrando' if a.verificar else 'removido'}: {rel(p)}")
        diferencas += len(mudados) + len(sobras) + len(extras)
        if a.verificar:
            continue
        for p in sobras:
            shutil.rmtree(p)
        for p in extras:
            p.unlink()
        for p in mudados:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(alvo[p])
    if a.verificar and diferencas:
        sys.exit(1)
    print("Skills sincronizadas." if diferencas else "Nada a fazer: destinos já iguais à fonte.")


if __name__ == "__main__":
    main()
