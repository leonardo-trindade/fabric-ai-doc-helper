"""App Fabric Doc Helper: cadastra projetos de documentação e abre cada um no VS Code ou no Claude Desktop.

Rodar:   uv run python app/main.py            (janela própria)
         uv run python app/main.py --navegador (abre no navegador, se a janela própria falhar)

A conversa com o assistente acontece na ferramenta escolhida; o app só organiza os projetos.
A conta do Fabric é conferida pelo assistente no início de cada conversa.
Rodado de fora da instalação padrão, abre em modo desenvolvimento (ver app/servicos.py).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import servicos as s  # noqa: E402

if sys.stdout is None or sys.stderr is None:  # pythonw (atalho, sem console): saída vai para um log
    s.DADOS.mkdir(parents=True, exist_ok=True)
    sys.stdout = sys.stderr = open(s.DADOS / "app.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115

from nicegui import app, run, ui  # noqa: E402

NATIVO = "--navegador" not in sys.argv
ESTADO = {"ferramentas": s.Ferramentas()}


def ferramentas() -> s.Ferramentas:
    return ESTADO["ferramentas"]


async def detectar() -> None:
    f = await run.io_bound(s.detectar_ferramentas)
    ESTADO["ferramentas"] = f
    lista.refresh()
    if f.tem_vscode:
        f.vscode_extensao = await run.io_bound(s.vscode_tem_extensao, f)
        lista.refresh()


async def escolher_pasta(inicial: str = "") -> str | None:
    if not NATIVO:
        ui.notify("Digite o caminho da pasta (seleção visual só na janela própria do app).")
        return None
    import webview
    r = await app.native.main_window.create_file_dialog(webview.FileDialog.FOLDER, directory=inicial)
    return r[0] if r else None


# ---------------------------------------------------------------- seleção de ferramenta
def seletor_ferramenta(valor: dict) -> None:
    """Dois cartões (VS Code / Claude Desktop); indisponível = cinza."""
    f = ferramentas()

    @ui.refreshable
    def cartoes() -> None:
        with ui.row().classes("w-full gap-3 no-wrap"):
            for chave, nome in s.FERRAMENTAS.items():
                ok = f.disponivel(chave)
                marcado = valor["v"] == chave
                classes = "cursor-pointer border-2 " + ("border-primary bg-blue-50" if marcado else "border-transparent")
                if not ok:
                    classes = "opacity-40 cursor-not-allowed border-2 border-transparent"
                card = ui.card().classes(f"flex-1 p-3 {classes}")
                with card:
                    with ui.row().classes("items-center gap-2 no-wrap"):
                        ui.icon("code" if chave == "vscode" else "chat", size="sm").classes("text-primary")
                        ui.label(nome).classes("font-medium")
                    ui.label("Instalado" if ok else "Não instalado neste PC").classes("text-xs text-grey-7")
                    if chave == "vscode" and ok and f.vscode_extensao is False:
                        ui.label("Falta a extensão Claude Code").classes("text-xs text-orange-8")
                if ok:
                    card.on("click", lambda c=chave: (valor.update(v=c), cartoes.refresh()))
                else:
                    card.tooltip(f"{nome} não foi encontrado neste computador.")

    cartoes()


# ---------------------------------------------------------------- dialogs
def dialogo_novo() -> None:
    cfg = s.carregar()
    f = ferramentas()
    padrao = "vscode" if f.tem_vscode else ("claude" if f.tem_claude else "vscode")
    ferr = {"v": padrao}
    clientes = sorted({p.cliente for p in cfg.projetos})

    with ui.dialog() as dlg, ui.card().classes("w-[620px] max-w-full"):
        ui.label("Novo projeto").classes("text-h6")
        ui.label("Uma pasta por projeto: dados e contexto de um cliente nunca se misturam com os de outro."
                 ).classes("text-sm text-grey-7")
        cliente = ui.input("Cliente *", autocomplete=clientes).classes("w-full")
        projeto = ui.input("Projeto / fase *").classes("w-full")
        workspace = ui.input("Workspace do Fabric a documentar *",
                             placeholder="nome exato do workspace (somente leitura)").classes("w-full")
        autor = ui.input("Autor do documento *", value=cfg.autor).classes("w-full")
        with ui.row().classes("w-full items-end no-wrap gap-2"):
            pasta = ui.input("Pasta do projeto *").classes("flex-1")

            async def escolher() -> None:
                base = await escolher_pasta(cfg.pasta_padrao)
                if base:
                    pasta.value = str(Path(base) / s.nome_pasta(cliente.value or "Cliente", projeto.value or "Projeto"))
            ui.button(icon="folder_open", on_click=escolher).props("flat").tooltip("Escolher outro local")
        aviso = ui.label().classes("text-xs text-orange-8")

        def sugerir() -> None:
            if not pasta.value or getattr(pasta, "_auto", True):
                pasta.value = str(Path(cfg.pasta_padrao) / s.nome_pasta(cliente.value or "Cliente", projeto.value or "Projeto"))
                pasta._auto = True
        cliente.on_value_change(lambda: sugerir())
        projeto.on_value_change(lambda: sugerir())
        pasta.on("keydown", lambda: setattr(pasta, "_auto", False))
        pasta.on_value_change(lambda: aviso.set_text(
            "Atenção: essa pasta está no OneDrive; os dados do cliente seriam sincronizados." if s.na_onedrive(pasta.value or "") else ""))
        sugerir()

        ui.label("Onde você vai conversar com o assistente").classes("text-subtitle2 mt-2")
        seletor_ferramenta(ferr)
        progresso = ui.label().classes("text-sm text-primary")

        async def criar() -> None:
            campos = {"Cliente": cliente.value, "Projeto": projeto.value, "Workspace": workspace.value,
                      "Autor": autor.value, "Pasta": pasta.value}
            faltando = [k for k, v in campos.items() if not (v or "").strip()]
            if faltando:
                ui.notify("Preencha: " + ", ".join(faltando), type="warning")
                return
            if not ferramentas().disponivel(ferr["v"]):
                ui.notify("Instale o VS Code ou o Claude Desktop para continuar.", type="warning")
                return
            botao.disable()
            try:
                p = await run.io_bound(
                    s.criar_projeto, s.carregar(), cliente=cliente.value.strip(), projeto=projeto.value.strip(),
                    workspace=workspace.value.strip(), autor=autor.value.strip(), pasta=pasta.value.strip(),
                    ferramenta=ferr["v"], progresso=lambda m: setattr(progresso, "text", m))
            except Exception as e:  # noqa: BLE001
                progresso.text = ""
                ui.notify(str(e), type="negative", multi_line=True, timeout=0, close_button=True)
                botao.enable()
                return
            dlg.close()
            lista.refresh()
            ui.notify(f"Projeto criado em {p.pasta}", type="positive")
            await abrir_projeto(p, atualizar=False)

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            botao = ui.button("Criar e abrir", on_click=criar)
    dlg.open()


def dialogo_existente() -> None:
    f = ferramentas()
    ferr = {"v": "vscode" if f.tem_vscode else "claude"}
    with ui.dialog() as dlg, ui.card().classes("w-[560px] max-w-full"):
        ui.label("Adicionar pasta existente").classes("text-h6")
        ui.label("Para projetos clonados manualmente antes do app.").classes("text-sm text-grey-7")
        with ui.row().classes("w-full items-end no-wrap gap-2"):
            pasta = ui.input("Pasta do projeto").classes("flex-1")

            async def escolher() -> None:
                r = await escolher_pasta()
                if r:
                    pasta.value = r
            ui.button(icon="folder_open", on_click=escolher).props("flat")
        seletor_ferramenta(ferr)

        def adicionar() -> None:
            try:
                s.adicionar_existente(s.carregar(), (pasta.value or "").strip(), ferr["v"])
            except Exception as e:  # noqa: BLE001
                ui.notify(str(e), type="negative")
                return
            dlg.close()
            lista.refresh()

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Adicionar", on_click=adicionar)
    dlg.open()


def dialogo_config() -> None:
    cfg = s.carregar()
    f = ferramentas()
    with ui.dialog() as dlg, ui.card().classes("w-[560px] max-w-full"):
        ui.label("Configurações").classes("text-h6")
        autor = ui.input("Autor padrão", value=cfg.autor).classes("w-full")
        with ui.row().classes("w-full items-end no-wrap gap-2"):
            pasta = ui.input("Pasta padrão dos projetos", value=cfg.pasta_padrao).classes("flex-1")

            async def escolher() -> None:
                r = await escolher_pasta(cfg.pasta_padrao)
                if r:
                    pasta.value = r
            ui.button(icon="folder_open", on_click=escolher).props("flat")

        ui.separator()
        ui.label("Ferramentas detectadas").classes("text-subtitle2")
        ui.label(f"VS Code: {'instalado' if f.tem_vscode else 'não encontrado'}"
                 + ("" if not f.tem_vscode else f" · extensão Claude Code: {'sim' if f.vscode_extensao else 'não'}")).classes("text-sm")
        ui.label(f"Claude Desktop: {'instalado' if f.tem_claude else 'não encontrado'}").classes("text-sm")
        if f.tem_vscode and f.vscode_extensao is False:
            async def instalar() -> None:
                ok, msg = await run.io_bound(s.instalar_extensao, f)
                ui.notify("Extensão instalada." if ok else f"Falha: {msg}", type="positive" if ok else "negative")
                await detectar()
            ui.button("Instalar extensão Claude Code no VS Code", on_click=instalar).props("outline")

        ui.separator()
        ui.label(f"Versão instalada: {s.versao_atual()}").classes("text-subtitle2")
        if s.MODO_DEV:
            ui.label(f"Modo desenvolvimento (branch {s.branch_origem() or '?'}). Os projetos de teste acompanham "
                     "o branch atual deste clone; atualize com git.").classes("text-sm text-grey-7")
        else:
            status = ui.label().classes("text-sm")
            versoes = ui.select([], label="Instalar outra versão (voltar atrás)").props("dense outlined").classes("w-full")

            async def carregar_versoes() -> None:
                versoes.options = await run.io_bound(s.versoes_publicadas)
                versoes.update()

            async def instalar(tag: str | None) -> None:
                status.text = "Instalando…"
                ok, msg = await run.io_bound(s.instalar_versao, tag)
                status.text = msg if ok else f"Falha: {msg}"

            with ui.row().classes("gap-2"):
                ui.button("Atualizar para a mais nova", icon="system_update",
                          on_click=lambda: instalar(None)).props("outline")
                ui.button("Instalar versão escolhida", icon="history",
                          on_click=lambda: instalar(versoes.value) if versoes.value else ui.notify("Escolha uma versão.")
                          ).props("outline")
            ui.timer(0.1, carregar_versoes, once=True)

        def salvar() -> None:
            c = s.carregar()
            c.autor, c.pasta_padrao = autor.value.strip(), pasta.value.strip() or c.pasta_padrao
            s.salvar(c)
            dlg.close()

        with ui.row().classes("w-full justify-end"):
            ui.button("Fechar", on_click=dlg.close).props("flat")
            ui.button("Salvar", on_click=salvar)
    dlg.open()


# ---------------------------------------------------------------- ações
async def abrir_projeto(p: s.Projeto, atualizar: bool = True) -> None:
    f = ferramentas()
    if not f.disponivel(p.ferramenta):
        ui.notify(f"{s.FERRAMENTAS[p.ferramenta]} não está instalado. Escolha outra ferramenta no projeto.", type="warning")
        return
    if atualizar:
        n = ui.notification("Preparando o projeto…", spinner=True, timeout=None)
        aviso = await run.io_bound(s.atualizar_projeto, p)
        n.dismiss()
        if aviso:
            ui.notify(aviso, type="warning")
    try:
        msg = await run.io_bound(s.abrir, p, f)
    except Exception as e:  # noqa: BLE001
        ui.notify(str(e), type="negative")
        return
    cfg = s.carregar()
    for q in cfg.projetos:
        if q.id == p.id:
            q.ultimo_acesso = s.agora()
    s.salvar(cfg)
    ui.notify(msg, type="info", multi_line=True, timeout=12000, close_button=True)
    if p.ferramenta == "vscode" and f.vscode_extensao is False:
        ui.notify("A extensão Claude Code não está instalada no VS Code (Configurações → Instalar extensão).", type="warning")
    lista.refresh()


def trocar_ferramenta(p: s.Projeto, nova: str) -> None:
    cfg = s.carregar()
    for q in cfg.projetos:
        if q.id == p.id:
            q.ferramenta = nova
    s.salvar(cfg)
    lista.refresh()


def remover(p: s.Projeto) -> None:
    cfg = s.carregar()
    cfg.projetos = [q for q in cfg.projetos if q.id != p.id]
    s.salvar(cfg)
    lista.refresh()
    ui.notify("Removido da lista (a pasta não foi apagada).")


# ---------------------------------------------------------------- lista
FILTRO = {"texto": ""}


@ui.refreshable
def lista() -> None:
    cfg = s.carregar()
    f = ferramentas()
    termo = FILTRO["texto"].lower()
    projetos = [p for p in cfg.projetos if termo in f"{p.cliente} {p.projeto} {p.pasta}".lower()]
    if not cfg.projetos:
        with ui.column().classes("w-full items-center py-16 gap-3"):
            ui.icon("description", size="xl").classes("text-grey-5")
            ui.label("Nenhum projeto ainda").classes("text-h6 text-grey-8")
            ui.label("Crie um projeto para cada cliente/fase que for documentar.").classes("text-grey-7")
            ui.button("Novo projeto", icon="add", on_click=dialogo_novo)
        return
    por_cliente: dict[str, list[s.Projeto]] = {}
    for p in sorted(projetos, key=lambda p: (p.cliente.lower(), p.ultimo_acesso or ""), reverse=False):
        por_cliente.setdefault(p.cliente, []).append(p)
    for cliente, itens in por_cliente.items():
        ui.label(cliente).classes("text-subtitle1 font-medium text-primary mt-4")
        with ui.grid().classes("w-full gap-3 grid-cols-1 md:grid-cols-2"):
            for p in itens:
                cartao(p, f)


def cartao(p: s.Projeto, f: s.Ferramentas) -> None:
    e = s.estado(p)
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-start justify-between no-wrap"):
            with ui.column().classes("gap-0 min-w-0"):
                ui.label(p.projeto or "(sem nome)").classes("text-h6 leading-tight")
                ui.label(p.pasta).classes("text-xs text-grey-7 break-all")
            with ui.button(icon="more_vert").props("flat round dense"):
                with ui.menu():
                    ui.menu_item("Abrir pasta", on_click=lambda: os.startfile(p.pasta) if e.existe else None)
                    if e.documentos:
                        ui.menu_item(f"Abrir documento ({e.documentos[0].name})",
                                     on_click=lambda d=e.documentos[0]: os.startfile(d))
                    ui.separator()
                    ui.menu_item("Remover da lista", on_click=lambda: remover(p))
        with ui.row().classes("gap-2 items-center"):
            cor = "grey" if not e.existe else ("positive" if e.etapa.startswith(("Revisado", "Documento gerado")) else "primary")
            ui.badge(e.etapa, color=cor).props("outline")
        with ui.column().classes("gap-0 text-sm"):
            ui.label(f"Workspace: {e.workspace or '—'}")
            ui.label(f"Conta: {e.conta or 'confirmada pelo assistente na 1ª conversa'}")
            if p.ultimo_acesso:
                ui.label(f"Último acesso: {p.ultimo_acesso}").classes("text-grey-7")
        with ui.row().classes("w-full items-center justify-between mt-2"):
            opcoes = {k: v + ("" if f.disponivel(k) else " (não instalado)") for k, v in s.FERRAMENTAS.items()}
            ui.select(opcoes, value=p.ferramenta, label="Abrir em",
                      on_change=lambda ev: trocar_ferramenta(p, ev.value)).props("dense outlined").classes("w-52")
            ui.button("Abrir", icon="open_in_new", on_click=lambda: abrir_projeto(p)).props(
                "" if e.existe and f.disponivel(p.ferramenta) else "disable")


# ---------------------------------------------------------------- página
@ui.page("/")
async def pagina() -> None:
    ui.colors(primary="#1f4e8c", secondary="#3a7bd5", accent="#c9a227", positive="#2e7d32")
    ui.query("body").classes("bg-grey-1")
    with ui.header().classes("bg-primary items-center justify-between px-6"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("description", size="md")
            ui.label("Fabric Doc Helper").classes("text-h6")
            ui.label(s.versao_atual()).classes("text-xs px-2 py-0.5 rounded border border-white/60 text-white")
        with ui.row().classes("gap-1"):
            ui.button("Novo projeto", icon="add", on_click=dialogo_novo).props("unelevated color=white text-color=primary")
            ui.button(icon="create_new_folder", on_click=dialogo_existente).props("flat color=white").tooltip("Adicionar pasta existente")
            ui.button(icon="settings", on_click=dialogo_config).props("flat color=white").tooltip("Configurações")
    if s.MODO_DEV:
        with ui.row().classes("w-full bg-orange-2 text-orange-10 px-6 py-2 items-center gap-2 no-wrap"):
            ui.icon("science")
            ui.label(f"DESENVOLVIMENTO · branch {s.branch_origem() or '?'} · projetos e lista separados do uso "
                     f"real (pasta padrão {s.PASTA_PADRAO})").classes("text-sm")
    with ui.column().classes("w-full max-w-5xl mx-auto px-4 py-4"):
        ui.input(placeholder="Buscar por cliente, projeto ou pasta",
                 on_change=lambda ev: (FILTRO.update(texto=ev.value or ""), lista.refresh())
                 ).props("outlined dense clearable").classes("w-full")
        lista()
    ui.timer(0.1, detectar, once=True)  # detecção roda depois que a página aparece
    ui.timer(1.0, verificar_versao, once=True)


async def verificar_versao() -> None:
    """Produção: avisa quando há versão publicada mais nova, com as novidades do CHANGELOG."""
    tag = await run.io_bound(s.atualizacao_disponivel)
    if not tag:
        return
    notas = await run.io_bound(s.novidades, tag)
    with ui.dialog() as dlg, ui.card().classes("w-[560px] max-w-full"):
        ui.label(f"Nova versão disponível: {tag}").classes("text-h6")
        ui.markdown(notas).classes("text-sm max-h-80 overflow-auto")
        status = ui.label().classes("text-sm")

        async def atualizar() -> None:
            status.text = "Instalando…"
            ok, msg = await run.io_bound(s.instalar_versao, tag)
            status.text = msg if ok else f"Falha: {msg}"

        with ui.row().classes("w-full justify-end"):
            ui.button("Depois", on_click=dlg.close).props("flat")
            ui.button("Atualizar agora", icon="system_update", on_click=atualizar)
    dlg.open()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Fabric Doc Helper" + (" (dev)" if s.MODO_DEV else ""), native=NATIVO, host="127.0.0.1",  # só este computador window_size=(1100, 780) if NATIVO else None,
           reload=False, show=not NATIVO and "--sem-abrir" not in sys.argv, port=None if NATIVO else 8765, favicon="📄")
