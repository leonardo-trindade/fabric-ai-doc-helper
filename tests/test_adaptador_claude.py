"""Adaptador do Claude Code: áreas próprias só desta pasta; skills embutidas só para leitura."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from conftest import RAIZ

ADAPTADOR = RAIZ / "scripts" / "adaptadores" / "claude_code.py"
SLUG = re.sub(r"[^A-Za-z0-9]", "-", str(RAIZ))  # mesma regra do adaptador
TMP = Path(tempfile.gettempdir())
TMP_LONGO = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "Temp"
SKILL = Path("bundled-skills", "2.1.286", "x", "claude-api", "shared", "prompt-audit.md")


def liberado(ferramenta: str, entrada: dict) -> bool:
    evento = {"tool_name": ferramenta, "tool_input": entrada, "cwd": str(RAIZ)}
    r = subprocess.run([sys.executable, str(ADAPTADOR)], input=json.dumps(evento), text=True, capture_output=True)
    return r.returncode == 0


@pytest.mark.parametrize("ferramenta, caminho, esperado", [
    ("Read", TMP / "claude" / SLUG / "s" / "a.txt", True),
    ("Read", Path.home() / ".claude" / "projects" / SLUG / "memory" / "MEMORY.md", True),
    ("Read", Path.home() / ".claude" / "projects" / "C--Fabric-OutroCliente" / "memory" / "MEMORY.md", False),
    ("Read", TMP / "claude" / "C--Fabric-OutroCliente" / "a.txt", False),
    ("Read", TMP / "claude" / SKILL, True),
    ("Grep", TMP / "claude" / "bundled-skills", True),
    ("Write", TMP / "claude" / SKILL, False),
    ("Edit", TMP / "claude" / SKILL, False),
    ("Read", TMP / "claude" / "bundled-skills-falso" / "a.txt", False),
    ("Read", Path.home() / ".ssh" / "id_rsa", False),
    ("Read", RAIZ / "AGENTS.md", True),
])
def test_arquivos(ferramenta, caminho, esperado):
    chave = "path" if ferramenta == "Grep" else "file_path"
    assert liberado(ferramenta, {chave: str(caminho)}) is esperado


@pytest.mark.skipif(not TMP_LONGO.exists(), reason="caminho longo do %TEMP% só existe no Windows")
def test_skill_embutida_pelo_caminho_longo():
    assert liberado("Read", {"file_path": str(TMP_LONGO / "claude" / SKILL)})


def test_terminal_nao_le_skill_embutida():
    assert not liberado("Bash", {"command": f"cat {TMP / 'claude' / SKILL}"})
