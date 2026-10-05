"""App: versões do documento (botão principal + menu de versões anteriores) e tema salvo."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

import marca
import servicos as s


def docx(pasta: Path, nome: str, revisado=False, idade_dias=0) -> Path:
    destino = pasta / "projeto" / "docs" / ("revisado" if revisado else "")
    destino.mkdir(parents=True, exist_ok=True)
    arq = destino / nome
    arq.write_bytes(b"")
    t = time.time() - idade_dias * 86400
    os.utime(arq, (t, t))
    return arq


def test_ordem_das_versoes(tmp_path):
    docx(tmp_path, "DT_cli_v0.1.docx", idade_dias=5)
    docx(tmp_path, "DT_cli_v0.10.docx", idade_dias=4)  # 0.10 > 0.9 (número, não texto)
    docx(tmp_path, "DT_cli_v0.9.docx", idade_dias=1)
    docx(tmp_path, "DT_cli_v0.10.docx", revisado=True, idade_dias=3)
    docx(tmp_path, "~$DT_cli_v0.10.docx")  # arquivo temporário do Word
    docx(tmp_path, "rascunho.docx", idade_dias=10)
    rotulos = [d.rotulo for d in s.documentos(tmp_path)]
    assert rotulos == ["v0.10 · revisado", "v0.10", "v0.9", "v0.1", "rascunho"]


def test_sem_documentos(tmp_path):
    assert s.documentos(tmp_path) == []
    (tmp_path / "projeto" / "docs").mkdir(parents=True)
    assert s.documentos(tmp_path) == []


@pytest.fixture
def projeto_registrado(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "DADOS", tmp_path / "dados")
    monkeypatch.setattr(s, "ARQUIVO", tmp_path / "dados" / "app.json")
    pasta = tmp_path / "proj"
    (pasta / "projeto").mkdir(parents=True)
    (pasta / "projeto" / "projeto.yaml").write_text(
        'cliente: "C"\nworkspace_alvo: "WS"\nconta_fabric: "x@y"\n', encoding="utf-8")
    (pasta / "projeto" / "inventario").mkdir()
    (pasta / "projeto" / "inventario" / "a.json").write_text("{}")
    (pasta / "projeto" / "analise").mkdir()
    (pasta / "projeto" / "analise" / "notas.md").write_text("x")
    return s.Projeto(id="1", cliente="C", projeto="P", pasta=str(pasta))


def test_etapa_segue_a_versao_mais_nova(projeto_registrado):
    pasta = Path(projeto_registrado.pasta)
    assert s.estado(projeto_registrado).etapa == "Documento pendente"
    docx(pasta, "DT_v0.1.docx", idade_dias=2)
    assert s.estado(projeto_registrado).etapa == "Documento gerado (v0.1)"
    docx(pasta, "DT_v0.1.docx", revisado=True, idade_dias=1)
    assert s.estado(projeto_registrado).etapa == "Revisado (v0.1)"
    docx(pasta, "DT_v0.2.docx")  # nova versão gerada a partir do revisado
    e = s.estado(projeto_registrado)
    assert e.etapa == "Documento gerado (v0.2)" and [d.rotulo for d in e.documentos][:2] == ["v0.2", "v0.1 · revisado"]


def test_abrir_documento_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        s.abrir_documento(s.DocVersao(tmp_path / "sumiu.docx", "0.1", False, s.datetime.now()))


def test_tema_salvo(projeto_registrado):
    cfg = s.carregar()
    assert cfg.tema == "auto"
    cfg.tema = "escuro"
    s.salvar(cfg)
    assert s.carregar().tema == "escuro"


def test_icones_oficiais():
    for chave, cor in (("vscode", "#007ACC"), ("claude", "#D97757")):
        svg = marca.SVG_FERRAMENTA[chave]
        assert svg.startswith("<svg") and f'fill="{cor}"' in svg and "<title>" not in svg
        assert marca.icone(chave).startswith("img:data:image/svg+xml;base64,")
