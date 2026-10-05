"""Instruções do assistente como artefato testado: o que elas citam precisa existir e estar coerente."""
from __future__ import annotations

import json
import re
import subprocess
import sys

import pytest

import guarda
import servicos
from conftest import RAIZ

AGENTS = RAIZ / "AGENTS.md"
FONTE_SKILLS = RAIZ / ".agents" / "skills"
SUBAGENTES = sorted((RAIZ / ".claude" / "agents").glob("*.md"))
INSTRUCOES = [AGENTS, RAIZ / "CLAUDE.md", *sorted(FONTE_SKILLS.glob("*/SKILL.md")), *SUBAGENTES]
FERRAMENTAS_DE_LEITURA = {"Read", "Grep", "Glob"}
ORCAMENTO_AGENTS = 115  # linhas: carregado em toda conversa; reduzir com o tempo, nunca aumentar sem motivo


def skills_da_tabela() -> set[str]:
    texto = AGENTS.read_text(encoding="utf-8")
    secao = texto.split("## Skills", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"^\|[^|]*\|\s*`([a-z0-9-]+)`\s*\|", secao, re.M))


def test_tabela_de_skills_igual_as_pastas():
    pastas = {p.name for p in FONTE_SKILLS.iterdir() if (p / "SKILL.md").is_file()}
    assert skills_da_tabela() == pastas


@pytest.mark.parametrize("skill", sorted(p.parent.name for p in FONTE_SKILLS.glob("*/SKILL.md")))
def test_frontmatter_da_skill(skill):
    texto = (FONTE_SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", texto, re.S)
    assert m, "sem frontmatter"
    campos = dict(linha.split(":", 1) for linha in m.group(1).splitlines() if ":" in linha)
    assert campos.get("name", "").strip() == skill
    assert len(campos.get("description", "").strip()) > 40  # é o que decide quando a skill é usada


def test_copias_das_skills_sincronizadas():
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "sincronizar_skills.py"), "--verificar"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("arquivo", INSTRUCOES, ids=lambda p: p.relative_to(RAIZ).as_posix())
def test_scripts_citados_existem(arquivo):
    citados = set(re.findall(r"scripts/([\w/]+\.(?:py|ps1))", arquivo.read_text(encoding="utf-8")))
    faltando = sorted(c for c in citados if not (RAIZ / "scripts" / c).is_file())
    assert not faltando, f"scripts citados que não existem: {faltando}"


@pytest.mark.parametrize("arquivo", INSTRUCOES, ids=lambda p: p.relative_to(RAIZ).as_posix())
def test_skills_citadas_existem(arquivo):
    citadas = set(re.findall(r"skill `([a-z0-9-]+)`", arquivo.read_text(encoding="utf-8")))
    assert citadas <= skills_da_tabela()


@pytest.mark.parametrize("arquivo", SUBAGENTES, ids=lambda p: p.stem)
def test_subagente_so_le(arquivo):
    """Subagentes revisam; quem escreve é a conversa principal. Sem `tools:` herdariam tudo."""
    m = re.match(r"---\n(.*?)\n---\n", arquivo.read_text(encoding="utf-8"), re.S)
    campos = dict(linha.split(":", 1) for linha in m.group(1).splitlines() if ":" in linha)
    assert campos["name"].strip() == arquivo.stem
    ferramentas = {f.strip() for f in campos["tools"].split(",")}
    assert ferramentas <= FERRAMENTAS_DE_LEITURA, f"{arquivo.stem}: {ferramentas - FERRAMENTAS_DE_LEITURA}"


@pytest.mark.parametrize("arquivo", INSTRUCOES, ids=lambda p: p.relative_to(RAIZ).as_posix())
def test_subagentes_citados_existem(arquivo):
    citados = set(re.findall(r"subagente `([a-z0-9-]+)`", arquivo.read_text(encoding="utf-8")))
    assert citados <= {p.stem for p in SUBAGENTES}


def test_orcamento_do_agents_md():
    linhas = len(AGENTS.read_text(encoding="utf-8").splitlines())
    assert linhas <= ORCAMENTO_AGENTS, f"AGENTS.md tem {linhas} linhas (máximo {ORCAMENTO_AGENTS})"


def test_settings_do_claude_code():
    cfg = json.loads((RAIZ / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert cfg.get("autoMemoryEnabled") is False
    comandos = json.dumps(cfg.get("hooks", {}))
    assert "adaptadores/claude_code.py" in comandos            # guarda antes de cada ferramenta
    assert "adaptadores/claude_code_inicio.py" in comandos     # conferência de conta no início
    matcher = cfg["hooks"]["PreToolUse"][0]["matcher"]
    for ferramenta in ("Read", "Edit", "Write", "Bash", "PowerShell"):
        assert ferramenta in matcher


def test_harness_e_protegidos_existem():
    for nome in servicos.HARNESS_ARQUIVOS + servicos.HARNESS_PASTAS:
        assert (RAIZ / nome).exists(), f"harness: {nome}"
    ausentes_ok = {".fabric-doc-helper.json", "projeto/referencias"}  # só existem em pastas de projeto
    for nome in guarda.PROTEGIDOS:
        assert nome in ausentes_ok or (RAIZ / nome).exists(), f"PROTEGIDOS: {nome}"


def test_ferramentas_de_desenvolvimento_fora_do_harness():
    harness = set(servicos.HARNESS_ARQUIVOS + servicos.HARNESS_PASTAS)
    assert not harness & {"tests", "dev", ".github", "app", "instalar.ps1", "CHANGELOG.md", "README.md"}
    assert {"tests", "dev", ".github"} <= set(guarda.PROTEGIDOS)


CABECALHO = re.compile(r"^## (v\d+\.\d+\.\d+) — \d{4}-\d{2}-\d{2}$")


def test_changelog():
    linhas = [l for l in (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8").splitlines() if l.startswith("## ")]
    assert linhas, "CHANGELOG sem versões"
    versoes = []
    for linha in linhas:
        m = CABECALHO.match(linha)
        assert m, f"cabeçalho fora do formato '## vX.Y.Z — AAAA-MM-DD': {linha!r}"
        versoes.append(tuple(int(x) for x in m.group(1)[1:].split(".")))
    assert versoes == sorted(versoes, reverse=True), "versões fora de ordem (mais nova primeiro)"
    assert len(versoes) == len(set(versoes)), "versão repetida"
