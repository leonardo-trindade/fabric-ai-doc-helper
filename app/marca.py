"""Identidade visual do app: tokens de cor do tema (único, escuro/azul),
tipografia, componentes (cartões, rótulos, botões, menus) e os ícones das ferramentas.

Ícones: SVGs oficiais das marcas, do Simple Icons (https://simpleicons.org, CC0), com as cores das
marcas. VS Code e Claude são marcas de seus donos; aqui só indicam onde o projeto será aberto.
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

AZUL = "#1d9bf0"

ICONES = Path(__file__).resolve().parent / "icones"
COR_MARCA = {"vscode": "#007ACC", "claude": "#D97757"}


def _svg(chave: str, arquivo: str) -> str:
    """SVG oficial (Simple Icons, monocromático) com a cor da marca aplicada ao desenho."""
    svg = (ICONES / arquivo).read_text(encoding="utf-8")
    svg = re.sub(r"<title>.*?</title>", "", svg)
    return svg.replace("<path ", f'<path fill="{COR_MARCA[chave]}" ', 1)


SVG_FERRAMENTA = {"vscode": _svg("vscode", "vscode.svg"), "claude": _svg("claude", "claude.svg")}


def icone(chave: str) -> str:
    """Ícone de ferramenta no formato do Quasar (`img:` + data URI), para botões e itens de menu."""
    return "img:data:image/svg+xml;base64," + base64.b64encode(SVG_FERRAMENTA[chave].encode()).decode()


# Marca própria do app: folha de documento com a dobra no canto e um traço de "fluxo" (dados que viram
# documento), num quadrado com gradiente azul → verde-água. Serve de logo e de ícone da janela.
LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">'
    '<defs><linearGradient id="fdh-g" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#2563eb"/><stop offset="1" stop-color="#14b8a6"/></linearGradient></defs>'
    '<rect width="32" height="32" rx="8" fill="url(#fdh-g)"/>'
    '<path d="M10 7h8.5L23 11.5V24a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z" fill="#fff"/>'
    '<path d="M18.5 7v4.5H23" fill="#cfe3fb"/>'
    '<path d="M12 16.5h3l1.6-2.6 2 5 1.4-2.4H21" fill="none" stroke="#2563eb" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M12 21.5h7" stroke="#94a3b8" stroke-width="1.6" stroke-linecap="round"/>'
    '</svg>')

FONTES = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
          '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" '
          'rel="stylesheet">')

CSS = """
:root {
  --fdh-bg: #0b1220; --fdh-chrome: #0b1220; --fdh-surface: #111a2b; --fdh-surface-2: #0f1726;
  --fdh-border: #222e42; --fdh-border-strong: #334155;
  --fdh-text: #f1f5f9; --fdh-muted: #94a3b8; --fdh-faint: #64748b;
  --fdh-primary: #1d9bf0; --fdh-primary-hover: #42abf3; --fdh-primary-soft: rgba(29, 155, 240, .14); --fdh-on-primary: #ffffff;
  --fdh-teal: #14b8a6;
  --fdh-ok: #34d399; --fdh-ok-soft: rgba(52, 211, 153, .14); --fdh-warn: #fb923c; --fdh-warn-soft: rgba(251, 146, 60, .14);
  --fdh-danger: #f87171; --fdh-danger-soft: rgba(248, 113, 113, .14);
  --fdh-shadow: 0 1px 2px rgba(0, 0, 0, .35); --fdh-shadow-lg: 0 12px 32px rgba(0, 0, 0, .5);
  --fdh-radius: 8px; --fdh-radius-sm: 6px;
}

body { background: var(--fdh-bg) !important; color: var(--fdh-text);
       font-family: Inter, "Segoe UI", system-ui, -apple-system, sans-serif; -webkit-font-smoothing: antialiased; }
.q-page-container, .nicegui-content { background: var(--fdh-bg); }

/* Cabeçalho e barra lateral */
.fdh-header { background: var(--fdh-chrome) !important; color: var(--fdh-text) !important;
              border-bottom: 1px solid var(--fdh-border); box-shadow: none !important; }
.fdh-logo { display: flex; align-items: center; gap: 10px; white-space: nowrap; line-height: 1; }
.fdh-logo svg { flex: none; display: block; }
.fdh-logo .nome { font-size: 17px; font-weight: 700; letter-spacing: -.01em; color: var(--fdh-text); }
.fdh-logo .nome span { font-weight: 400; color: var(--fdh-muted); }
.fdh-drawer { background: var(--fdh-chrome) !important; border-right: 1px solid var(--fdh-border) !important; }
.fdh-nav { display: flex; width: 100%; align-items: center; gap: 12px; padding: 9px 12px; border-radius: var(--fdh-radius);
           color: var(--fdh-muted); font-size: 13.5px; font-weight: 500; cursor: pointer; user-select: none;
           transition: background .15s, color .15s; }
