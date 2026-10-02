"""Funções compartilhadas pelos scripts (fab, projeto.yaml, mascaramento de segredos)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from guarda import Bloqueio, verificar_fab

RAIZ = Path(__file__).resolve().parent.parent
PROJETO = RAIZ / "projeto"

SEGREDO = re.compile(
    r"""(?ix)
    (?P<chave>\b\w*(?:senha|password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|account[_-]?key)\w*)
    (?P<sep>\s*[:=]\s*)
    (?P<aspas>\\?["'])(?P<valor>[^"'\\\n]{3,})(?P=aspas)
    """
)
CONN_STRING = re.compile(r"(?i)((?:password|pwd|accountkey|sharedaccesssignature)\s*=\s*)([^;\"'\s]+)")


def mascarar(texto: str) -> tuple[str, int]:
    """Troca valores de senhas/tokens/chaves por ***MASCARADO***. Retorna (texto, ocorrências)."""
    n = len(SEGREDO.findall(texto)) + len(CONN_STRING.findall(texto))
    texto = SEGREDO.sub(lambda m: f"{m.group('chave')}{m.group('sep')}{m.group('aspas')}***MASCARADO***{m.group('aspas')}", texto)
    texto = CONN_STRING.sub(lambda m: f"{m.group(1)}***MASCARADO***", texto)
    return texto, n


def fab_exe() -> str:
    exe = shutil.which("fab")
    if not exe:
        sys.exit("`fab` não encontrado. Rode via `uv run python scripts/...` após `uv sync`.")
    return exe


def fab(*args: str, check: bool = True) -> str:
    try:
        verificar_fab(list(args))  # mesmas regras da guarda, em qualquer ferramenta
    except Bloqueio as e:
        sys.exit(f"[guarda fabric-ai-doc-helper] BLOQUEADO: {e}")
    p = subprocess.run([fab_exe(), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"fab {' '.join(args[:2])}: {((p.stdout or '') + (p.stderr or '')).strip()[:300]}")
    return p.stdout


def fab_api(endpoint: str) -> dict:
    """GET na API REST do Fabric via `fab api` (retorna o corpo JSON)."""
    try:
        dados = json.loads(fab("api", endpoint))
    except (json.JSONDecodeError, RuntimeError):
        return {}
    return dados.get("text", dados) if isinstance(dados, dict) else {}


def json_da_saida(txt: str):
    """`fab get` pode imprimir avisos antes do JSON: pega do primeiro { em diante."""
    i = txt.find("{")
    return json.loads(txt[i:]) if i >= 0 else {}


def config() -> dict:
    cfg = PROJETO / "projeto.yaml"
    if not cfg.exists():
        sys.exit("projeto/projeto.yaml não existe. Faça a entrevista inicial (skill iniciar-projeto).")
    dados = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    if not (dados.get("workspace_alvo") or "").strip():
        sys.exit("`workspace_alvo` não definido em projeto/projeto.yaml.")
    return dados


def sessao_fab() -> dict:
    """Conta e tenant do login ativo do `fab` (nunca retorna tokens)."""
    status = fab("auth", "status", check=False)
    tenant = re.search(r"Tenant ID:\s*(\S+)", status)
    conta = re.search(r"Account:\s*(\S+)", status)
    return {"logado": "Logged In: True" in status,
            "conta": conta.group(1) if conta else None,
            "tenant_id": tenant.group(1) if tenant else None}


def checar_login(cfg: dict) -> dict:
    """Interrompe se não houver login ou se a conta/tenant não for a registrada no projeto."""
    s = sessao_fab()
    if not s["logado"]:
        sys.exit("Sem login no Fabric. Avise o usuário e rode `uv run python scripts/entrar.py` (login pelo navegador).")
    conta_esp = (cfg.get("conta_fabric") or "").strip().lower()
    tenant_esp = (cfg.get("tenant_id") or "").strip().lower()
    if (conta_esp and (s["conta"] or "").lower() != conta_esp) or \
       (tenant_esp and (s["tenant_id"] or "").lower() != tenant_esp):
        sys.exit(f"LOGIN DIFERENTE DO PROJETO: ativo = {s['conta']} (tenant {s['tenant_id']}); "
                 f"projeto espera {cfg.get('conta_fabric') or '?'} (tenant {cfg.get('tenant_id') or '?'}). "
                 "Mostre as duas contas ao usuário e peça permissão para trocar; se ele aceitar, rode "
                 "`uv run python scripts/entrar.py --trocar`.")
    return {"tenant_id": s["tenant_id"], "conta": s["conta"]}
