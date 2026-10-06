"""App: anexar arquivos de referência por categoria (cópia em projeto/referencias/ + registro no projeto.yaml)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import servicos as s

YAML_INICIAL = (
    "# Gerado pelo app Fabric Doc Helper.\n"
    'cliente: "C"\n'
    'workspace_alvo: "WS"          # escolhido na 1ª conversa\n'
    "referencias: []\n"
    "decisoes:\n"
    '  - "não documentar X"\n'
)


@pytest.fixture
def pasta(tmp_path) -> Path:
    (tmp_path / "projeto" / "referencias").mkdir(parents=True)
    (tmp_path / "projeto" / "projeto.yaml").write_text(YAML_INICIAL, encoding="utf-8")
    return tmp_path


def entradas(pasta: Path) -> list[dict]:
    return yaml.safe_load((pasta / "projeto" / "projeto.yaml").read_text(encoding="utf-8"))["referencias"]


def test_anexar_copia_e_registra(pasta, tmp_path_factory):
    origem = tmp_path_factory.mktemp("origem") / "Levantamento Cliente.pptx"
    origem.write_bytes(b"pptx")
    ref = s.anexar_referencia(pasta, origem.name, origem, "levantamento")
    assert ref.arquivo == pasta / "projeto" / "referencias" / "Levantamento Cliente.pptx"
    assert ref.arquivo.read_bytes() == b"pptx" and origem.exists()  # o original fica onde estava
    s.anexar_referencia(pasta, "mapa.xlsx", b"xlsx", "mapeamento")
    assert entradas(pasta) == [{"arquivo": "referencias/Levantamento Cliente.pptx", "tipo": "levantamento"},
                               {"arquivo": "referencias/mapa.xlsx", "tipo": "mapeamento"}]
    txt = (pasta / "projeto" / "projeto.yaml").read_text(encoding="utf-8")
    assert "# escolhido na 1ª conversa" in txt and '"não documentar X"' in txt  # resto do arquivo intacto
    assert [(r.arquivo.name, r.categoria) for r in s.referencias(pasta)] == [
        ("Levantamento Cliente.pptx", "Levantamento de requisitos"), ("mapa.xlsx", "Mapeamento")]


def test_nome_repetido_nao_sobrescreve(pasta):
    s.anexar_referencia(pasta, "ata.docx", b"1", "outro")
    r2 = s.anexar_referencia(pasta, r"C:\qualquer\ata.docx", b"2", "outro")
    assert r2.arquivo.name == "ata (2).docx"
    assert (pasta / "projeto" / "referencias" / "ata.docx").read_bytes() == b"1"


def test_categoria_invalida_e_nome_invalido(pasta):
    with pytest.raises(ValueError):
        s.anexar_referencia(pasta, "a.xlsx", b"", "requisitos")
    with pytest.raises(ValueError):
        s.anexar_referencia(pasta, "~$a.xlsx", b"", "outro")


def test_arquivo_colocado_a_mao_fica_sem_categoria(pasta):
    (pasta / "projeto" / "referencias" / "solto.pdf").write_bytes(b"")
    (pasta / "projeto" / "referencias" / "_texto").mkdir()  # gerado pelo ler_referencia.py: não lista
    [r] = s.referencias(pasta)
    assert r.tipo == "" and r.categoria == "Sem categoria"
    s.definir_categoria(pasta, r, "mapeamento")
    assert entradas(pasta) == [{"arquivo": "referencias/solto.pdf", "tipo": "mapeamento"}]


def test_mudar_categoria_preserva_campos_do_assistente(pasta):
    (pasta / "projeto" / "projeto.yaml").write_text(YAML_INICIAL.replace(
        "referencias: []\n",
        'referencias:\n  - {arquivo: "referencias/m.xlsx", tipo: "outro", abas: ["Tabelas"], uso: "mapa"}\n'),
        encoding="utf-8")
    (pasta / "projeto" / "referencias" / "m.xlsx").write_bytes(b"")
    [r] = s.referencias(pasta)
    s.definir_categoria(pasta, r, "mapeamento")
    assert entradas(pasta) == [{"arquivo": "referencias/m.xlsx", "tipo": "mapeamento", "abas": ["Tabelas"],
                                "uso": "mapa"}]


def test_remover(pasta):
    ref = s.anexar_referencia(pasta, "a.xlsx", b"", "mapeamento")
    s.anexar_referencia(pasta, "b.pdf", b"", "outro")
    texto = pasta / "projeto" / "referencias" / "_texto" / "a.xlsx.md"
    texto.parent.mkdir()
    texto.write_text("x")
    s.remover_referencia(pasta, ref)
    assert not ref.arquivo.exists() and not texto.exists()
    assert entradas(pasta) == [{"arquivo": "referencias/b.pdf", "tipo": "outro"}]
    s.remover_referencia(pasta, s.referencias(pasta)[0])
    assert entradas(pasta) == [] and "referencias: []" in (pasta / "projeto" / "projeto.yaml").read_text("utf-8")


def test_yaml_sem_bloco_referencias(pasta):
    (pasta / "projeto" / "projeto.yaml").write_text('cliente: "C"\n', encoding="utf-8")
    s.anexar_referencia(pasta, "a.csv", b"", "outro")
    assert entradas(pasta) == [{"arquivo": "referencias/a.csv", "tipo": "outro"}]
