"""App Fabric Doc Helper: cadastra projetos de documentação e abre cada um no VS Code ou no Claude Desktop.

Rodar:   uv run python app/main.py            (janela própria)
         uv run python app/main.py --navegador (abre no navegador, se a janela própria falhar)

A conversa com o assistente acontece na ferramenta escolhida; o app só organiza os projetos.
A conta do Fabric é conferida pelo assistente no início de cada conversa.
Rodado de fora da instalação padrão, abre em modo desenvolvimento (ver app/servicos.py).
Visual: app/marca.py (marca própria, tema escuro).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marca  # noqa: E402
import servicos as s  # noqa: E402

if sys.stdout is None or sys.stderr is None:  # pythonw (atalho, sem console): saída vai para um log
    s.DADOS.mkdir(parents=True, exist_ok=True)
    sys.stdout = sys.stderr = open(s.DADOS / "app.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115

from nicegui import app, run, ui  # noqa: E402

try:  # 1ª abertura depois da v2.3: traz a lista de projetos do local antigo (AppData)
    AVISO_MIGRACAO = s.migrar_local_antigo()
except OSError as e:
    AVISO_MIGRACAO = f"Não foi possível trazer a lista de projetos do local antigo ({s.DADOS_ANTIGOS}): {e}"

NATIVO = "--navegador" not in sys.argv
ESTADO = {"ferramentas": s.Ferramentas()}
FILTRO = {"texto": ""}


def ferramentas() -> s.Ferramentas:
    return ESTADO["ferramentas"]


async def detectar() -> None:
    f = await run.io_bound(s.detectar_ferramentas)
    ESTADO["ferramentas"] = f
    painel.refresh()
    if f.tem_vscode:
        f.vscode_extensao = await run.io_bound(s.vscode_tem_extensao, f)
        painel.refresh()


async def escolher_pasta(inicial: str = "") -> str | None:
    if not NATIVO:
        ui.notify("Digite o caminho da pasta (seleção visual só na janela própria do app).")
        return None
    import webview
    r = await app.native.main_window.create_file_dialog(webview.FileDialog.FOLDER, directory=inicial)
    return r[0] if r else None


# ---------------------------------------------------------------- componentes
def botao(texto: str = "", *, on_click=None, icone: str | None = None, tipo: str = "suave",
          desabilitado: bool = False, dica: str | None = None) -> ui.button:
    """Botão do design system: tipo primario | suave | fantasma."""
    b = ui.button(texto, on_click=on_click, icon=icone, color=None).props("unelevated no-caps")
    b.classes(f"fdh-btn fdh-{tipo}")
    if desabilitado:
        b.disable()
    if dica:
        b.tooltip(dica)
    return b


def rotulo(texto: str) -> ui.label:
    return ui.label(texto).classes("fdh-rotulo")


def cabecalho_secao(titulo: str, direita: str = "") -> None:
    with ui.row().classes("w-full items-end justify-between no-wrap fdh-cabecalho-secao"):
        ui.label(titulo).classes("fdh-titulo-secao")
        if direita:
            ui.label(direita).classes("fdh-rotulo")


def svg(chave: str) -> None:
    ui.html(marca.SVG_FERRAMENTA[chave], sanitize=False).classes("svg")


def seletor_ferramenta(valor: dict, ao_mudar=None, compacto: bool = False) -> None:
    """VS Code / Claude Desktop com os ícones oficiais; ferramenta não instalada fica indisponível."""
    f = ferramentas()

    @ui.refreshable
    def opcoes() -> None:
        with ui.row().classes("w-full gap-2 no-wrap"):
            for chave, nome in s.FERRAMENTAS.items():
                ok = f.disponivel(chave)
                classes = "fdh-ferramenta" + (" marcada" if valor["v"] == chave else "") + ("" if ok else " indisponivel")
                caixa = ui.element("div").classes(classes).props(f'role="radio" tabindex="{0 if ok else -1}" '
                                                                  f'aria-checked="{str(valor["v"] == chave).lower()}"')
                with caixa:
                    svg(chave)
                    with ui.column().classes("gap-0 min-w-0"):
                        ui.label(nome).classes("nome")
                        if not compacto or not ok:
                            estado = "Instalado" if ok else "Não instalado neste PC"
                            if chave == "vscode" and ok and f.vscode_extensao is False:
                                estado = "Falta a extensão Claude Code"
                            ui.label(estado).classes("estado")
                if ok:
                    def escolher(c=chave):
                        valor["v"] = c
                        opcoes.refresh()
                        if ao_mudar:
                            ao_mudar(c)
                    caixa.on("click", escolher)
                    caixa.on("keydown.enter", escolher)
                else:
                    caixa.tooltip(f"{nome} não foi encontrado neste computador.")

    opcoes()


def botao_documento(e: s.Estado) -> None:
    """Botão principal abre a versão mais nova; o menu lista as anteriores."""
    if not e.documentos:
        botao("Nenhum documento ainda", icone="description", desabilitado=True,
              dica="O documento aparece aqui depois que o assistente gerar a 1ª versão.").classes("w-full")
        return
    atual = e.documentos[0]

    def abrir(doc: s.DocVersao) -> None:
        try:
            s.abrir_documento(doc)
        except Exception as ex:  # noqa: BLE001
            ui.notify(str(ex), type="negative")

    with ui.dropdown_button(f"Abrir documento · {atual.rotulo}", icon="description", split=True, auto_close=True,
                            color=None, on_click=lambda: abrir(atual)).classes("fdh-doc").props(
                                'unelevated no-caps menu-anchor="bottom end" menu-self="top end" '
                                'content-class="fdh-menu"'):
        rotulo("Versões do documento").classes("q-px-md q-pt-sm q-pb-xs")
        for i, doc in enumerate(e.documentos):
            with ui.item(on_click=lambda d=doc: abrir(d)).props("clickable"):
                with ui.item_section().props("avatar"):
                    ui.icon("verified" if doc.revisado else "description").style(
                        f"color: var({'--fdh-ok' if doc.revisado else '--fdh-primary'})")
                with ui.item_section():
                    ui.item_label(doc.rotulo).classes("fdh-texto text-weight-bold")
                    ui.item_label(f"{doc.modificado:%d/%m/%Y %H:%M} · {doc.arquivo.name}").props("caption")
                if i == 0:
                    with ui.item_section().props("side"):
                        ui.label("Mais nova").classes("fdh-selo azul")


# ---------------------------------------------------------------- referências
ICONE_CATEGORIA = {"levantamento": "assignment", "mapeamento": "table_chart", "outro": "attach_file"}
TIPOS_REFERENCIA = ("Documentos (*.xlsx;*.xlsm;*.pptx;*.docx;*.pdf;*.md;*.txt;*.csv)", "Todos os arquivos (*.*)")


def botao_referencias(p: s.Projeto, e: s.Estado) -> None:
    """Anexar: o usuário escolhe a categoria e depois os arquivos (copiados para projeto/referencias/)."""
    with ui.row().classes("w-full gap-2 no-wrap"):
        with botao("Anexar referência", icone="attach_file", desabilitado=not e.existe).classes("col"):
            with ui.menu().classes("fdh-menu").props('anchor="bottom left" self="top left"'):
                rotulo("Categoria do arquivo").classes("q-px-md q-pt-sm q-pb-xs")
                for tipo, nome in s.CATEGORIAS.items():
                    with ui.item(on_click=lambda t=tipo: anexar(p, t)).props("clickable v-close-popup"):
                        with ui.item_section().props("avatar"):
                            ui.icon(ICONE_CATEGORIA[tipo]).style("color: var(--fdh-primary)")
                        with ui.item_section():
                            ui.item_label(nome).classes("fdh-texto text-weight-bold")
        pendentes = sum(not r.tipo for r in e.referencias)
        botao(f"Ver ({len(e.referencias)})", icone="folder_open", tipo="fantasma",
              desabilitado=not e.referencias, on_click=lambda: dialogo_referencias(p),
              dica=f"{pendentes} arquivo(s) sem categoria" if pendentes else "Arquivos de referência do projeto")


async def anexar(p: s.Projeto, tipo: str) -> None:
    categoria = s.CATEGORIAS[tipo]
    if not NATIVO:  # no navegador não há caminho de arquivo: envia pelo formulário
        dlg, cartao = dialogo(f"Anexar · {categoria}", "Escolha os arquivos que complementam a documentação.", 520)

        async def recebido(ev) -> None:
            dados = await ev.file.read()
            try:
                await run.io_bound(s.anexar_referencia, p.pasta, ev.file.name, dados, tipo)
            except Exception as ex:  # noqa: BLE001
                ui.notify(str(ex), type="negative")
                return
            ui.notify(f"{ev.file.name} anexado como {categoria}.", type="positive")
            painel.refresh()
        with cartao:
            ui.upload(multiple=True, auto_upload=True, on_upload=recebido).props("flat bordered").classes("w-full")
            with ui.row().classes("w-full justify-end"):
                botao("Fechar", on_click=dlg.close, tipo="fantasma")
        dlg.open()
        return
    import webview
    caminhos = await app.native.main_window.create_file_dialog(
        webview.FileDialog.OPEN, allow_multiple=True, file_types=TIPOS_REFERENCIA)
    if not caminhos:
        return
    nomes, erros = [], []
    for c in caminhos:
        try:
            ref = await run.io_bound(s.anexar_referencia, p.pasta, Path(c).name, Path(c), tipo)
            nomes.append(ref.arquivo.name)
        except Exception as ex:  # noqa: BLE001
            erros.append(f"{Path(c).name}: {ex}")
    if nomes:
        ui.notify(f"{len(nomes)} arquivo(s) anexado(s) como {categoria}: " + ", ".join(nomes),
                  type="positive", multi_line=True)
    for erro in erros:
        ui.notify(erro, type="negative", multi_line=True)
    painel.refresh()


def dialogo_referencias(p: s.Projeto) -> None:
    dlg, cartao = dialogo(f"Referências · {p.projeto}",
                          "Arquivos que complementam a documentação, como levantamento de requisitos e "
                          "mapeamento de tabelas.", 780)

    @ui.refreshable
    def lista() -> None:
        refs = s.referencias(p.pasta)
        if not refs:
            ui.label("Nenhum arquivo de referência.").classes("fdh-mudo")
            return
        for r in refs:
            with ui.element("div").classes("fdh-ref" + ("" if r.tipo else " sem-categoria")):
                ui.icon(ICONE_CATEGORIA.get(r.tipo, "help_outline")).style(
                    f"color: var({'--fdh-primary' if r.tipo else '--fdh-warn'})")
                ui.label(r.arquivo.name).classes("nome").tooltip(r.arquivo.name)  # nome longo: reticências

                def mudar(ev, ref=r) -> None:
                    if ev.value and ev.value != ref.tipo:
                        s.definir_categoria(p.pasta, ref, ev.value)
                        lista.refresh()
                        painel.refresh()
                ui.select(s.CATEGORIAS, value=r.tipo or None, label=None if r.tipo else "Escolha a categoria",
                          on_change=mudar).props("outlined dense options-dense")
                botao(icone="open_in_new", tipo="fantasma", dica="Abrir o arquivo",
                      on_click=lambda ref=r: os.startfile(ref.arquivo)).props("dense")
                botao(icone="delete_outline", tipo="fantasma", dica="Remover do projeto",
                      on_click=lambda ref=r: confirmar_remocao(ref)).props("dense")

    def confirmar_remocao(ref: s.Referencia) -> None:
        conf, c = dialogo("Remover referência?", f"{ref.arquivo.name} sai do projeto. O arquivo original "
                          "não é alterado.", 460)

        def remover_ref() -> None:
            s.remover_referencia(p.pasta, ref)
            conf.close()
            lista.refresh()
            painel.refresh()
        with c, ui.row().classes("w-full justify-end gap-2"):
            botao("Cancelar", on_click=conf.close, tipo="fantasma")
            botao("Remover", on_click=remover_ref, tipo="primario", icone="delete_outline")
        conf.open()

    with cartao:
        with ui.column().classes("w-full gap-2"):
            lista()
        with ui.row().classes("w-full justify-end gap-2"):
            botao("Abrir pasta", icone="folder_open", tipo="fantasma",
                  on_click=lambda: os.startfile(s.pasta_referencias(p.pasta)))
            botao("Fechar", on_click=dlg.close, tipo="primario")
    dlg.open()


# ---------------------------------------------------------------- diálogos
def dialogo(titulo: str, subtitulo: str = "", largura: int = 620):
    dlg = ui.dialog()
    with dlg, ui.card().classes(f"fdh-dialogo w-[{largura}px] max-w-full gap-3") as cartao:
        ui.label(titulo).classes("fdh-titulo-secao text-lg")
        if subtitulo:
            ui.label(subtitulo).classes("fdh-mudo")
    return dlg, cartao


def campo(rotulo_campo: str, **kw) -> ui.input:
    return ui.input(rotulo_campo, **kw).props("outlined dense").classes("w-full")


def dialogo_novo() -> None:
    cfg = s.carregar()
    f = ferramentas()
    ferr = {"v": "vscode" if f.tem_vscode else ("claude" if f.tem_claude else "vscode")}
    clientes = sorted({p.cliente for p in cfg.projetos})

    dlg, cartao = dialogo("Novo projeto", "Uma pasta por projeto (um workspace): dados e contexto de um cliente "
                          "nunca se misturam com os de outro. A conta do Fabric e o workspace são escolhidos na 1ª "
                          "conversa com o assistente.")
    with cartao:
        cliente = campo("Cliente *", autocomplete=clientes)
        projeto = campo("Projeto *")
        autor = campo("Autor do documento *", value=cfg.autor)
        with ui.row().classes("w-full items-center no-wrap gap-2"):
            pasta = campo("Pasta do projeto *").classes("flex-1")

            async def escolher() -> None:
                base = await escolher_pasta(cfg.pasta_padrao)
                if base:
                    pasta.value = str(Path(base) / s.nome_pasta(cliente.value or "Cliente", projeto.value or "Projeto"))
            botao(icone="folder_open", on_click=escolher, tipo="fantasma", dica="Escolher outro local")
        aviso = ui.label().classes("fdh-mudo").style("color: var(--fdh-warn)")

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

        rotulo("Onde você vai conversar com o assistente").classes("q-mt-sm")
        seletor_ferramenta(ferr)
        progresso = ui.label().classes("fdh-mudo").style("color: var(--fdh-primary)")

        async def criar() -> None:
            campos = {"Cliente": cliente.value, "Projeto": projeto.value, "Autor": autor.value, "Pasta": pasta.value}
            faltando = [k for k, v in campos.items() if not (v or "").strip()]
            if faltando:
                ui.notify("Preencha: " + ", ".join(faltando), type="warning")
                return
            if not ferramentas().disponivel(ferr["v"]):
                ui.notify("Instale o VS Code ou o Claude Desktop para continuar.", type="warning")
                return
            criar_btn.disable()
            try:
                p = await run.io_bound(
                    s.criar_projeto, s.carregar(), cliente=cliente.value.strip(), projeto=projeto.value.strip(),
                    autor=autor.value.strip(), pasta=pasta.value.strip(),
                    ferramenta=ferr["v"], progresso=lambda m: setattr(progresso, "text", m))
            except Exception as e:  # noqa: BLE001
                progresso.text = ""
                ui.notify(str(e), type="negative", multi_line=True, timeout=0, close_button=True)
                criar_btn.enable()
                return
            dlg.close()
            painel.refresh()
            ui.notify(f"Projeto criado em {p.pasta}", type="positive")
            await abrir_projeto(p, atualizar=False)

        with ui.row().classes("w-full justify-end gap-2"):
            botao("Cancelar", on_click=dlg.close, tipo="fantasma")
            criar_btn = botao("Criar e abrir", on_click=criar, tipo="primario", icone="add")
    dlg.open()


def dialogo_existente() -> None:
    f = ferramentas()
    ferr = {"v": "vscode" if f.tem_vscode else "claude"}
    dlg, cartao = dialogo("Adicionar pasta",
                          "Para uma pasta de projeto que não está na lista (outro computador, versão antiga…).", 560)
    with cartao:
        with ui.row().classes("w-full items-center no-wrap gap-2"):
            pasta = campo("Pasta do projeto").classes("flex-1")

            async def escolher() -> None:
                r = await escolher_pasta()
                if r:
                    pasta.value = r
            botao(icone="folder_open", on_click=escolher, tipo="fantasma", dica="Escolher pasta")
        rotulo("Onde você vai conversar com o assistente")
        seletor_ferramenta(ferr)

        def adicionar() -> None:
            try:
                s.adicionar_existente(s.carregar(), (pasta.value or "").strip(), ferr["v"])
            except Exception as e:  # noqa: BLE001
                ui.notify(str(e), type="negative")
                return
            dlg.close()
            painel.refresh()

        with ui.row().classes("w-full justify-end gap-2"):
            botao("Cancelar", on_click=dlg.close, tipo="fantasma")
            botao("Adicionar", on_click=adicionar, tipo="primario")
    dlg.open()


def dialogo_config() -> None:
    cfg = s.carregar()
    f = ferramentas()
    dlg, cartao = dialogo("Configurações", largura=600)
    with cartao:
        autor = campo("Autor padrão", value=cfg.autor)
        with ui.row().classes("w-full items-center no-wrap gap-2"):
            pasta = campo("Pasta padrão dos projetos", value=cfg.pasta_padrao).classes("flex-1")

            async def escolher() -> None:
                r = await escolher_pasta(cfg.pasta_padrao)
                if r:
                    pasta.value = r
            botao(icone="folder_open", on_click=escolher, tipo="fantasma", dica="Escolher pasta")

        rotulo("Ferramentas detectadas").classes("q-mt-sm")
        seletor_ferramenta({"v": ""})
        if f.tem_vscode and f.vscode_extensao is False:
            async def instalar() -> None:
                ok, msg = await run.io_bound(s.instalar_extensao, f)
                ui.notify("Extensão instalada." if ok else f"Falha: {msg}", type="positive" if ok else "negative")
                await detectar()
            botao("Instalar extensão Claude Code no VS Code", on_click=instalar, icone=marca.icone("vscode"))

        rotulo(f"Versão em uso: {s.versao_atual()}").classes("q-mt-sm")
        if s.MODO_DEV:
            ui.label("Modo desenvolvimento: o app roda do código-fonte e os projetos de teste recebem o assistente "
                     "direto da pasta de trabalho (inclusive o que não foi commitado).").classes("fdh-mudo")
        elif s.LEGADO:
            ui.label("Instalação antiga (v1). Rode o instalador de novo para passar ao formato atual.").classes(
                "fdh-mudo").style("color: var(--fdh-warn)")
        else:
            status = ui.label().classes("fdh-mudo")
            versoes = ui.select([], label="Instalar outra versão (voltar atrás)").props("outlined dense").classes("w-full")

            async def carregar_versoes() -> None:
                try:
                    versoes.options = await run.io_bound(s.versoes_publicadas)
                except Exception:  # noqa: BLE001
                    status.text = "Não foi possível consultar as versões no GitHub agora."
                versoes.update()

            async def instalar_v(tag: str | None) -> None:
                status.text = "Instalando…"
                ok, msg = await run.io_bound(s.instalar_versao, tag)
                status.text = msg if ok else f"Falha: {msg}"

            with ui.row().classes("gap-2"):
                botao("Atualizar para a mais nova", icone="system_update", on_click=lambda: instalar_v(None))
                botao("Instalar versão escolhida", icone="history",
                      on_click=lambda: instalar_v(versoes.value) if versoes.value else ui.notify("Escolha uma versão."))
            ui.timer(0.1, carregar_versoes, once=True)

        def salvar() -> None:
            c = s.carregar()
            c.autor, c.pasta_padrao = autor.value.strip(), pasta.value.strip() or c.pasta_padrao
            s.salvar(c)
            dlg.close()

        with ui.row().classes("w-full justify-end gap-2"):
            botao("Fechar", on_click=dlg.close, tipo="fantasma")
            botao("Salvar", on_click=salvar, tipo="primario")
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
    painel.refresh()


def trocar_ferramenta(p: s.Projeto, nova: str) -> None:
    cfg = s.carregar()
    for q in cfg.projetos:
        if q.id == p.id:
            q.ferramenta = nova
    s.salvar(cfg)
    painel.refresh()


def remover(p: s.Projeto) -> None:
    cfg = s.carregar()
    cfg.projetos = [q for q in cfg.projetos if q.id != p.id]
    s.salvar(cfg)
    painel.refresh()
    ui.notify("Removido da lista (a pasta não foi apagada).")


def revisar(p: s.Projeto, revisado: bool) -> None:
    s.marcar_revisado(s.carregar(), p.id, revisado)
    painel.refresh()
    ui.notify(f"{p.projeto}: marcado como pronto." if revisado else f"{p.projeto}: reaberto.",
              type="positive" if revisado else "info")


def dialogo_excluir(p: s.Projeto) -> None:
    """Apaga a pasta inteira; pede para digitar o nome do projeto, porque não dá para desfazer."""
    dlg, cartao = dialogo("Excluir projeto?", "A pasta do projeto será apagada com tudo o que está nela: documentos, "
                          "análise, inventário e referências. Não dá para desfazer (não vai para a Lixeira).", 520)
    with cartao:
        ui.label(p.pasta).classes("fdh-caminho")
        nome = p.projeto or p.cliente
        confirma = campo(f'Digite "{nome}" para confirmar')

        async def excluir() -> None:
            if (confirma.value or "").strip() != nome:
                ui.notify("O nome digitado não confere.", type="warning")
                return
            btn.disable()
            try:
                await run.io_bound(s.excluir_projeto, s.carregar(), p)
            except Exception as ex:  # noqa: BLE001
                ui.notify(str(ex), type="negative", multi_line=True, timeout=0, close_button=True)
                btn.enable()
                return
            dlg.close()
            painel.refresh()
            ui.notify(f"Projeto {nome} excluído.", type="positive")

        with ui.row().classes("w-full justify-end gap-2"):
            botao("Cancelar", on_click=dlg.close, tipo="fantasma")
            btn = botao("Excluir projeto", on_click=excluir, tipo="perigo", icone="delete_forever")
    dlg.open()


# ---------------------------------------------------------------- painel
@ui.refreshable
def painel() -> None:
    cfg = s.carregar()
    f = ferramentas()
    estados = {p.id: s.estado(p) for p in cfg.projetos}

    termo = FILTRO["texto"].lower()
    projetos = [p for p in cfg.projetos if termo in f"{p.cliente} {p.projeto} {p.pasta}".lower()]
    cabecalho_secao("Projetos", f"{len(projetos)} projeto(s) · {len({p.cliente for p in projetos})} cliente(s)")

    if not cfg.projetos:
        with ui.element("div").classes("fdh-cartao w-full"):
            with ui.column().classes("w-full items-center q-py-xl gap-2"):
                ui.icon("description", size="42px").style("color: var(--fdh-faint)")
                ui.label("Nenhum projeto ainda").classes("fdh-titulo-cartao")
                ui.label("Crie um projeto para cada documentação de cliente.").classes("fdh-mudo")
                botao("Novo projeto", icone="add", on_click=dialogo_novo, tipo="primario").classes("q-mt-sm")
        return
    if not projetos:
        ui.label("Nenhum projeto corresponde à busca.").classes("fdh-mudo")
        return

    versao_app = s.versao_atual()
    por_cliente: dict[str, list[s.Projeto]] = {}
    for p in sorted(projetos, key=lambda p: (p.cliente.lower(), p.projeto.lower())):
        por_cliente.setdefault(p.cliente, []).append(p)
    for cliente, itens in por_cliente.items():
        rotulo(f"{cliente} · {len(itens)}").classes("q-mt-sm")
        with ui.element("div").classes("grid w-full gap-3 grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3"):
            for p in itens:
                cartao_projeto(p, estados[p.id], f, versao_app)


def cartao_projeto(p: s.Projeto, e: s.Estado, f: s.Ferramentas, versao_app: str) -> None:
    with ui.element("div").classes("fdh-cartao interativo w-full q-pa-md column gap-3"):
        with ui.row().classes("w-full items-start justify-between no-wrap gap-2"):
            with ui.column().classes("gap-1 min-w-0 col"):
                ui.label(p.projeto or "(sem nome)").classes("fdh-titulo-cartao")
                ui.label(p.pasta).classes("fdh-caminho").tooltip(p.pasta)
            with ui.row().classes("items-center gap-1 no-wrap"):
                if not e.existe:
                    ui.label("Pasta não encontrada").classes("fdh-selo erro").tooltip(p.pasta)
                elif p.revisado_em:
                    ui.label("Pronto").classes("fdh-selo ok").tooltip(f"Marcado como revisado em {p.revisado_em}")
                with botao(icone="more_vert", tipo="fantasma").props("round dense").tooltip("Mais ações"):
                    with ui.menu().classes("fdh-menu") as menu:
                        if p.revisado_em:
                            item_menu(menu, "Reabrir (tirar de pronto)", "undo", lambda: revisar(p, False))
                        else:
                            item_menu(menu, "Marcar como revisado (pronto)", "task_alt", lambda: revisar(p, True))
                        item_menu(menu, "Abrir pasta do projeto", "folder_open",
                                  lambda: os.startfile(p.pasta) if e.existe else None)
                        ui.separator()
                        item_menu(menu, "Remover da lista", "playlist_remove", lambda: remover(p))
                        item_menu(menu, "Excluir projeto…", "delete_forever", lambda: dialogo_excluir(p), perigo=True)

        with ui.element("div").classes("grid grid-cols-2 gap-x-4 gap-y-2"):
            for titulo, valor in (("Workspace", e.workspace or "Escolhido na 1ª conversa"),
                                  ("Conta do Fabric", e.conta or "Confirmada na 1ª conversa"),
                                  ("Assistente", (e.versao_harness or "—") + ("" if not e.versao_harness or
                                                  e.versao_harness == versao_app else f" → {versao_app} ao abrir")),
                                  ("Último acesso", p.ultimo_acesso or "—")):
                with ui.column().classes("gap-0 min-w-0"):
                    rotulo(titulo)
                    ui.label(valor).classes("fdh-texto ellipsis").tooltip(valor)

        with ui.column().classes("w-full gap-1"):
            rotulo("Documento")
            botao_documento(e)

        with ui.column().classes("w-full gap-1"):
            rotulo(f"Referências · {len(e.referencias)}" if e.referencias else "Referências")
            botao_referencias(p, e)

        with ui.column().classes("w-full gap-1"):
            rotulo("Abrir no assistente")
            escolha = {"v": p.ferramenta}
            seletor_ferramenta(escolha, ao_mudar=lambda c: trocar_ferramenta(p, c), compacto=True)
            pode = e.existe and f.disponivel(p.ferramenta)
            botao(f"Abrir no {s.FERRAMENTAS[p.ferramenta]}", icone=marca.icone(p.ferramenta),
                  on_click=lambda: abrir_projeto(p), tipo="primario", desabilitado=not pode,
                  dica=None if pode else ("Pasta do projeto não encontrada." if not e.existe
                                          else f"{s.FERRAMENTAS[p.ferramenta]} não está instalado.")).classes("w-full")


# ---------------------------------------------------------------- página
def item_menu(menu: ui.menu, texto: str, icone: str, on_click, perigo: bool = False) -> None:
    def clicar():
        menu.close()
        return on_click()
    with ui.item(on_click=clicar).props("clickable").classes("fdh-perigo" if perigo else ""):
        with ui.item_section().props("avatar"):
            ui.icon(icone)
        with ui.item_section():
            ui.item_label(texto)


def item_nav(texto: str, icone: str, on_click=None, ativo: bool = False) -> None:
    with ui.element("div").classes("fdh-nav" + (" ativo" if ativo else "")).props('role="button" tabindex="0"') as nav:
        ui.icon(icone)
        ui.label(texto)
    if on_click:
        nav.on("click", on_click)
        nav.on("keydown.enter", on_click)


@ui.page("/")
async def pagina() -> None:
    ui.add_head_html(marca.FONTES)
    ui.add_css(marca.CSS)
    ui.colors(primary=marca.AZUL)
    ui.dark_mode(True)  # tema único: escuro

    # Menu lateral fixo: sempre aberto, sem botão de recolher (behavior=desktop ignora a largura da janela)
    with ui.left_drawer(value=True, bordered=False).props("width=240 behavior=desktop persistent no-swipe-close") \
            .classes("fdh-drawer q-pa-sm q-pt-md"):
        item_nav("Projetos", "folder_copy", ativo=True)
        ui.label("Ações").classes("fdh-secao-nav")
        item_nav("Novo projeto", "add_circle_outline", dialogo_novo)
        item_nav("Adicionar pasta", "create_new_folder", dialogo_existente)
        item_nav("Configurações", "settings", dialogo_config)

    with ui.header().classes("fdh-header items-center justify-between q-px-md").style("height: 56px"):
        with ui.row().classes("items-center gap-3 no-wrap"):
            ui.html(f'<span class="fdh-logo">{marca.LOGO_SVG}<span class="nome">Fabric <span>Doc Helper</span></span></span>',
                    sanitize=False)
            ui.label(s.versao_atual()).classes("fdh-selo neutro")
        botao("Novo projeto", icone="add", on_click=dialogo_novo, tipo="primario").classes("gt-xs")

    with ui.column().classes("w-full max-w-[1400px] mx-auto q-pa-md gap-4"):
        if s.MODO_DEV:
            ui.label(f"DESENVOLVIMENTO · código-fonte em {s.RAIZ} · projetos e lista separados do uso real "
                     f"(pasta padrão {s.PASTA_PADRAO})").classes("fdh-faixa w-full")
        elif s.LEGADO:
            ui.label("Instalação antiga (v1). Rode o instalador de novo para passar ao formato atual "
                     "(seus projetos e configurações são mantidos).").classes("fdh-faixa w-full")
        elif s.NO_LOCAL_ANTIGO:
            faixa = ui.label(f"O app está mudando para {s.CASA} (pasta com o app, os projetos novos e a lista). "
                             "Aguarde…").classes("fdh-faixa w-full")
        ui.input(placeholder="Buscar por cliente, projeto ou pasta",
                 on_change=lambda ev: (FILTRO.update(texto=ev.value or ""), painel.refresh())
                 ).props("outlined dense clearable").classes("w-full fdh-busca")
        painel()
    ui.timer(0.1, detectar, once=True)  # detecção roda depois que a página aparece
    if AVISO_MIGRACAO:
        ui.notify(AVISO_MIGRACAO, type="info", multi_line=True, timeout=15000, close_button=True)
    if s.NO_LOCAL_ANTIGO:
        async def mudar() -> None:
            ok, msg = await run.io_bound(s.mudar_de_local)
            faixa.text = (f"Pronto: o app agora fica em {s.CASA}. Feche e abra pelo atalho." if ok
                          else f"Não foi possível mudar o app de lugar: {msg} Rode o instalador de novo.")
        ui.timer(0.5, mudar, once=True)
    else:
        ui.timer(5.0, lambda: run.io_bound(s.remover_instalacao_antiga), once=True)
        ui.timer(1.0, verificar_versao, once=True)


async def verificar_versao() -> None:
    """Produção: avisa quando há versão publicada mais nova, com as novidades do CHANGELOG."""
    tag = await run.io_bound(s.atualizacao_disponivel)
    if not tag:
        return
    notas = await run.io_bound(s.novidades, tag)
    dlg, cartao = dialogo(f"Nova versão disponível: {tag}", largura=560)
    with cartao:
        ui.markdown(notas).classes("fdh-texto max-h-80 overflow-auto")
        status = ui.label().classes("fdh-mudo")

        async def atualizar() -> None:
            status.text = "Instalando…"
            ok, msg = await run.io_bound(s.instalar_versao, tag)
            status.text = msg if ok else f"Falha: {msg}"

        with ui.row().classes("w-full justify-end gap-2"):
            botao("Depois", on_click=dlg.close, tipo="fantasma")
            botao("Atualizar agora", icone="system_update", on_click=atualizar, tipo="primario")
    dlg.open()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Fabric Doc Helper" + (" (dev)" if s.MODO_DEV else ""), native=NATIVO,
           host="127.0.0.1",  # só este computador
           window_size=(1280, 820) if NATIVO else None,
           reload=False, show=not NATIVO and "--sem-abrir" not in sys.argv, port=None if NATIVO else 8765, favicon=marca.LOGO_SVG)
