"""App: marcar projeto como revisado (pronto) e excluir projeto (apaga a pasta)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import servicos as s


@pytest.fixture
def cfg(tmp_path, monkeypatch) -> s.Config:
    monkeypatch.setattr(s, "DADOS", tmp_path / "dados")
    monkeypatch.setattr(s, "ARQUIVO", tmp_path / "dados" / "app.json")
    return s.carregar()


def projeto_em(cfg: s.Config, pasta: Path, marcador: bool = True) -> s.Projeto:
    (pasta / "projeto" / "docs").mkdir(parents=True)
    (pasta / "projeto" / "docs" / "DT_v0.1.docx").write_bytes(b"")
    if marcador:
        (pasta / s.MARCADOR).write_text(json.dumps({"id": "x"}), encoding="utf-8")
    p = s.Projeto(id=pasta.name, cliente="C", projeto="P", pasta=str(pasta))
    cfg.projetos.append(p)
    s.salvar(cfg)
    return p


def test_marcar_e_reabrir(cfg, tmp_path):
    p = projeto_em(cfg, tmp_path / "proj")
    s.marcar_revisado(cfg, p.id, True)
    assert s.carregar().projetos[0].revisado_em
    s.marcar_revisado(s.carregar(), p.id, False)
    assert s.carregar().projetos[0].revisado_em == ""


def test_app_json_antigo_sem_campo(cfg):
    s.DADOS.mkdir(parents=True)
    s.ARQUIVO.write_text(json.dumps({"projetos": [{"id": "1", "cliente": "C", "projeto": "P", "pasta": "x"}],
                                     "tema": "claro"}), encoding="utf-8")
    assert s.carregar().projetos[0].revisado_em == ""


def test_excluir_apaga_pasta_e_tira_da_lista(cfg, tmp_path):
    p = projeto_em(cfg, tmp_path / "proj")
    outro = projeto_em(cfg, tmp_path / "outro")
    (Path(p.pasta) / "projeto" / "docs" / "DT_v0.1.docx").chmod(0o444)  # somente leitura também sai
    s.excluir_projeto(s.carregar(), p)
    assert not Path(p.pasta).exists() and Path(outro.pasta).exists()
    assert [q.id for q in s.carregar().projetos] == [outro.id]


def test_excluir_pasta_que_ja_sumiu(cfg, tmp_path):
    p = s.Projeto(id="1", cliente="C", projeto="P", pasta=str(tmp_path / "sumiu"))
    cfg.projetos.append(p)
    s.excluir_projeto(cfg, p)
    assert s.carregar().projetos == []


def test_nao_apaga_pasta_que_nao_e_projeto(cfg, tmp_path):
    p = projeto_em(cfg, tmp_path / "qualquer", marcador=False)
    with pytest.raises(ValueError, match="não é apagada"):
        s.excluir_projeto(s.carregar(), p)
    assert Path(p.pasta).exists() and len(s.carregar().projetos) == 1


@pytest.mark.parametrize("onde", ["repo_git", "codigo_fonte"])
def test_nao_apaga_repositorio_nem_codigo_fonte(cfg, tmp_path, monkeypatch, onde):
    p = projeto_em(cfg, tmp_path / "proj")
    if onde == "repo_git":
        (Path(p.pasta) / ".git").mkdir()
    else:
        monkeypatch.setattr(s, "RAIZ", Path(p.pasta) / "sub")
    with pytest.raises(ValueError):
        s.excluir_projeto(s.carregar(), p)
    assert Path(p.pasta).exists()


def test_migra_lista_do_local_antigo(cfg, tmp_path, monkeypatch):
    antigos = tmp_path / "antigos"
    antigos.mkdir()
    monkeypatch.setattr(s, "DADOS_ANTIGOS", antigos)
    (antigos / "app.json").write_text(json.dumps({
        "autor": "Ana", "pasta_padrao": "C:\\Fabric",
        "projetos": [{"id": "1", "cliente": "C", "projeto": "P", "pasta": "C:\\Fabric\\C-P"}]}), encoding="utf-8")
    assert "Lista de projetos trazida" in s.migrar_local_antigo()
    c = s.carregar()
    assert c.autor == "Ana" and c.pasta_padrao == s.PASTA_PADRAO  # padrão antigo vira Projetos\
    assert c.projetos[0].pasta == "C:\\Fabric\\C-P"  # projeto existente não muda de lugar
    assert not (antigos / "app.json").exists() and (antigos / "app.json.migrado").exists()
    assert s.migrar_local_antigo() is None  # só uma vez


def test_nao_migra_se_ja_tem_lista(cfg, tmp_path, monkeypatch):
    monkeypatch.setattr(s, "DADOS_ANTIGOS", tmp_path / "antigos")
    (tmp_path / "antigos").mkdir()
    (tmp_path / "antigos" / "app.json").write_text("{}", encoding="utf-8")
    s.salvar(s.Config(autor="Novo"))
    assert s.migrar_local_antigo() is None and s.carregar().autor == "Novo"


def test_pasta_padrao_escolhida_pelo_usuario_fica(cfg):
    s.salvar(s.Config(pasta_padrao="D:\\Clientes"))
    assert s.carregar().pasta_padrao == "D:\\Clientes"


def test_locais_do_app():
    assert s.PASTA_PADRAO == str(s.CASA / "Projetos") and s.DADOS == s.CASA / "dados"
    assert s.CASA.parent == Path.home() and s.CASA.name in {"FabricDocHelper", "FabricDocHelper-dev"}