.fdh-nav:hover { background: var(--fdh-surface-2); color: var(--fdh-text); }
.fdh-nav.ativo { background: var(--fdh-primary-soft); color: var(--fdh-primary); font-weight: 600; }
.fdh-nav .q-icon { font-size: 18px; }
.fdh-secao-nav { font-size: 10.5px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase;
                 color: var(--fdh-muted); padding: 18px 12px 6px; }

/* Rótulos e títulos */
.fdh-rotulo { font-size: 10.5px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; color: var(--fdh-muted); }
.fdh-valor { font-size: 20px; font-weight: 700; color: var(--fdh-text); line-height: 1.2; }
.fdh-titulo-secao { font-size: 15px; font-weight: 800; color: var(--fdh-text); }
.fdh-cabecalho-secao { border-bottom: 1px solid var(--fdh-border); padding-bottom: 8px; }
.fdh-titulo-cartao { font-size: 16px; font-weight: 800; color: var(--fdh-text); line-height: 1.25; }
.fdh-texto { font-size: 13px; color: var(--fdh-text); }
.fdh-mudo { font-size: 12px; color: var(--fdh-muted); }
.fdh-caminho { font-size: 11.5px; color: var(--fdh-faint); font-family: Consolas, "Cascadia Mono", monospace;
               display: block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fdh-cartao, .fdh-cartao .col, .fdh-cartao .q-column, .fdh-cartao .nicegui-column { min-width: 0; }
.fdh-cartao .ellipsis { display: block; max-width: 100%; }

/* Cartões */
.fdh-cartao { background: var(--fdh-surface) !important; color: var(--fdh-text);
              border: 1px solid var(--fdh-border); border-radius: var(--fdh-radius) !important;
              box-shadow: var(--fdh-shadow) !important; transition: border-color .15s, box-shadow .15s; }
.fdh-cartao.interativo:hover { border-color: var(--fdh-border-strong); box-shadow: var(--fdh-shadow-lg) !important; }
.fdh-faixa { border: 1px solid var(--fdh-warn); background: var(--fdh-warn-soft); color: var(--fdh-text);
             border-radius: var(--fdh-radius); padding: 10px 14px; font-size: 12.5px; }

/* Selos (versão, "mais nova") */
.fdh-selo { font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; white-space: nowrap;
            padding: 3px 7px; border-radius: 4px; border: 1px solid currentColor;
            max-width: 190px; overflow: hidden; text-overflow: ellipsis; flex: none; }
.fdh-selo.neutro { color: var(--fdh-muted); } .fdh-selo.azul { color: var(--fdh-primary); background: var(--fdh-primary-soft); }
.fdh-selo.ok { color: var(--fdh-ok); background: var(--fdh-ok-soft); }
.fdh-selo.alerta { color: var(--fdh-warn); background: var(--fdh-warn-soft); }
.fdh-selo.erro { color: var(--fdh-danger); background: var(--fdh-danger-soft); }

/* Botões: primário (cheio), suave (contorno) e fantasma. Estados: hover, active, focus, disabled */
.q-btn.fdh-btn { text-transform: uppercase; font-size: 11px; font-weight: 800; letter-spacing: .04em;
                 border-radius: var(--fdh-radius-sm); min-height: 34px; padding: 0 14px; box-shadow: none;
                 transition: background .15s, border-color .15s, color .15s, transform .06s, opacity .15s; }
.q-btn.fdh-btn:active:not(.disabled) { transform: translateY(1px); }
.q-btn.fdh-btn:focus-visible { outline: 2px solid var(--fdh-primary); outline-offset: 2px; }
.q-btn.fdh-btn.disabled, .q-btn.fdh-btn[disabled] { opacity: .45 !important; cursor: not-allowed !important; }
.q-btn.fdh-btn .q-focus-helper { display: none; }
.q-btn.fdh-primario { background: var(--fdh-primary) !important; color: var(--fdh-on-primary) !important; }
.q-btn.fdh-primario:hover:not(.disabled) { background: var(--fdh-primary-hover) !important; }
.q-btn.fdh-suave { background: var(--fdh-surface-2) !important; color: var(--fdh-text) !important;
                   border: 1px solid var(--fdh-border-strong); }
.q-btn.fdh-suave:hover:not(.disabled) { border-color: var(--fdh-primary); color: var(--fdh-primary) !important; }
.q-btn.fdh-fantasma { background: transparent !important; color: var(--fdh-muted) !important; }
.q-btn.fdh-fantasma:hover:not(.disabled) { background: var(--fdh-surface-2) !important; color: var(--fdh-text) !important; }
.q-btn.fdh-perigo { background: var(--fdh-danger) !important; color: #fff !important; }
.q-btn.fdh-perigo:hover:not(.disabled) { filter: brightness(1.1); }
.fdh-menu .q-item .q-item__section--avatar { min-width: 32px; color: var(--fdh-muted); }
.fdh-menu .q-item.fdh-perigo, .fdh-menu .q-item.fdh-perigo .q-item__section--avatar { color: var(--fdh-danger) !important; }
.fdh-menu .q-item.fdh-perigo:hover { background: var(--fdh-danger-soft); }
.q-btn.fdh-redondo { border-radius: 50%; min-height: 34px; width: 34px; padding: 0; border: 1px solid var(--fdh-border); }

/* Botão de documento com menu de versões (q-btn-dropdown split) */
.fdh-doc { width: 100%; }
.fdh-doc.q-btn-group { border-radius: var(--fdh-radius-sm); box-shadow: none; overflow: hidden; }
.fdh-doc .q-btn { background: var(--fdh-primary) !important; color: var(--fdh-on-primary) !important;
                  text-transform: uppercase; font-size: 11px; font-weight: 800; letter-spacing: .04em; min-height: 34px; }
.fdh-doc .q-btn:first-child { flex: 1; justify-content: flex-start; }
.fdh-doc .q-btn:hover { background: var(--fdh-primary-hover) !important; }
.fdh-doc .q-btn-dropdown__arrow-container { border-left: 1px solid rgba(255, 255, 255, .28) !important; }
.fdh-doc .q-btn .q-focus-helper { display: none; }
.q-menu.fdh-menu { background: var(--fdh-surface); color: var(--fdh-text); border: 1px solid var(--fdh-border);
                   border-radius: var(--fdh-radius); box-shadow: var(--fdh-shadow-lg); min-width: 280px; }
.fdh-menu .q-item { min-height: 44px; border-radius: var(--fdh-radius-sm); margin: 2px 4px; transition: background .12s; }
.fdh-menu .q-item:hover { background: var(--fdh-primary-soft); }
.fdh-menu .q-item__label--caption { color: var(--fdh-muted); }

/* Referências do projeto */
.fdh-ref { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border: 1px solid var(--fdh-border);
           border-radius: var(--fdh-radius-sm); background: var(--fdh-surface-2); min-width: 0; }
.fdh-ref .nome { font-size: 13px; font-weight: 600; color: var(--fdh-text); overflow: hidden; text-overflow: ellipsis;
                 white-space: nowrap; flex: 1; min-width: 0; }
.fdh-ref .q-select { width: 250px; flex: none; }
.fdh-ref.sem-categoria { border-color: var(--fdh-warn); }
@media (max-width: 599px) { .fdh-ref { flex-wrap: wrap; } .fdh-ref .q-select { width: 100%; } }

/* Escolha da ferramenta (VS Code / Claude Desktop) */
.fdh-ferramenta { display: flex; align-items: center; gap: 8px; padding: 7px 10px; flex: 1; min-width: 0;
                  border: 1px solid var(--fdh-border-strong); border-radius: var(--fdh-radius-sm); cursor: pointer;
                  background: var(--fdh-surface-2); transition: border-color .15s, background .15s, opacity .15s; }
.fdh-ferramenta:hover:not(.indisponivel) { border-color: var(--fdh-primary); }
.fdh-ferramenta.marcada { border-color: var(--fdh-primary); background: var(--fdh-primary-soft);
                          box-shadow: inset 0 0 0 1px var(--fdh-primary); }
.fdh-ferramenta.indisponivel { opacity: .45; cursor: not-allowed; }
.fdh-ferramenta .svg { width: 18px; height: 18px; flex: none; }
.fdh-ferramenta .nome { font-size: 12.5px; font-weight: 700; color: var(--fdh-text); }
.fdh-ferramenta .estado { font-size: 10.5px; color: var(--fdh-muted); }

/* Campos e diálogos */
.fdh-dialogo { background: var(--fdh-surface) !important; color: var(--fdh-text); border-radius: 10px !important;
               border: 1px solid var(--fdh-border); }
.fdh-dialogo .q-field__label, .fdh-dialogo .q-field__native, .fdh-busca .q-field__native { color: var(--fdh-text); }
.fdh-busca .q-field__control { background: var(--fdh-surface); border-radius: var(--fdh-radius-sm); }
"""
