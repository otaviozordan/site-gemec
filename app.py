"""App de administracao do site do GEMEC (duplo clique em "Abrir o app.bat").

Aba "Conteudo do site": tudo o que o painel do WordPress controla (membros,
linhas de pesquisa, publicacoes, oportunidades, parceiros e paginas), lido do
site ao abrir o app e gravado direto la (scripts/conteudo.py).
As outras abas mostram as ultimas atualizacoes do Lattes (o que cada envio ao
site mudou, os curriculos e as publicacoes) e rodam as tarefas do main.py,
inclusive a atualizacao de um membro so. So usa a biblioteca padrao (tkinter);
o Pillow, se existir, mostra as fotos em JPEG.
"""
import base64
import datetime
import tempfile
import os
import queue
import re
import subprocess
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "scripts"))
import historico  # noqa: E402
import conteudo  # noqa: E402
import acesso  # noqa: E402
import busca  # noqa: E402

CACHE = os.path.join(AQUI, "scripts", "lattes", "cache")
MARCA_SEMANAL = os.path.join(AQUI, "scripts", "lattes", "ultima_semanal.txt")
LOGS = os.path.join(historico.PASTA, "registros")
MARCA = os.path.join(AQUI, "marca")
SITE = "https://gemec.unifei.edu.br"

# Identidade visual do site (tema gemec, style.css)
TINTA = "#0E1B2C"
AZUL = "#0B4F96"
MARINHO = "#003A70"
AZUL_CLARO = "#E8EFF8"
VERMELHO = "#E0352B"
ARDOSIA = "#5B6878"
NEVOA = "#F5F7FA"
BORDA = "#D9DEE5"
VERDE = "#1E7B45"
FONTE = "Segoe UI"  # Inter, se estiver instalada (_estilo)

# tarefa do main.py -> (rotulo do botao, confirmar antes?, dica)
TAREFAS = [
    ("completo", "Atualização completa", True, "Baixa o CV de todos, gera o relatório e refaz o site (uns 15 minutos)."),
    ("novos", "Só membros novos", False, "Baixa só quem foi cadastrado no site e ainda não tem CV."),
    ("perfis", "Completar perfis", False, "Preenche campos vazios dos perfis com o que está no Lattes."),
    ("faltam", "Ver quem falta", False, "Lista os membros sem CV baixado."),
    ("abrir", "Abrir CVs que faltam", False, "Abre no navegador os CVs que faltam, para salvar à mão."),
]
CAT_ORDEM = [k for k, _r in conteudo.CATEGORIAS]
FEMININOS = ("linha de pesquisa", "publicação", "oportunidade", "página")


def novo_de(singular):
    return ("Nova " if singular in FEMININOS else "Novo ") + singular


def python_console():
    """python.exe ao lado do pythonw.exe: a tarefa precisa de saida de texto."""
    exe = sys.executable
    if os.path.basename(exe).lower() == "pythonw.exe":
        alt = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.exists(alt):
            return alt
    return exe


def baixar_cv(lid):
    """Baixa um CV para o cache pelo main.py (Chrome do scriptLattes); roda fora da janela."""
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    r = subprocess.run([python_console(), "-u", os.path.join(AQUI, "main.py"), "cv", lid], cwd=AQUI, env=env,
                       capture_output=True, stdin=subprocess.DEVNULL, timeout=900,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not os.path.exists(os.path.join(CACHE, lid)):
        fim = r.stdout.decode("utf-8", "replace").strip().splitlines()[-3:]
        raise conteudo.ErroSite("Não deu para baixar o CV do Lattes (o Lattes pode ter bloqueado o robô; tente de novo "
                                "ou salve o CV à mão pela aba Registro → Abrir CVs que faltam).\n\n" + "\n".join(fim))


def quando(iso):
    try:
        d = datetime.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or ""
    return d.strftime("%d/%m/%Y %H:%M")


def ha_quanto(d):
    dias = (datetime.date.today() - d).days
    if dias <= 0:
        return "hoje"
    if dias == 1:
        return "ontem"
    return "há %d dias" % dias


def dmy(iso):
    """AAAA-MM-DD -> dd/mm/aaaa (o resto passa como esta)."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})$", iso or "")
    return "%s/%s/%s" % (m.group(3), m.group(2), m.group(1)) if m else (iso or "")


def imagem(dados=None, caminho=None, lado=96):
    """PhotoImage de bytes ou arquivo; JPEG so com o Pillow. None se nao der."""
    try:
        from PIL import Image, ImageTk
        import io
        im = Image.open(io.BytesIO(dados) if dados else caminho)
        im.thumbnail((lado, lado))
        return ImageTk.PhotoImage(im)
    except Exception:  # noqa: BLE001
        pass
    try:
        im = tk.PhotoImage(data=base64.b64encode(dados).decode()) if dados else tk.PhotoImage(file=caminho)
        f = max(1, -(-max(im.width(), im.height()) // lado))
        return im.subsample(f) if f > 1 else im
    except Exception:  # noqa: BLE001
        return None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GEMEC · Painel do site")
        self.geometry("1280x800")
        self.minsize(980, 620)
        self.configure(bg=NEVOA)
        try:
            self.iconbitmap(default=os.path.join(MARCA, "gemec.ico"))
        except tk.TclError:
            pass
        try:  # PNGs tambem: a barra de tarefas pega o tamanho grande daqui
            self._icones = [tk.PhotoImage(file=os.path.join(MARCA, "simbolo-%d.png" % n)) for n in (256, 64, 48, 32, 16)]
            self.iconphoto(True, *self._icones)
        except tk.TclError:
            pass
        self.proc = None
        self.fila = queue.Queue()   # saida da tarefa
        self.ui = queue.Queue()     # respostas do site para a janela
        self.log_arq = None
        self.hist = []
        self.site = {}
        self.dados = {}             # tipo -> itens lidos do site
        self.tipo = "membros"
        self.atual = None           # item no formulario (None = novo)
        self.snap = None            # formulario como foi carregado (para saber se mudou)
        self.foto_id = 0
        self.foto_nova = None
        self._ocupado = 0
        self._ignorar_sel = False
        self._estilo()
        self._montar()
        self.recarregar()
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        self.bind_all("<MouseWheel>", self._rodinha)
        self.after(100, self._ler_fila)
        self.after(300, lambda: self.sincronizar() if acesso.tem_login() else self.pedir_login(self.sincronizar))

    # ------------------------------------------------------------------ visual
    def _estilo(self):
        global FONTE
        if "Inter" in tkfont.families(self):
            FONTE = "Inter"
        st = ttk.Style(self)
        st.theme_use("clam")
        base = (FONTE, 10)
        negrito = (FONTE, 10, "bold")
        st.configure(".", font=base, background=NEVOA, foreground=TINTA, bordercolor=BORDA,
                     lightcolor=NEVOA, darkcolor=NEVOA, troughcolor=NEVOA, focuscolor=AZUL)
        st.configure("TFrame", background=NEVOA)
        st.configure("Card.TFrame", background="white")
        st.configure("TLabel", background=NEVOA, foreground=TINTA)
        st.configure("Card.TLabel", background="white")
        st.configure("H1.TLabel", background="white", foreground=MARINHO, font=(FONTE, 15, "bold"))
        st.configure("Campo.TLabel", background="white", foreground=TINTA, font=negrito)
        st.configure("Dica.TLabel", background="white", foreground=ARDOSIA, font=(FONTE, 9))
        st.configure("Cinza.TLabel", background=NEVOA, foreground=ARDOSIA)
        st.configure("Num.TLabel", background="white", foreground=MARINHO, font=(FONTE, 20, "bold"))
        st.configure("Rot.TLabel", background="white", foreground=ARDOSIA, font=(FONTE, 9))

        st.configure("TButton", padding=(12, 6), background="white", foreground=TINTA, bordercolor=BORDA,
                     lightcolor="white", darkcolor="white", relief="flat")
        st.map("TButton", background=[("disabled", NEVOA), ("pressed", AZUL_CLARO), ("active", AZUL_CLARO)],
               foreground=[("disabled", "#9AA4B2")])
        st.configure("Acao.TButton")
        st.configure("Principal.TButton", background=AZUL, foreground="white", bordercolor=AZUL,
                     lightcolor=AZUL, darkcolor=AZUL, font=negrito)
        st.map("Principal.TButton", background=[("disabled", "#9DB5D3"), ("pressed", MARINHO), ("active", MARINHO)],
               lightcolor=[("active", MARINHO)], darkcolor=[("active", MARINHO)], foreground=[("disabled", "white")])
        st.configure("Perigo.TButton", foreground=VERMELHO)
        st.map("Perigo.TButton", background=[("active", "#FDECEA")])
        st.configure("Tipo.Toolbutton", padding=(14, 7), background=NEVOA, foreground=ARDOSIA, font=negrito, relief="flat")
        st.map("Tipo.Toolbutton", background=[("selected", AZUL), ("active", AZUL_CLARO)],
               foreground=[("selected", "white"), ("active", MARINHO)])

        st.configure("TNotebook", background=NEVOA, borderwidth=0, tabmargins=(0, 0, 0, 0))
        st.configure("TNotebook.Tab", padding=(16, 8), background=NEVOA, foreground=ARDOSIA, bordercolor=BORDA,
                     lightcolor=NEVOA, font=base)
        st.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", AZUL)],
               font=[("selected", negrito)])
        st.configure("Treeview", background="white", fieldbackground="white", foreground=TINTA, rowheight=28,
                     bordercolor=BORDA, font=base)
        st.map("Treeview", background=[("selected", AZUL_CLARO)], foreground=[("selected", MARINHO)])
        st.configure("Treeview.Heading", background=NEVOA, foreground=ARDOSIA, font=negrito, relief="flat",
                     bordercolor=BORDA, lightcolor=NEVOA, darkcolor=NEVOA)
        st.map("Treeview.Heading", background=[("active", AZUL_CLARO)])
        for w in ("TEntry", "TCombobox", "TSpinbox"):
            st.configure(w, fieldbackground="white", bordercolor=BORDA, lightcolor="white", darkcolor="white",
                         arrowcolor=ARDOSIA, padding=4)
            st.map(w, bordercolor=[("focus", AZUL)], lightcolor=[("focus", AZUL)])
        st.map("TCombobox", fieldbackground=[("readonly", "white")], selectbackground=[("readonly", "white")],
               selectforeground=[("readonly", TINTA)])
        st.configure("Card.TCheckbutton", background="white", indicatorbackground="white")
        st.configure("TScrollbar", background=NEVOA, troughcolor="white", bordercolor="white", arrowcolor=ARDOSIA,
                     lightcolor=NEVOA, darkcolor=NEVOA)
        st.configure("Horizontal.TProgressbar", background=VERMELHO, troughcolor=AZUL_CLARO, bordercolor=AZUL_CLARO,
                     lightcolor=VERMELHO, darkcolor=VERMELHO)
        st.configure("TPanedwindow", background=NEVOA)
        self.option_add("*TCombobox*Listbox.font", base)
        self.option_add("*TCombobox*Listbox.selectBackground", AZUL_CLARO)
        self.option_add("*TCombobox*Listbox.selectForeground", MARINHO)

    def _link(self, pai, texto, url=None, comando=None, bg="white"):
        l = tk.Label(pai, text=texto, bg=bg, fg=AZUL, cursor="hand2", font=(FONTE, 10))
        l.bind("<Button-1>", lambda _e: comando() if comando else webbrowser.open(url))
        l.bind("<Enter>", lambda _e: l.configure(font=(FONTE, 10, "underline")))
        l.bind("<Leave>", lambda _e: l.configure(font=(FONTE, 10)))
        return l

    def _montar(self):
        # Cabecalho como o do site: logo sobre branco e a faixa vermelha e azul
        topo = tk.Frame(self, bg="white")
        topo.pack(fill="x")
        try:
            self.logo = tk.PhotoImage(file=os.path.join(MARCA, "logo-40.png"))
            tk.Label(topo, image=self.logo, bg="white").pack(side="left", padx=(22, 16), pady=12)
        except tk.TclError:
            tk.Label(topo, text="GEMEC", bg="white", fg=TINTA, font=(FONTE, 20, "bold")).pack(side="left", padx=(22, 16), pady=12)
        tk.Frame(topo, bg=BORDA, width=1, height=36).pack(side="left", pady=14)
        nome = tk.Frame(topo, bg="white")
        nome.pack(side="left", padx=16)
        tk.Label(nome, text="Painel do site", bg="white", fg=TINTA, font=(FONTE, 13, "bold")).pack(anchor="w")
        tk.Label(nome, text="Grupo de Estudos em Mecânica Experimental e Computacional · UNIFEI", bg="white",
                 fg=ARDOSIA, font=(FONTE, 9)).pack(anchor="w")
        self._link(topo, "Abrir o site ↗", SITE).pack(side="right", padx=(10, 22))
        self._link(topo, "Painel do WordPress ↗", SITE + "/wp-admin/").pack(side="right", padx=10)
        self._link(topo, "⚙ Configurações", comando=self.configuracoes).pack(side="right", padx=10)
        faixa = tk.Frame(self, bg=AZUL, height=4)
        faixa.pack(fill="x")
        tk.Frame(faixa, bg=VERMELHO).place(relx=0, rely=0, relwidth=0.24, relheight=1)

        # Cartoes de numeros
        self.cartoes = ttk.Frame(self)
        self.cartoes.pack(fill="x", padx=18, pady=(14, 4))
        self.num = {}
        for k, rot in (("ultima", "última atualização completa"), ("envio", "último envio ao site"),
                       ("membros", "membros no site"), ("pubs", "publicações no site")):
            f = tk.Frame(self.cartoes, bg="white", highlightthickness=1, highlightbackground=BORDA)
            f.pack(side="left", padx=(0, 12))
            tk.Frame(f, bg=VERMELHO, width=3).pack(side="left", fill="y")
            dentro = ttk.Frame(f, style="Card.TFrame", padding=(14, 8, 22, 8))
            dentro.pack(side="left")
            self.num[k] = ttk.Label(dentro, text="—", style="Num.TLabel")
            self.num[k].pack(anchor="w")
            self.num[k + "_r"] = ttk.Label(dentro, text=rot, style="Rot.TLabel")
            self.num[k + "_r"].pack(anchor="w")

        # Acoes
        acoes = ttk.Frame(self)
        acoes.pack(fill="x", padx=18, pady=(10, 10))
        self.botoes = []
        for cmd, rot, confirmar, dica in TAREFAS:
            b = ttk.Button(acoes, text=rot, style="Principal.TButton" if cmd == "completo" else "Acao.TButton",
                           command=lambda c=cmd, r=rot, q=confirmar, d=dica: self.rodar(c, r, q, d))
            b.pack(side="left", padx=(0, 8))
            Dica(b, dica)
            self.botoes.append(b)
            if cmd == "completo":
                b = ttk.Button(acoes, text="Atualizar um membro…", style="Acao.TButton", command=self.escolher_membro)
                b.pack(side="left", padx=(0, 8))
                Dica(b, "Escolha um membro: baixa só o CV dele no Lattes e refaz o site com ele (uns 5 minutos).")
                self.botoes.append(b)
        self.parar_b = ttk.Button(acoes, text="Parar", style="Perigo.TButton", command=self.parar, state="disabled")
        self.parar_b.pack(side="right")
        self.barra = ttk.Progressbar(acoes, mode="indeterminate", length=140)
        self.status = ttk.Label(acoes, text="", style="Cinza.TLabel")
        self.status.pack(side="right", padx=8)

        self.abas = ttk.Notebook(self)
        self.abas.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        self._aba_conteudo()
        self._aba_historico()
        self._aba_curriculos()
        self._aba_publicacoes()
        self._aba_registro()

    def _arvore(self, pai, colunas, larguras, alto=None, selecao="browse"):
        f = ttk.Frame(pai)
        t = ttk.Treeview(f, columns=[c for c, _ in colunas], show="headings", height=alto or 10, selectmode=selecao)
        self._colunas(t, colunas, larguras)
        sb = ttk.Scrollbar(f, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        t.tag_configure("recente", foreground=VERDE)
        t.tag_configure("apagado", foreground="#8A94A3")
        return f, t

    def _colunas(self, t, colunas, larguras):
        t.configure(columns=[c for c, _ in colunas])
        for (c, rot), w in zip(colunas, larguras):
            t.heading(c, text=rot, command=lambda c=c, t=t: self._ordenar(t, c))
            t.column(c, width=w, stretch=w > 200, anchor="w")

    def _ordenar(self, t, col, inverso=None):
        inverso = not getattr(t, "_inv_" + col, False) if inverso is None else inverso
        itens = [(t.set(i, col), i) for i in t.get_children("")]

        def chave(x):  # datas dd/mm/aaaa pela data; numeros pelo valor
            v = x[0]
            return historico.data_iso(v) or (v.zfill(8) if v.isdigit() else historico_chave(v))
        itens.sort(key=chave, reverse=inverso)
        for n, (_v, i) in enumerate(itens):
            t.move(i, "", n)
        setattr(t, "_inv_" + col, inverso)

    def _rolavel(self, pai):
        """Canvas com um Frame dentro (o formulario), rolado pela rodinha."""
        can = tk.Canvas(pai, bg="white", highlightthickness=0)
        sb = ttk.Scrollbar(pai, orient="vertical", command=can.yview)
        dentro = tk.Frame(can, bg="white")
        jan = can.create_window(0, 0, window=dentro, anchor="nw")
        dentro.bind("<Configure>", lambda _e: can.configure(scrollregion=can.bbox("all")))
        can.bind("<Configure>", lambda e: can.itemconfigure(jan, width=e.width))
        can.configure(yscrollcommand=sb.set)
        self._rolaveis = getattr(self, "_rolaveis", []) + [can]
        return can, sb, dentro

    def _rodinha(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        if w is None or isinstance(w, (tk.Text, tk.Listbox, ttk.Treeview)):
            return
        for can in getattr(self, "_rolaveis", []):
            if str(w).startswith(str(can)):
                can.yview_scroll(int(-e.delta / 120), "units")
                return

    # ------------------------------------------------------------ aba conteudo
    def _aba_conteudo(self):
        aba = ttk.Frame(self.abas, padding=10)
        self.abas.add(aba, text="Conteúdo do site")
        self.aba_conteudo = aba

        tipos = ttk.Frame(aba)
        tipos.pack(fill="x", pady=(0, 10))
        self.tipo_var = tk.StringVar(value=self.tipo)
        for k, t in conteudo.TIPOS.items():
            ttk.Radiobutton(tipos, text=t["rotulo"], value=k, variable=self.tipo_var, style="Tipo.Toolbutton",
                            command=self.trocar_tipo).pack(side="left", padx=(0, 4))
        self.novo_b = ttk.Button(tipos, text="+ Novo", style="Principal.TButton", command=self.novo)
        self.novo_b.pack(side="right")
        ttk.Button(tipos, text="⟳ Sincronizar", style="Acao.TButton", command=self.sincronizar).pack(side="right", padx=8)

        linha = ttk.Frame(aba)
        linha.pack(fill="x", pady=(0, 8))
        ttk.Label(linha, text="Buscar:").pack(side="left")
        self.c_busca = tk.StringVar()
        ttk.Entry(linha, textvariable=self.c_busca, width=34).pack(side="left", padx=6)
        self.c_busca.trace_add("write", lambda *_: self.preencher_lista())
        ttk.Label(linha, text="Mostrar:").pack(side="left", padx=(12, 4))
        self.c_filtro = ttk.Combobox(linha, state="readonly", width=24)
        self.c_filtro.pack(side="left")
        self.c_filtro.bind("<<ComboboxSelected>>", lambda _e: self.preencher_lista())
        self.c_conta = ttk.Label(linha, text="", style="Cinza.TLabel")
        self.c_conta.pack(side="left", padx=10)
        self.c_status = ttk.Label(linha, text="", style="Cinza.TLabel")
        self.c_status.pack(side="right")

        pan = ttk.PanedWindow(aba, orient="horizontal")
        pan.pack(fill="both", expand=True)
        f, self.t_cont = self._arvore(pan, [("titulo", "Nome")], [300], selecao="extended")
        self.t_cont.bind("<<TreeviewSelect>>", self._selecionou)
        self.t_cont.bind("<Delete>", lambda _e: self.lixeira())
        pan.add(f, weight=3)

        self.direita = tk.Frame(pan, bg="white", highlightthickness=1, highlightbackground=BORDA)
        pan.add(self.direita, weight=4)
        cab = tk.Frame(self.direita, bg="white")
        cab.pack(fill="x", padx=22, pady=(16, 4))
        self.painel_b = ttk.Button(cab, text="WordPress ↗", command=self.abrir_painel)
        self.painel_b.pack(side="right", anchor="n")
        self.ver_b = ttk.Button(cab, text="Ver no site ↗", command=self.ver_no_site)
        self.ver_b.pack(side="right", anchor="n", padx=6)
        self.f_titulo = ttk.Label(cab, text="", style="H1.TLabel")
        self.f_titulo.pack(side="top", anchor="w")
        self.f_sub = ttk.Label(cab, text="", style="Dica.TLabel", wraplength=420, justify="left")
        self.f_sub.pack(side="top", anchor="w", pady=(2, 0))
        tk.Frame(self.direita, bg=BORDA, height=1).pack(fill="x", pady=(8, 0))

        # Rodape com os botoes do formulario
        self.f_barra = tk.Frame(self.direita, bg=NEVOA)
        self.f_barra.pack(side="bottom", fill="x")
        self.salvar_b = ttk.Button(self.f_barra, text="Salvar no site", style="Principal.TButton", command=self.salvar)
        self.salvar_b.pack(side="left", padx=(16, 6), pady=10)
        self.desfazer_b = ttk.Button(self.f_barra, text="Desfazer", command=lambda: self._encher_form(self.atual))
        self.desfazer_b.pack(side="left", pady=10)
        self.lixo_b = ttk.Button(self.f_barra, text="Lixeira", style="Perigo.TButton", command=self.lixeira)
        self.lixo_b.pack(side="right", padx=(6, 16), pady=10)

        self.corpo = tk.Frame(self.direita, bg="white")
        self.corpo.pack(fill="both", expand=True)
        self.f_rol = tk.Frame(self.corpo, bg="white")
        can, sb, self.f_dentro = self._rolavel(self.f_rol)
        can.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.v_dentro = tk.Frame(self.corpo, bg="white")   # varios selecionados
        self.vazio = tk.Frame(self.corpo, bg="white")      # nada selecionado
        self.vazio_txt = ttk.Label(self.vazio, text="", style="Dica.TLabel", wraplength=480, justify="left")
        self.vazio_txt.pack(anchor="nw", padx=22, pady=18)
        self.trocar_tipo(perguntar=False)

    def _painel(self, qual):
        for f in (self.f_rol, self.v_dentro, self.vazio):
            f.pack_forget()
        {"form": self.f_rol, "varios": self.v_dentro, "vazio": self.vazio}[qual].pack(fill="both", expand=True)
        estado = "normal" if qual == "form" else "disabled"
        for b in (self.salvar_b, self.desfazer_b, self.ver_b, self.painel_b):
            b.configure(state=estado)
        self.lixo_b.configure(state="normal" if qual == "varios" or (qual == "form" and self.atual) else "disabled")
        if qual == "form" and not self.atual:
            self.ver_b.configure(state="disabled")
            self.painel_b.configure(state="disabled")
        if qual == "vazio":
            t = conteudo.TIPOS[self.tipo]
            self.f_titulo.configure(text=t["rotulo"])
            self.f_sub.configure(text=t["dica"])
            self.vazio_txt.configure(text="Escolha um item na lista para editar" +
                                     (", ou clique em + Novo." if t.get("novo", True) else ".") +
                                     "\nCom Ctrl ou Shift dá para selecionar vários e mudar todos de uma vez.")

    # --- dados do site
    def sincronizar(self):
        """Le do site todos os tipos de conteudo (ao abrir o app e no botao)."""
        if self._sujo() and not messagebox.askyesno("Sincronizar", "Descartar as alterações não salvas?", parent=self):
            return
        tipos = list(conteudo.TIPOS)

        def trabalho():
            return {k: conteudo.listar(k) for k in tipos}

        def depois(d):
            self.dados = d
            self.atualizado = datetime.datetime.now()
            self.atual, self.snap = None, None
            self.preencher_lista()
            self._painel("vazio")
            self._numeros_site()
            self.c_status.configure(text="Sincronizado às %s" % self.atualizado.strftime("%H:%M"))
        self.em_fundo(trabalho, depois, "Sincronizando com o site…")

    def em_fundo(self, trabalho, depois=None, msg="Carregando…"):
        """Roda trabalho() fora da janela; depois(resultado) volta para ela."""
        self._ocupado += 1
        self.c_status.configure(text=msg, foreground=ARDOSIA)
        self.configure(cursor="watch")

        def corre():
            try:
                r = trabalho()
            except BaseException as e:  # noqa: BLE001 - o gm sai com SystemExit
                self.ui.put(self._fim_fundo)
                self.ui.put(lambda e=e: self._falhou(e))
                return
            self.ui.put(self._fim_fundo)
            if depois:
                self.ui.put(lambda: depois(r))
        threading.Thread(target=corre, daemon=True).start()

    def _fim_fundo(self):
        self._ocupado -= 1
        if not self._ocupado:
            self.configure(cursor="")
            self.c_status.configure(text="")

    def _falhou(self, e):
        self.c_status.configure(text="Falhou: " + (str(e) or type(e).__name__)[:80], foreground=VERMELHO)
        messagebox.showerror("Site do GEMEC", str(e) or type(e).__name__, parent=self)

    def _numeros_site(self):
        if "membros" in self.dados:
            n = sum(1 for m in self.dados["membros"] if m["situacao"] == "publish")
            self.num["membros"].config(text=str(n))
            self.num["membros_r"].config(text="membros no site (%d ocultos)" % sum(1 for m in self.dados["membros"] if m["situacao"] == "private"))
        if "publicacoes" in self.dados:
            n = sum(1 for p in self.dados["publicacoes"] if p["situacao"] == "publish" and p["meta"].get("gemec_oculta") != "1")
            self.num["pubs"].config(text=str(n))
            self.num["pubs_r"].config(text="publicações no site (agora)")

    # --- lista
    def trocar_tipo(self, perguntar=True):
        novo = self.tipo_var.get()
        if perguntar and self._sujo() and not messagebox.askyesno("Alterações não salvas", "Descartar as alterações em “%s”?" % self.w_titulo.get(), parent=self):
            self.tipo_var.set(self.tipo)
            return
        self.tipo = novo
        t = conteudo.TIPOS[novo]
        self._colunas(self.t_cont, [(c, r) for c, r, _w in t["colunas"]], [w for _c, _r, w in t["colunas"]])
        self.filtros = [("", "Todos")] + t["situacoes"] + ([("oculta", "Ocultas do site")] if novo == "publicacoes" else [])
        self.c_filtro.configure(values=[r for _v, r in self.filtros])
        self.c_filtro.current(0)
        self.novo_b.configure(text="+ " + novo_de(t["singular"]).replace(" de pesquisa", "") if t.get("novo", True) else "+ Novo",
                              state="normal" if t.get("novo", True) else "disabled")
        self.atual, self.snap = None, None
        self._montar_form()
        self.preencher_lista()
        self._painel("vazio")

    def _valor_col(self, it, col):
        meta = it["meta"]
        if col == "titulo":
            return it["titulo"]
        if col == "situacao":
            return dict(conteudo.TIPOS[self.tipo]["situacoes"]).get(it["situacao"], it["situacao"])
        if col == "ordem":
            return str(it["ordem"])
        if col == "slug":
            return "/%s/" % it["slug"]
        if col == "oculta":
            return "Oculta" if meta.get("gemec_oculta") == "1" else "Sim"
        if col == "aberta":
            hoje = datetime.date.today().isoformat()
            if meta.get("gemec_prazo") and meta["gemec_prazo"] < hoje:
                return "Encerradas"
            if meta.get("gemec_inicio") and meta["gemec_inicio"] > hoje:
                return "A partir de " + dmy(meta["gemec_inicio"])[:5]
            return "Abertas"
        if col in ("gemec_data", "gemec_prazo"):
            return dmy(meta.get(col, ""))
        return conteudo.rotulo_de(self.tipo, col, meta.get(col, ""))

    def _ordem_padrao(self, it):
        if self.tipo == "membros":
            c = it["meta"].get("gemec_categoria", "")
            return (CAT_ORDEM.index(c) if c in CAT_ORDEM else 99, it["meta"].get("gemec_destaque") != "1",
                    it["ordem"], historico_chave(it["titulo"]))
        return (it["ordem"], historico_chave(it["titulo"]))

    def preencher_lista(self):
        itens = self.dados.get(self.tipo, [])
        if self.tipo == "publicacoes":
            itens = sorted(itens, key=lambda p: (p["meta"].get("gemec_data", ""), p["titulo"]), reverse=True)
        else:
            itens = sorted(itens, key=self._ordem_padrao)
        busca = historico_chave(self.c_busca.get())
        filtro = self.filtros[self.c_filtro.current()][0] if self.c_filtro.current() >= 0 else ""
        cols = [c for c, _r, _w in conteudo.TIPOS[self.tipo]["colunas"]]
        t = self.t_cont
        antes = set(t.selection())
        self._ignorar_sel = True
        t.delete(*t.get_children())
        n = 0
        for it in itens:
            if filtro == "oculta":
                if it["meta"].get("gemec_oculta") != "1":
                    continue
            elif filtro and it["situacao"] != filtro:
                continue
            if busca and busca not in historico_chave(it["titulo"] + " " + " ".join(str(v) for v in it["meta"].values())):
                continue
            apagado = it["situacao"] != "publish" or it["meta"].get("gemec_oculta") == "1"
            t.insert("", "end", iid=str(it["id"]), values=[self._valor_col(it, c) for c in cols], tags=("apagado",) if apagado else ())
            n += 1
        manter = [i for i in antes if t.exists(i)]
        if manter:
            t.selection_set(manter)
            t.see(manter[0])
        self.after_idle(lambda: setattr(self, "_ignorar_sel", False))
        total = len(itens)
        self.c_conta.configure(text=("%d de %d" % (n, total)) if n != total else "%d" % total)

    def _item(self, id_):
        for it in self.dados.get(self.tipo, []):
            if str(it["id"]) == str(id_):
                return it
        return None

    def _selecionou(self, _e=None):
        if self._ignorar_sel:
            return
        sel = self.t_cont.selection()
        atual = str(self.atual["id"]) if self.atual else None
        if self._sujo() and list(sel) != [atual]:
            if not messagebox.askyesno("Alterações não salvas", "Descartar as alterações em “%s”?" % (self.w_titulo.get() or "novo item"), parent=self):
                self._ignorar_sel = True
                self.t_cont.selection_set([atual] if atual and self.t_cont.exists(atual) else [])
                self.after_idle(lambda: setattr(self, "_ignorar_sel", False))
                return
        if len(sel) == 1:
            self._encher_form(self._item(sel[0]))
        elif len(sel) > 1:
            self.atual, self.snap = None, None
            self._mostrar_varios(sel)
        else:
            self.atual, self.snap = None, None
            self._painel("vazio")

    # --- formulario
    def _montar_form(self):
        t = conteudo.TIPOS[self.tipo]
        for w in self.f_dentro.winfo_children():
            w.destroy()
        self.w = {}
        d = self.f_dentro
        pad = {"padx": 22}

        def rotulo(txt, pai=d, topo=14):
            ttk.Label(pai, text=txt, style="Campo.TLabel").pack(anchor="w", pady=(topo, 4), **pad)

        def dica(txt, pai=d):
            if txt:
                ttk.Label(pai, text=txt, style="Dica.TLabel", wraplength=540, justify="left").pack(anchor="w", pady=(3, 0), **pad)

        rotulo(t["titulo"], topo=16)
        self.w_titulo = tk.StringVar()
        ttk.Entry(d, textvariable=self.w_titulo, font=(FONTE, 12)).pack(fill="x", **pad)

        linha = tk.Frame(d, bg="white")
        linha.pack(fill="x", pady=(14, 0), **pad)
        c1 = tk.Frame(linha, bg="white")
        c1.pack(side="left")
        ttk.Label(c1, text="Situação", style="Campo.TLabel").pack(anchor="w", pady=(0, 4))
        self.sit_map = dict(t["situacoes"])
        self.w_sit = ttk.Combobox(c1, state="readonly", width=26, values=[r for _v, r in t["situacoes"]])
        self.w_sit.pack(anchor="w")
        self.w_ordem = None
        if t.get("ordem"):
            c2 = tk.Frame(linha, bg="white")
            c2.pack(side="left", padx=(18, 0))
            ttk.Label(c2, text="Ordem", style="Campo.TLabel").pack(anchor="w", pady=(0, 4))
            self.w_ordem = tk.StringVar()
            ttk.Spinbox(c2, from_=-99, to=999, width=6, textvariable=self.w_ordem).pack(anchor="w")
        if self.tipo == "membros":
            dica("Privado = oculto: o Lattes é importado e os papers aparecem em Publicações, mas a pessoa some de Membros e das estatísticas.")

        self.foto_lbl = None
        if t.get("foto"):
            rotulo(t["foto"])
            fl = tk.Frame(d, bg="white")
            fl.pack(fill="x", **pad)
            self.foto_lbl = tk.Label(fl, bg=NEVOA, fg=ARDOSIA, width=12, height=5, font=(FONTE, 9),
                                     highlightthickness=1, highlightbackground=BORDA)
            self.foto_lbl.pack(side="left")
            bts = tk.Frame(fl, bg="white")
            bts.pack(side="left", padx=12)
            ttk.Button(bts, text="Escolher imagem…", command=self.escolher_foto).pack(anchor="w")
            ttk.Button(bts, text="Remover", command=self.remover_foto).pack(anchor="w", pady=(6, 0))
            dica("Quadrada para membros (é cortada em círculo); PNG com fundo transparente para logos. Vai para o site ao salvar.")

        for campo in t["campos"]:
            chave, rot, tipo, opcoes, txt = campo[:5]
            if tipo == "marca":
                v = tk.StringVar()
                ttk.Checkbutton(d, text=rot, variable=v, onvalue="1", offvalue="", style="Card.TCheckbutton").pack(anchor="w", pady=(16, 0), **pad)
                self.w[chave] = ("texto", v, None)
                dica(txt)
                continue
            rotulo(rot)
            if tipo == "longo":
                w = tk.Text(d, height=6 if chave == "gemec_bio" else 3, wrap="word", font=(FONTE, 10), relief="flat",
                            highlightthickness=1, highlightbackground=BORDA, highlightcolor=AZUL, padx=6, pady=4, undo=True)
                w.pack(fill="x", **pad)
                self.w[chave] = ("longo", w, None)
            elif tipo == "lista":
                w = ttk.Combobox(d, state="readonly", width=40, values=[r for _v, r in opcoes])
                w.pack(anchor="w", **pad)
                self.w[chave] = ("lista", w, campo)
            elif tipo == "membros":
                w = tk.Listbox(d, selectmode="multiple", height=9, exportselection=False, relief="flat", font=(FONTE, 10),
                               highlightthickness=1, highlightbackground=BORDA, selectbackground=AZUL_CLARO,
                               selectforeground=MARINHO, activestyle="none")
                w.pack(fill="x", **pad)
                self.w[chave] = ("membros", w, None)
            else:
                v = tk.StringVar()
                if tipo == "arquivo":
                    fl = tk.Frame(d, bg="white")
                    fl.pack(fill="x", **pad)
                    ttk.Entry(fl, textvariable=v).pack(side="left", fill="x", expand=True)
                    ttk.Button(fl, text="Enviar PDF…", command=lambda v=v: self.enviar_pdf(v)).pack(side="left", padx=(8, 0))
                else:
                    ttk.Entry(d, textvariable=v, width=18 if tipo == "data" else 0).pack(
                        **({"anchor": "w"} if tipo == "data" else {"fill": "x"}), **pad)
                self.w[chave] = ("texto", v, None)
            dica(txt)
            if chave == "gemec_orcid":
                self._barra_importar(d, pad)

        self.w_conteudo = None
        if t.get("conteudo"):
            rotulo("Conteúdo (blocos do editor)")
            self.w_conteudo = tk.Text(d, height=24, wrap="word", font=("Consolas", 9), relief="flat", undo=True,
                                      highlightthickness=1, highlightbackground=BORDA, highlightcolor=AZUL, padx=6, pady=4)
            self.w_conteudo.pack(fill="x", **pad)
        tk.Frame(d, bg="white", height=24).pack()

    def _barra_importar(self, d, pad):
        """Botoes do cadastro do membro: dados e foto do Lattes, busca no ORCID/OpenAlex."""
        caixa = tk.Frame(d, bg=AZUL_CLARO)
        caixa.pack(fill="x", pady=(14, 0), **pad)
        tk.Label(caixa, text="Importar dados", bg=AZUL_CLARO, fg=MARINHO, font=(FONTE, 10, "bold")).pack(anchor="w", padx=12, pady=(8, 4))
        l1 = tk.Frame(caixa, bg=AZUL_CLARO)
        l1.pack(fill="x", padx=12)
        for rot, cmd, dica in (
                ("Preencher pelo Lattes", self.preencher_lattes, "Puxa do Lattes o nome, formação, ORCID, temas, titulação e a foto, só nos campos vazios. Baixa o CV se ainda não estiver no PC."),
                ("Importar foto do Lattes", self.importar_foto, "Troca a foto do perfil pela do Lattes (vai ao site ao salvar)."),
                ("Buscar no ORCID / OpenAlex…", self.buscar_pesquisador, "Procura a pessoa pelo nome ou ORCID no ORCID e no OpenAlex, como no Altímetro.")):
            b = ttk.Button(l1, text=rot, command=cmd)
            b.pack(side="left", padx=(0, 6))
            Dica(b, dica)
        l2 = tk.Frame(caixa, bg=AZUL_CLARO)
        l2.pack(fill="x", padx=12, pady=(6, 10))
        self.lattes_b = ttk.Button(l2, text="Atualizar este membro no site", command=self.atualizar_este)
        self.lattes_b.pack(side="left")
        Dica(self.lattes_b, "Refaz o site com o Lattes novo dele (ou, sem Lattes, com as obras do OpenAlex pelo ORCID).")
        self._link(l2, "Abrir o Lattes ↗", comando=self.abrir_lattes, bg=AZUL_CLARO).pack(side="left", padx=12)
        self._link(l2, "Abrir o ORCID ↗", comando=self.abrir_orcid, bg=AZUL_CLARO).pack(side="left")
        self.lat_box = tk.Frame(d, bg="white")  # formacao e areas do Lattes (_mostrar_lattes)
        self.lat_box.pack(fill="x", **pad)

    def _mostrar_lattes(self):
        """Formacao academica e areas de atuacao do CV baixado, como vao ao perfil do site."""
        box = getattr(self, "lat_box", None)
        if box is None or not box.winfo_exists():
            return
        for w in box.winfo_children():
            w.destroy()
        lid = self._lattes_do_form()
        if not lid or not os.path.exists(os.path.join(CACHE, lid)):
            return
        import perfis
        try:
            forms, areas = perfis.formacao_lattes(lid), perfis.areas_lattes(lid)
        except Exception:  # noqa: BLE001 - CV salvo a mao fora do padrao: so nao mostra
            return
        if not forms and not areas:
            return
        ttk.Label(box, text="Do Lattes, no perfil do site", style="Campo.TLabel").pack(anchor="w", pady=(16, 0))
        ttk.Label(box, text="Formação acadêmica e áreas de atuação vêm do CV a cada atualização (para mudar, edite o Lattes).",
                  style="Dica.TLabel", wraplength=540, justify="left").pack(anchor="w", pady=(2, 6))
        for f in forms:
            linha = tk.Frame(box, bg="white")
            linha.pack(fill="x", pady=(0, 6))
            tk.Label(linha, text=f["anos"], bg="white", fg=AZUL, font=(FONTE, 9, "bold"), width=11, anchor="nw").pack(side="left", anchor="n")
            txt = tk.Frame(linha, bg="white")
            txt.pack(side="left", fill="x", expand=True)
            tk.Label(txt, text=f["curso"], bg="white", fg=TINTA, font=(FONTE, 9, "bold"), wraplength=430, justify="left", anchor="w").pack(anchor="w")
            det = [f["inst"]] + ([f["titulo"]] if f["titulo"] else []) + (
                ["Orientação: " + f["orientador"] + (" e " + f["coorientador"] if f["coorientador"] else "")] if f["orientador"] else [])
            tk.Label(txt, text="\n".join(x for x in det if x), bg="white", fg=ARDOSIA, font=(FONTE, 9), wraplength=430,
                     justify="left", anchor="w").pack(anchor="w")
        if areas:
            ttk.Label(box, text="Áreas de atuação: " + "; ".join(areas), style="Dica.TLabel", wraplength=540,
                      justify="left").pack(anchor="w", pady=(2, 0))

    def _campo(self, chave):
        tipo, w, campo = self.w[chave]
        if tipo == "longo":
            return w.get("1.0", "end-1c").strip()
        if tipo == "lista":
            return {r: x for x, r in campo[3]}.get(w.get(), "")
        return w.get().strip()

    def _por_campo(self, chave, valor):
        tipo, w, campo = self.w[chave]
        if tipo == "longo":
            w.delete("1.0", "end")
            w.insert("1.0", valor)
        elif tipo == "lista":
            w.set(dict(campo[3]).get(valor, valor))
        else:
            w.set(valor)

    def _do_lattes(self, depois, msg):
        lid = self._lattes_do_form()
        if not lid:
            messagebox.showinfo("Lattes", "Cole primeiro o link do Lattes (16 dígitos) no campo Currículo Lattes.", parent=self)
            return

        def trabalho():
            if not os.path.exists(os.path.join(CACHE, lid)):
                baixar_cv(lid)
            import perfis
            return perfis.do_lattes(lid)
        self.em_fundo(trabalho, lambda d: self._lattes_do_form() == lid and depois(lid, d), msg)

    def _foto_bytes(self, lid, dados):
        caminho = os.path.join(tempfile.gettempdir(), "gemec-lattes-%s.jpg" % lid)
        with open(caminho, "wb") as f:
            f.write(dados)
        self.foto_nova = caminho
        self._mostrar_foto()

    def preencher_lattes(self):
        def depois(lid, d):
            feitos = []
            if not self.w_titulo.get().strip() and d["nome"]:
                self.w_titulo.set(d["nome"])
                feitos.append("nome")
            rot = {"gemec_formacao": "formação", "gemec_orcid": "ORCID", "gemec_temas": "temas", "gemec_titulacao": "titulação"}
            for chave, nome in rot.items():
                if chave == "gemec_titulacao" and self._campo("gemec_categoria") != "egresso":
                    continue
                if not self._campo(chave) and d.get(chave):
                    self._por_campo(chave, d[chave])
                    feitos.append(nome)
            if not self.foto_id and not self.foto_nova and d["foto"]:
                self._foto_bytes(lid, d["foto"])
                feitos.append("foto")
            self._mostrar_lattes()
            self.c_status.configure(foreground=VERDE if feitos else ARDOSIA, text=(
                "Do Lattes: " + ", ".join(feitos) + ". Confira e clique em Salvar no site.") if feitos else
                "Nada a preencher: os campos que o Lattes traz já estão preenchidos.")
        self._do_lattes(depois, "Lendo o Lattes (pode baixar o CV, uns 30 s)…")

    def importar_foto(self):
        def depois(lid, d):
            if d["foto"]:
                self._foto_bytes(lid, d["foto"])
                self.c_status.configure(text="Foto do Lattes carregada. Clique em Salvar no site.", foreground=VERDE)
            else:
                messagebox.showinfo("Foto do Lattes", "O Lattes dessa pessoa não tem foto.", parent=self)
        self._do_lattes(depois, "Buscando a foto no Lattes…")

    def abrir_orcid(self):
        o = re.search(busca.ORCID_RE, self._campo("gemec_orcid"))
        if o:
            webbrowser.open("https://orcid.org/" + o.group())
        else:
            self.buscar_pesquisador()

    def buscar_pesquisador(self):
        """Busca no ORCID e no OpenAlex (pelo nome ou ORCID), como no Altimetro."""
        top = tk.Toplevel(self)
        top.title("Buscar no ORCID e no OpenAlex")
        top.configure(bg="white")
        top.transient(self)
        top.geometry("1080x580+%d+%d" % (self.winfo_rootx() + 60, self.winfo_rooty() + 60))
        tk.Frame(top, bg=VERMELHO, height=3).pack(fill="x")
        ttk.Label(top, text="Buscar no ORCID e no OpenAlex", style="H1.TLabel").pack(anchor="w", padx=20, pady=(14, 2))
        ttk.Label(top, text="Pelo nome ou pelo ORCID. Confira instituição, anos e temas para não pegar um homônimo. "
                            "Usar o perfil grava o ORCID no cadastro; para quem não tem Lattes, as publicações vêm do "
                            "OpenAlex por esse ORCID a cada atualização.", style="Dica.TLabel", wraplength=1000, justify="left").pack(anchor="w", padx=20)
        barra = tk.Frame(top, bg="white")
        barra.pack(fill="x", padx=20, pady=(12, 8))
        v = tk.StringVar(value=self._campo("gemec_orcid") or self.w_titulo.get().strip())
        e = ttk.Entry(barra, textvariable=v, width=48)
        e.pack(side="left")
        info = ttk.Label(barra, text="", style="Dica.TLabel")
        f, t = self._arvore(top, [("fonte", "Fonte"), ("nome", "Nome"), ("inst", "Instituição"), ("orcid", "ORCID"),
                                  ("obras", "Obras"), ("anos", "Anos"), ("temas", "Temas")], [80, 220, 230, 150, 60, 90, 300])
        f.pack(fill="both", expand=True, padx=20)
        res = []

        def buscar(_e=None):
            q = v.get().strip()
            if not q:
                return
            info.configure(text="Buscando…", foreground=ARDOSIA)

            def trabalho():
                out, erros = [], []
                for fonte, fn in (("OpenAlex", busca.openalex), ("ORCID", busca.orcid)):
                    try:
                        out += fn(q)
                    except Exception as erro:  # noqa: BLE001 - uma fonte fora do ar nao impede a outra
                        erros.append("%s fora do ar (%s)" % (fonte, type(erro).__name__))
                return out, erros

            def depois(r):
                if not top.winfo_exists():
                    return
                res[:] = r[0]
                t.delete(*t.get_children())
                for k, it in enumerate(res):
                    t.insert("", "end", iid=str(k), values=(it["fonte"], it["nome"], it["instituicao"], it["orcid"] or "—",
                                                           it["obras"], it["anos"], it["temas"]), tags=() if it["orcid"] else ("apagado",))
                info.configure(text="%d perfis%s" % (len(res), (" · " + "; ".join(r[1])) if r[1] else ""))
            self.em_fundo(trabalho, depois, "Buscando no ORCID e no OpenAlex…")

        def escolhido():
            sel = t.selection()
            return res[int(sel[0])] if sel else None

        def usar(_e=None):
            it = escolhido()
            if not it:
                return
            if not it["orcid"]:
                messagebox.showinfo("Buscar", "Este perfil do OpenAlex não tem ORCID. Escolha um que tenha: o site liga a pessoa pelo ORCID.", parent=top)
                return
            self._por_campo("gemec_orcid", it["orcid"])
            if not self.w_titulo.get().strip():
                self.w_titulo.set(it["nome"])
            if it.get("temas") and not self._campo("gemec_temas"):
                self._por_campo("gemec_temas", it["temas"])
            top.destroy()
            self.c_status.configure(text="ORCID %s no cadastro. Clique em Salvar no site." % it["orcid"], foreground=VERDE)

        ttk.Button(barra, text="Buscar", style="Principal.TButton", command=buscar).pack(side="left", padx=8)
        info.pack(side="left", padx=8)
        pe = tk.Frame(top, bg=NEVOA)
        pe.pack(fill="x", side="bottom", pady=(10, 0))
        ttk.Button(pe, text="Usar este perfil", style="Principal.TButton", command=usar).pack(side="right", padx=(6, 16), pady=10)
        ttk.Button(pe, text="Cancelar", command=top.destroy).pack(side="right", pady=10)
        ttk.Button(pe, text="Abrir o perfil ↗", command=lambda: escolhido() and webbrowser.open(busca.link(escolhido()))).pack(side="left", padx=16, pady=10)
        e.bind("<Return>", buscar)
        t.bind("<Double-1>", usar)
        top.bind("<Escape>", lambda _e: top.destroy())
        e.focus_set()
        if v.get():
            top.after(100, buscar)

    # --- configuracoes
    def pedir_login(self, depois):
        """Primeira vez neste PC: pede o login, confere no site e grava em config.json."""
        top = tk.Toplevel(self)
        top.title("Entrar")
        top.configure(bg="white")
        top.transient(self)
        top.resizable(False, False)
        top.geometry("+%d+%d" % (self.winfo_rootx() + 320, self.winfo_rooty() + 160))
        tk.Frame(top, bg=VERMELHO, height=3).pack(fill="x")
        c = tk.Frame(top, bg="white")
        c.pack(fill="both", expand=True, padx=24, pady=16)
        ttk.Label(c, text="Entrar no site do GEMEC", style="H1.TLabel").pack(anchor="w")
        ttk.Label(c, text="Usuário e senha do WordPress (gemec.unifei.edu.br). Ficam salvos só neste PC, "
                          "em config.json; para trocar depois, use Configurações.",
                  style="Dica.TLabel", wraplength=380, justify="left").pack(anchor="w", pady=(4, 12))
        v_u, v_s = tk.StringVar(value=acesso.ler()["usuario"]), tk.StringVar()
        for rot, var, oculto in (("Usuário", v_u, False), ("Senha", v_s, True)):
            f = tk.Frame(c, bg="white")
            f.pack(fill="x", pady=3)
            ttk.Label(f, text=rot, style="Card.TLabel", width=9).pack(side="left")
            e = ttk.Entry(f, textvariable=var, show="•" if oculto else "", width=34)
            e.pack(side="left", fill="x", expand=True)
        e.focus_set()

        def entrar(_e=None):
            u, sn = v_u.get().strip(), v_s.get()
            if not u or not sn:
                messagebox.showwarning("Entrar", "Preencha usuário e senha.", parent=top)
                return

            def ok(_r):
                acesso.gravar(u, sn)
                conteudo.sair()
                top.destroy()
                depois()
            self.em_fundo(lambda: conteudo.testar_login(u, sn), ok, "Conferindo o login no site…")
        ttk.Button(c, text="Entrar", style="Principal.TButton", command=entrar).pack(anchor="e", pady=(14, 0))
        top.bind("<Return>", entrar)
        top.grab_set()

    def configuracoes(self):
        top = tk.Toplevel(self)
        top.title("Configurações")
        top.configure(bg="white")
        top.transient(self)
        top.geometry("580x780+%d+%d" % (self.winfo_rootx() + 160, self.winfo_rooty() + 30))
        tk.Frame(top, bg=VERMELHO, height=3).pack(fill="x")
        c = tk.Frame(top, bg="white")
        c.pack(fill="both", expand=True, padx=24, pady=14)
        ttk.Label(c, text="Configurações", style="H1.TLabel").pack(anchor="w")

        def titulo(txt, dica):
            ttk.Label(c, text=txt, style="Campo.TLabel").pack(anchor="w", pady=(16, 2))
            ttk.Label(c, text=dica, style="Dica.TLabel", wraplength=520, justify="left").pack(anchor="w", pady=(0, 6))

        def linha(rot, var, oculto=False):
            f = tk.Frame(c, bg="white")
            f.pack(fill="x", pady=2)
            ttk.Label(f, text=rot, style="Card.TLabel", width=16).pack(side="left")
            e = ttk.Entry(f, textvariable=var, show="•" if oculto else "")
            e.pack(side="left", fill="x", expand=True)
            return e

        titulo("Login no WordPress do GEMEC", "Usado pelo app e pelas atualizações do Lattes. Fica só neste PC (config.json, na pasta do app).")
        atual = acesso.ler()
        v_u, v_s = tk.StringVar(value=atual["usuario"]), tk.StringVar(value=atual["senha"])
        linha("Usuário", v_u)
        e_s = linha("Senha", v_s, oculto=True)
        v_ver = tk.BooleanVar()
        ttk.Checkbutton(c, text="Mostrar a senha", variable=v_ver, style="Card.TCheckbutton",
                        command=lambda: e_s.configure(show="" if v_ver.get() else "•")).pack(anchor="w", pady=(4, 0))
        info1 = ttk.Label(c, text="", style="Dica.TLabel")
        conta = ttk.Label(c, text="", style="Dica.TLabel", wraplength=520, justify="left")

        def ler_conta():
            self.em_fundo(conteudo.eu, lambda d: top.winfo_exists() and conta.configure(
                text="Conectado como %s (%s) · %s%s" % (d["nome"], d["usuario"], ", ".join(d["papeis"]), " · " + d["email"] if d["email"] else "")),
                "Lendo a conta…")

        def salvar_login():
            u, sn = v_u.get().strip(), v_s.get()
            if not u or not sn:
                messagebox.showwarning("Login", "Preencha usuário e senha.", parent=top)
                return

            def ok(_r):
                acesso.gravar(u, sn)
                conteudo.sair()
                if top.winfo_exists():
                    info1.configure(text="Login conferido no site e salvo.", foreground=VERDE)
                    ler_conta()
            self.em_fundo(lambda: conteudo.testar_login(u, sn), ok, "Conferindo o login no site…")
        b = tk.Frame(c, bg="white")
        b.pack(fill="x", pady=(8, 0))
        ttk.Button(b, text="Conferir e salvar", style="Principal.TButton", command=salvar_login).pack(side="left")
        info1.pack(in_=b, side="left", padx=10)
        conta.pack(anchor="w", pady=(8, 0))

        tk.Frame(c, bg=BORDA, height=1).pack(fill="x", pady=(16, 0))
        titulo("Trocar a senha no site", "Muda a senha deste usuário no WordPress e já grava aqui. Quem usa a mesma conta "
                                         "em outro lugar (outro PC, o navegador) vai precisar da senha nova.")
        v_n1, v_n2 = tk.StringVar(), tk.StringVar()
        linha("Senha nova", v_n1, oculto=True)
        linha("Repita", v_n2, oculto=True)
        info2 = ttk.Label(c, text="", style="Dica.TLabel")

        def trocar():
            n1, n2 = v_n1.get(), v_n2.get()
            if len(n1) < 10:
                messagebox.showwarning("Senha", "Use pelo menos 10 caracteres.", parent=top)
                return
            if n1 != n2:
                messagebox.showwarning("Senha", "As duas senhas não são iguais.", parent=top)
                return
            if not messagebox.askyesno("Trocar a senha", "Trocar a senha do usuário “%s” no site agora?" % acesso.ler()["usuario"], parent=top):
                return

            def ok(_r):
                if top.winfo_exists():
                    v_s.set(n1)
                    v_n1.set("")
                    v_n2.set("")
                    info2.configure(text="Senha trocada no site e salva aqui.", foreground=VERDE)
            self.em_fundo(lambda: conteudo.trocar_senha(n1), ok, "Trocando a senha no site…")
        b = tk.Frame(c, bg="white")
        b.pack(fill="x", pady=(8, 0))
        ttk.Button(b, text="Trocar a senha", command=trocar).pack(side="left")
        info2.pack(in_=b, side="left", padx=10)

        tk.Frame(c, bg=BORDA, height=1).pack(fill="x", pady=(16, 0))
        titulo("Outros usuários do site", "Criar contas, mudar papéis e redefinir senhas de outras pessoas é no painel do WordPress.")
        b = tk.Frame(c, bg="white")
        b.pack(fill="x")
        self._link(b, "Usuários ↗", SITE + "/wp-admin/users.php").pack(side="left")
        self._link(b, "Adicionar usuário ↗", SITE + "/wp-admin/user-new.php").pack(side="left", padx=16)
        self._link(b, "Meu perfil ↗", SITE + "/wp-admin/profile.php").pack(side="left")
        pe = tk.Frame(top, bg=NEVOA)
        pe.pack(fill="x", side="bottom")
        ttk.Button(pe, text="Fechar", command=top.destroy).pack(side="right", padx=16, pady=10)
        top.bind("<Escape>", lambda _e: top.destroy())
        ler_conta()

    def _membros_lb(self):
        """(id, nome) dos membros para a caixa de membros das publicacoes."""
        return sorted(((m["id"], m["titulo"]) for m in self.dados.get("membros", [])), key=lambda x: historico_chave(x[1]))

    def _encher_form(self, item):
        t = conteudo.TIPOS[self.tipo]
        self.atual = item
        self.foto_nova = None
        meta = item["meta"] if item else {}
        self.w_titulo.set(item["titulo"] if item else "")
        sit = item["situacao"] if item else t["situacoes"][0][0]
        self.w_sit.set(self.sit_map.get(sit, sit))
        if self.w_ordem is not None:
            self.w_ordem.set(str(item["ordem"]) if item else "0")
        for chave, (tipo, w, campo) in self.w.items():
            valor = meta.get(chave, "")
            if tipo == "longo":
                w.delete("1.0", "end")
                w.insert("1.0", valor or "")
                w.edit_reset()
            elif tipo == "lista":
                valor = valor or conteudo.opcao(campo)
                w.set(dict(campo[3]).get(valor, valor))
            elif tipo == "membros":
                self.lb_ids = [i for i, _n in self._membros_lb()]
                w.delete(0, "end")
                for _i, n in self._membros_lb():
                    w.insert("end", n)
                for k, i in enumerate(self.lb_ids):
                    if i in (valor or []):
                        w.selection_set(k)
            else:
                w.set(valor or "")
        if self.w_conteudo is not None:
            self.w_conteudo.delete("1.0", "end")
            self.w_conteudo.insert("1.0", item["conteudo"] if item else "")
            self.w_conteudo.edit_reset()
        self.foto_id = item["foto"] if item else 0
        self._mostrar_foto()
        if self.tipo == "membros":
            self._mostrar_lattes()
        sing = t["singular"]
        if item:
            self.f_titulo.configure(text=item["titulo"] or "(sem título)")
            self.f_sub.configure(text="%s · nº %d no WordPress%s" % (sing[0].upper() + sing[1:], item["id"],
                                 " · " + t["dica"] if self.tipo == "publicacoes" else ""))
        else:
            self.f_titulo.configure(text=novo_de(sing))
            self.f_sub.configure(text=("Cole o link do Lattes e clique em Preencher pelo Lattes; quem não tem Lattes, busque o ORCID. "
                                       "Depois, Salvar no site.") if self.tipo == "membros" else "Preencha e clique em Salvar no site. " + t["dica"])
        self._painel("form")
        self.snap = self._ler_form()

    def _ler_form(self):
        t = conteudo.TIPOS[self.tipo]
        inv = {r: v for v, r in t["situacoes"]}
        v = {"title": self.w_titulo.get().strip(), "status": inv.get(self.w_sit.get(), self.w_sit.get())}
        if self.w_ordem is not None:
            try:
                v["menu_order"] = int(self.w_ordem.get() or 0)
            except ValueError:
                v["menu_order"] = 0
        meta = {}
        for chave, (tipo, w, campo) in self.w.items():
            if tipo == "longo":
                meta[chave] = w.get("1.0", "end-1c").strip()
            elif tipo == "lista":
                meta[chave] = {r: x for x, r in campo[3]}.get(w.get(), "")
            elif tipo == "membros":
                meta[chave] = sorted(self.lb_ids[k] for k in w.curselection())
            else:
                meta[chave] = w.get().strip()
        if meta:
            v["meta"] = meta
        if self.w_conteudo is not None:
            v["content"] = self.w_conteudo.get("1.0", "end-1c")
        if t.get("foto"):
            v["featured_media"] = self.foto_id
        return v

    def _sujo(self):
        return self.snap is not None and (self.foto_nova is not None or self._ler_form() != self.snap)

    def _mostrar_foto(self):
        if not self.foto_lbl:
            return
        self.foto_img = None
        if self.foto_nova:
            self.foto_img = imagem(caminho=self.foto_nova)
            texto = "nova:\n" + os.path.basename(self.foto_nova)[:18]
        elif self.foto_id:
            texto = "carregando…"
            id_, media = (self.atual or {}).get("id"), self.foto_id
            self.em_fundo(lambda: conteudo.miniatura(media), lambda b: self._foto_chegou(id_, media, b), "Carregando imagem…")
        else:
            texto = "sem imagem"
        if self.foto_img:
            self.foto_lbl.configure(image=self.foto_img, text="", width=96, height=96)
        else:
            self.foto_lbl.configure(image="", text=texto, width=12, height=5)

    def _foto_chegou(self, id_, media, dados):
        if (self.atual or {}).get("id") != id_ or self.foto_id != media or self.foto_nova or not self.foto_lbl:
            return
        self.foto_img = imagem(dados=dados) if dados else None
        if self.foto_img:
            self.foto_lbl.configure(image=self.foto_img, text="", width=96, height=96)
        else:
            self.foto_lbl.configure(image="", text="tem imagem\n(sem prévia)" if dados else "imagem não\nencontrada", width=12, height=5)

    def escolher_foto(self):
        c = filedialog.askopenfilename(parent=self, title="Escolher imagem",
                                       filetypes=[("Imagens", "*.jpg *.jpeg *.png *.gif *.webp"), ("Todos", "*.*")])
        if c:
            self.foto_nova = c
            self._mostrar_foto()

    def remover_foto(self):
        self.foto_nova = None
        self.foto_id = 0
        self._mostrar_foto()

    def enviar_pdf(self, var):
        c = filedialog.askopenfilename(parent=self, title="Escolher o edital", filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
        if c:
            self.em_fundo(lambda: conteudo.enviar_arquivo(c), lambda m: var.set(m["url"]), "Enviando o PDF…")

    def novo(self):
        if self._sujo() and not messagebox.askyesno("Alterações não salvas", "Descartar as alterações em “%s”?" % self.w_titulo.get(), parent=self):
            return
        self._ignorar_sel = True
        self.t_cont.selection_set([])
        self.after_idle(lambda: setattr(self, "_ignorar_sel", False))
        self._encher_form(None)

    def _validar(self, v):
        if not v["title"]:
            return "Preencha o campo %s." % conteudo.TIPOS[self.tipo]["titulo"]
        for chave, valor in v.get("meta", {}).items():
            if chave in ("gemec_data", "gemec_inicio", "gemec_prazo") and valor and not re.match(r"\d{4}-\d{2}-\d{2}$", valor):
                return "A data deve estar no formato AAAA-MM-DD (ex.: 2026-11-30)."
            if chave == "gemec_email" and valor and not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+$", valor):
                return "O e-mail não parece certo: " + valor
        return None

    def salvar(self):
        v = self._ler_form()
        erro = self._validar(v)
        if erro:
            messagebox.showwarning("Salvar", erro, parent=self)
            return
        lattes = v.get("meta", {}).get("gemec_lattes", "")
        if self.tipo == "membros" and lattes and not re.search(r"\d{16}", lattes):
            if not messagebox.askyesno("Salvar", "O link do Lattes não tem o número de 16 dígitos; a importação não vai achar o CV.\n\nSalvar assim mesmo?", parent=self):
                return
        tipo, id_, foto = self.tipo, (self.atual or {}).get("id"), self.foto_nova

        def trabalho():
            if foto:
                v["featured_media"] = conteudo.enviar_arquivo(foto, v["title"])["id"]
            return conteudo.salvar(tipo, id_, v)

        def depois(item):
            lista = self.dados.setdefault(tipo, [])
            for k, it in enumerate(lista):
                if it["id"] == item["id"]:
                    lista[k] = item
                    break
            else:
                lista.append(item)
            if tipo != self.tipo:
                return
            self.preencher_lista()
            self._ignorar_sel = True
            if self.t_cont.exists(str(item["id"])):
                self.t_cont.selection_set([str(item["id"])])
                self.t_cont.see(str(item["id"]))
            self.after_idle(lambda: setattr(self, "_ignorar_sel", False))
            self._encher_form(item)
            self._numeros_site()
            self.c_status.configure(text="Salvo no site às %s" % datetime.datetime.now().strftime("%H:%M"), foreground=VERDE)
            if tipo == "membros" and not id_ and item["situacao"] in ("publish", "private") and not self.proc:
                m = re.search(r"\d{16}", item["meta"].get("gemec_lattes", ""))
                o = re.search(busca.ORCID_RE, item["meta"].get("gemec_orcid", ""))
                if (m or o) and messagebox.askyesno("Membro novo", "%s está no site. Trazer agora as publicações dele%s?"
                                                    % (item["titulo"], "" if m else " (do OpenAlex, pelo ORCID)"), parent=self):
                    self.atualizar_membro(item["titulo"], m.group() if m else o.group().upper())
        self.em_fundo(trabalho, depois, "Salvando no site…")

    def lixeira(self):
        ids = [int(i) for i in self.t_cont.selection()] or ([self.atual["id"]] if self.atual else [])
        if not ids:
            return
        t = conteudo.TIPOS[self.tipo]
        nomes = [self._item(i)["titulo"] for i in ids if self._item(i)]
        txt = "“%s”" % nomes[0] if len(ids) == 1 else "%d itens" % len(ids)
        extra = "\n\nPublicações do Lattes voltam na próxima atualização; para tirar do site de vez, use Ocultar." if self.tipo == "publicacoes" else ""
        if not messagebox.askyesno("Mover para a lixeira", "Mover %s para a lixeira do WordPress?\n\nDá para recuperar pela lixeira do painel.%s" % (txt, extra), parent=self):
            return
        tipo = self.tipo

        def trabalho():
            for i in ids:
                conteudo.lixeira(tipo, i)

        def depois(_r):
            self.dados[tipo] = [it for it in self.dados.get(tipo, []) if it["id"] not in ids]
            self.atual, self.snap = None, None
            if tipo == self.tipo:
                self.preencher_lista()
                self._painel("vazio")
            self._numeros_site()
        self.em_fundo(trabalho, depois, "Movendo %s para a lixeira…" % t["rotulo"].lower())

    def _mostrar_varios(self, ids):
        for w in self.v_dentro.winfo_children():
            w.destroy()
        t = conteudo.TIPOS[self.tipo]
        self.f_titulo.configure(text="%d selecionados" % len(ids))
        self.f_sub.configure(text="O que fizer aqui vale para todos os itens selecionados na lista.")
        d = self.v_dentro
        ttk.Label(d, text="Mudar a situação", style="Campo.TLabel").pack(anchor="w", padx=22, pady=(18, 6))
        fl = tk.Frame(d, bg="white")
        fl.pack(anchor="w", padx=22)
        for cod, rot in t["situacoes"]:
            ttk.Button(fl, text=rot, command=lambda c=cod: self._lote(ids, {"status": c})).pack(side="left", padx=(0, 6))
        if self.tipo == "publicacoes":
            ttk.Label(d, text="Na página Publicações", style="Campo.TLabel").pack(anchor="w", padx=22, pady=(18, 6))
            fl = tk.Frame(d, bg="white")
            fl.pack(anchor="w", padx=22)
            ttk.Button(fl, text="Ocultar do site", command=lambda: self._lote(ids, {"meta": {"gemec_oculta": "1"}})).pack(side="left", padx=(0, 6))
            ttk.Button(fl, text="Mostrar no site", command=lambda: self._lote(ids, {"meta": {"gemec_oculta": ""}})).pack(side="left")
            ttk.Label(d, text="A marca Ocultar se mantém nas próximas atualizações do Lattes.", style="Dica.TLabel").pack(anchor="w", padx=22, pady=(4, 0))
        if self.tipo == "membros":
            ttk.Label(d, text="Categoria", style="Campo.TLabel").pack(anchor="w", padx=22, pady=(18, 6))
            cb = ttk.Combobox(d, state="readonly", width=32, values=[r for _v, r in conteudo.CATEGORIAS])
            cb.pack(anchor="w", padx=22)
            cb.bind("<<ComboboxSelected>>", lambda _e: self._lote(ids, {"meta": {"gemec_categoria": conteudo.CATEGORIAS[cb.current()][0]}}))
            ttk.Label(d, text="Ex.: quem defendeu passa de Mestrado para Egressos.", style="Dica.TLabel").pack(anchor="w", padx=22, pady=(4, 0))
        self._painel("varios")

    def _lote(self, ids, corpo):
        tipo = self.tipo
        if not messagebox.askyesno("Mudar vários", "Aplicar a mudança em %d itens no site?" % len(ids), parent=self):
            return

        def trabalho():
            return [conteudo.salvar(tipo, int(i), corpo) for i in ids]

        def depois(itens):
            novos = {it["id"]: it for it in itens}
            self.dados[tipo] = [novos.get(it["id"], it) for it in self.dados.get(tipo, [])]
            if tipo == self.tipo:
                self.preencher_lista()
            self._numeros_site()
            self.c_status.configure(text="%d itens salvos no site" % len(itens), foreground=VERDE)
        self.em_fundo(trabalho, depois, "Salvando %d itens no site…" % len(ids))

    def ver_no_site(self):
        t = conteudo.TIPOS[self.tipo]
        if self.atual and self.atual["situacao"] == "publish" and self.tipo in ("membros", "paginas") and self.atual["link"]:
            webbrowser.open(self.atual["link"])
        else:
            webbrowser.open(SITE + t.get("pagina", "/"))

    def abrir_painel(self):
        if self.atual:
            webbrowser.open(conteudo.painel(self.atual["id"]))

    def _lattes_do_form(self):
        m = re.search(r"\d{16}", self.w.get("gemec_lattes", ("", tk.StringVar(), None))[1].get())
        return m.group() if m else None

    def abrir_lattes(self):
        lid = self._lattes_do_form()
        if lid:
            webbrowser.open("http://lattes.cnpq.br/" + lid)
        else:
            messagebox.showinfo("Lattes", "Este membro não tem o link do Lattes (16 dígitos).", parent=self)

    def atualizar_este(self):
        o = re.search(busca.ORCID_RE, self._campo("gemec_orcid"))
        lid = self._lattes_do_form() or (o.group().upper() if o else None)
        if not lid:
            messagebox.showinfo("Atualizar", "Preencha o link do Lattes (ou, para quem não tem Lattes, o ORCID) e salve antes.", parent=self)
            return
        if self._sujo() or (self.atual and self.atual["situacao"] not in ("publish", "private")):
            messagebox.showinfo("Lattes", "Salve o membro no site (publicado ou oculto) antes de atualizar pelo Lattes.", parent=self)
            return
        self.atualizar_membro(self.w_titulo.get(), lid)

    # ------------------------------------------------------ um membro so
    def escolher_membro(self):
        if self.proc:
            messagebox.showinfo("Atualizar um membro", "Já tem uma tarefa rodando.", parent=self)
            return
        top = tk.Toplevel(self)
        top.title("Atualizar um membro")
        top.configure(bg="white")
        top.transient(self)
        top.geometry("520x560+%d+%d" % (self.winfo_rootx() + 120, self.winfo_rooty() + 80))
        tk.Frame(top, bg=VERMELHO, height=3).pack(fill="x")
        ttk.Label(top, text="Atualizar um membro pelo Lattes", style="H1.TLabel").pack(anchor="w", padx=20, pady=(16, 2))
        ttk.Label(top, text="Baixa só o CV dessa pessoa e refaz o site com ele (publicações, resumo, estatísticas e perfil). "
                            "Os outros membros entram com o CV que já está baixado.", style="Dica.TLabel",
                  wraplength=470, justify="left").pack(anchor="w", padx=20)
        filtro = tk.StringVar()
        e = ttk.Entry(top, textvariable=filtro)
        e.pack(fill="x", padx=20, pady=(14, 6))
        lb = tk.Listbox(top, relief="flat", font=(FONTE, 10), highlightthickness=1, highlightbackground=BORDA,
                        selectbackground=AZUL, selectforeground="white", activestyle="none", exportselection=False)
        lb.pack(fill="both", expand=True, padx=20)
        info = ttk.Label(top, text="", style="Dica.TLabel")
        info.pack(anchor="w", padx=20, pady=(4, 0))
        itens = []
        cats = dict(conteudo.CATEGORIAS)

        def lista_membros():
            if "membros" in self.dados:
                out, sem = [], 0
                for it in self.dados["membros"]:
                    m = re.search(r"\d{16}", it["meta"].get("gemec_lattes", ""))
                    o = re.search(busca.ORCID_RE, it["meta"].get("gemec_orcid", ""))
                    if it["situacao"] not in ("publish", "private"):
                        continue
                    if not m and not o:
                        sem += 1
                        continue
                    cat = cats.get(it["meta"].get("gemec_categoria", ""), "") + (" · oculto" if it["situacao"] == "private" else "")
                    out.append((it["titulo"], m.group() if m else o.group().upper(), cat + ("" if m else " · sem Lattes (OpenAlex)")))
                info.configure(text="%d membros%s." % (len(out), " (%d sem Lattes nem ORCID não aparecem)" % sem if sem else ""))
            else:
                out = [(m.get("nome", ""), i, "") for i, m in self.site.get("membros", {}).items()]
                info.configure(text="Lista do último envio; sincronizando com o site…")
            return sorted(out, key=lambda x: historico_chave(x[0]))

        def encher(*_):
            q = historico_chave(filtro.get())
            lb.delete(0, "end")
            itens.clear()
            for nome, lid, cat in lista_membros():
                if q in historico_chave(nome):
                    itens.append((nome, lid))
                    lb.insert("end", "  %s   —   %s" % (nome, cat) if cat else "  " + nome)
            if itens:
                lb.selection_set(0)

        def ir(_e=None):
            sel = lb.curselection()
            if not sel:
                return
            nome, lid = itens[sel[0]]
            top.destroy()
            self.atualizar_membro(nome, lid)

        filtro.trace_add("write", encher)
        bts = tk.Frame(top, bg=NEVOA)
        bts.pack(fill="x", side="bottom", pady=(10, 0))
        ttk.Button(bts, text="Atualizar", style="Principal.TButton", command=ir).pack(side="right", padx=(6, 16), pady=10)
        ttk.Button(bts, text="Cancelar", command=top.destroy).pack(side="right", pady=10)
        lb.bind("<Double-1>", ir)
        top.bind("<Return>", ir)
        top.bind("<Escape>", lambda _e: top.destroy())
        e.bind("<Down>", lambda _e: (lb.focus_set(), "break"))
        encher()
        e.focus_set()
        if "membros" not in self.dados:
            self.em_fundo(lambda: conteudo.listar("membros"),
                          lambda d: (self.dados.__setitem__("membros", d), top.winfo_exists() and encher()), "Lendo os membros do site…")

    def atualizar_membro(self, nome, lid):
        if re.fullmatch(busca.ORCID_RE, lid):
            dica = ("%s não tem Lattes: refaz o site trazendo as obras dele do OpenAlex pelo ORCID. "
                    "Os outros membros entram com o CV já baixado. Leva alguns minutos." % nome)
        else:
            dica = ("Baixa o CV de %s no Lattes e refaz o site com ele: publicações, resumo, estatísticas e perfil. "
                    "Os outros membros entram com o CV já baixado. Leva alguns minutos." % nome)
        self.rodar("membro", "Atualizar " + nome, True, dica, args=[lid])

    # ------------------------------------------------------- abas do Lattes
    def _aba_historico(self):
        aba = ttk.Frame(self.abas, padding=10)
        self.abas.add(aba, text="Últimas atualizações")
        self.aba_hist = aba
        pan = ttk.PanedWindow(aba, orient="horizontal")
        pan.pack(fill="both", expand=True)
        f, self.t_hist = self._arvore(pan, [("data", "Quando"), ("modo", "Tipo"), ("resumo", "O que mudou")], [130, 170, 300])
        self.t_hist.bind("<<TreeviewSelect>>", lambda _e: self.mostrar_entrada())
        pan.add(f, weight=2)
        df = tk.Frame(pan, bg="white", highlightthickness=1, highlightbackground=BORDA)
        self.detalhe = tk.Text(df, wrap="word", relief="flat", padx=18, pady=14, font=(FONTE, 10),
                               bg="white", fg=TINTA, cursor="arrow", spacing1=1, spacing3=1)
        sb = ttk.Scrollbar(df, orient="vertical", command=self.detalhe.yview)
        self.detalhe.configure(yscrollcommand=sb.set)
        self.detalhe.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        d = self.detalhe
        d.tag_configure("h1", font=(FONTE, 14, "bold"), foreground=MARINHO, spacing3=6)
        d.tag_configure("h2", font=(FONTE, 11, "bold"), spacing1=12, spacing3=4)
        d.tag_configure("cinza", foreground=ARDOSIA)
        d.tag_configure("mais", foreground=VERDE, font=(FONTE, 10, "bold"))
        d.tag_configure("menos", foreground=VERMELHO, font=(FONTE, 10, "bold"))
        d.tag_configure("ti", font=(FONTE, 10))
        d.tag_configure("item", lmargin1=10, lmargin2=24, spacing3=4)
        pan.add(df, weight=3)

    def _aba_curriculos(self):
        aba = ttk.Frame(self.abas, padding=10)
        self.abas.add(aba, text="Currículos no Lattes")
        ttk.Label(aba, text="Quando cada membro atualizou o Currículo Lattes (em verde: nos últimos 30 dias) e quando o app baixou o CV pela última vez. "
                            "Duplo clique abre o CV; botão direito atualiza só aquele membro.", style="Cinza.TLabel").pack(anchor="w", pady=(0, 6))
        f, self.t_cvs = self._arvore(aba, [("nome", "Membro"), ("grupo", "Categoria"), ("lattes", "Atualizado no Lattes"), ("baixado", "Baixado pelo app")],
                                     [320, 200, 160, 160])
        f.pack(fill="both", expand=True)
        self.t_cvs.bind("<Double-1>", self._abrir_lattes)
        self.t_cvs.bind("<Button-3>", self._menu_cv)

    def _menu_cv(self, e):
        i = self.t_cvs.identify_row(e.y)
        if not i:
            return
        self.t_cvs.selection_set(i)
        nome = self.t_cvs.set(i, "nome")
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Atualizar só %s pelo Lattes" % nome, command=lambda: self.atualizar_membro(nome, i))
        m.add_command(label="Abrir o CV no navegador", command=lambda: webbrowser.open("http://lattes.cnpq.br/" + i))
        m.tk_popup(e.x_root, e.y_root)

    def _aba_publicacoes(self):
        aba = ttk.Frame(self.abas, padding=10)
        self.abas.add(aba, text="Publicações recentes")
        linha = ttk.Frame(aba)
        linha.pack(fill="x", pady=(0, 6))
        ttk.Label(linha, text="Buscar:").pack(side="left")
        self.busca = tk.StringVar()
        e = ttk.Entry(linha, textvariable=self.busca, width=40)
        e.pack(side="left", padx=6)
        self.busca.trace_add("write", lambda *_: self.preencher_pubs())
        self.conta_pubs = ttk.Label(linha, text="", style="Cinza.TLabel")
        self.conta_pubs.pack(side="left", padx=8)
        f, self.t_pubs = self._arvore(aba, [("ano", "Ano"), ("tipo", "Tipo"), ("titulo", "Título"), ("membros", "Membros do GEMEC"), ("veiculo", "Onde")],
                                      [60, 160, 420, 240, 240])
        f.pack(fill="both", expand=True)
        self.t_pubs.bind("<Double-1>", self._abrir_pub)

    def _aba_registro(self):
        aba = ttk.Frame(self.abas, padding=10)
        self.abas.add(aba, text="Registro")
        self.aba_registro = aba
        self.log = tk.Text(aba, wrap="word", font=("Consolas", 10), bg=TINTA, fg="#E6EDF3", insertbackground="white",
                           relief="flat", padx=12, pady=10)
        sb = ttk.Scrollbar(aba, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set, state="disabled")
        self.log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.log.tag_configure("erro", foreground="#FF8A80")
        self.log.tag_configure("ok", foreground="#7EE787")
        self.log.tag_configure("cmd", foreground="#8DB8F2")

    # ------------------------------------------------------------------ dados
    def recarregar(self):
        self.hist = historico.ler(historico.HISTORICO, [])
        site = historico.ler(historico.SITE_JSON, {})
        rel = historico.ler(historico.RELATORIO_JSON, {})
        self.site = site

        # Cartoes
        if os.path.exists(MARCA_SEMANAL):
            d = datetime.datetime.fromtimestamp(os.path.getmtime(MARCA_SEMANAL)).date()
            self.num["ultima"].config(text=d.strftime("%d/%m"))
            self.num["ultima_r"].config(text="última atualização completa (%s)" % ha_quanto(d))
        if self.hist:
            d = datetime.datetime.fromisoformat(self.hist[0]["data"]).date()
            self.num["envio"].config(text=d.strftime("%d/%m"))
            self.num["envio_r"].config(text="último envio ao site (%s)" % ha_quanto(d))
        if not self.dados:  # sem sincronizar ainda: numeros do ultimo envio
            self.num["membros"].config(text=str(len(set(site.get("membros", {})) - set(site.get("ocultos", []))) or "—"))
            self.num["membros_r"].config(text="currículos no relatório")
            self.num["pubs"].config(text=str(len(site.get("publicacoes", [])) or "—"))

        # Historico
        t = self.t_hist
        t.delete(*t.get_children())
        for n, e in enumerate(self.hist):
            t.insert("", "end", iid=str(n), values=(quando(e["data"]), e.get("modo", ""), historico.resumo(e)))
        if self.hist:
            t.selection_set("0")
            t.focus("0")
        else:
            self._texto([("Ainda não há atualizações registradas.\n", "h1"),
                         ("Depois do próximo envio ao site, aparece aqui o que mudou.", "cinza")])

        # Curriculos
        grupo = {m.get("lattes"): m.get("rotulo", "") for m in rel.get("membros", [])}
        hoje = datetime.date.today()
        t = self.t_cvs
        t.delete(*t.get_children())
        linhas = []
        for i, m in site.get("membros", {}).items():
            cam = os.path.join(CACHE, i)
            baixado = datetime.date.fromtimestamp(os.path.getmtime(cam)).strftime("%d/%m/%Y") if os.path.exists(cam) else "—"
            iso = historico.data_iso(m.get("atualizado", ""))
            recente = bool(iso) and (hoje - datetime.date.fromisoformat(iso)).days <= 30
            cat = "Oculto (só publicações)" if i in site.get("ocultos", []) else grupo.get(i, "")
            linhas.append((iso, i, (m.get("nome", ""), cat, m.get("atualizado", ""), baixado), recente))
        for iso, i, vals, recente in sorted(linhas, key=lambda x: x[0], reverse=True):
            t.insert("", "end", iid=i, values=vals, tags=("recente",) if recente else ())

        self.preencher_pubs()

    def preencher_pubs(self):
        nomes = {i: m.get("nome", "") for i, m in self.site.get("membros", {}).items()}
        nomes.update(self.site.get("estrangeiros", {}))
        busca = historico_chave(self.busca.get())
        t = self.t_pubs
        t.delete(*t.get_children())
        pubs = sorted(self.site.get("publicacoes", []), key=lambda p: (str(p.get("ano") or ""), p.get("titulo", "")), reverse=True)
        n = 0
        for k, p in enumerate(pubs):
            membros = ", ".join(sorted({nomes.get(i, i) for i in p.get("lattes", [])}))
            vals = (p.get("ano", ""), historico.TIPOS.get(p.get("tipo"), p.get("tipo", "")), p.get("titulo", ""), membros, p.get("veiculo", ""))
            if busca and busca not in historico_chave(" ".join(str(v) for v in vals)):
                continue
            t.insert("", "end", iid=str(k), values=vals)
            n += 1
            if n >= 400 and not busca:
                break
        self._pubs_ordem = pubs
        total = len(pubs)
        self.conta_pubs.config(text=("%d de %d" % (n, total)) if busca else ("as %d mais recentes de %d" % (n, total) if n < total else "%d" % total))

    def mostrar_entrada(self):
        sel = self.t_hist.selection()
        if not sel:
            return
        e = self.hist[int(sel[0])]
        partes = [("%s · %s\n" % (e.get("modo", ""), quando(e["data"])), "h1"),
                  ("%d currículos · %d publicações no site\n" % (e.get("cvs", 0), e.get("publicacoes", 0)), "cinza")]
        if e.get("primeiro"):
            partes.append(("\nPrimeiro registro do histórico. A partir do próximo envio ao site, esta tela mostra o que mudou "
                           "em cada um: publicações novas e removidas, membros que entraram ou saíram e currículos atualizados.", "cinza"))
            self._texto(partes)
            return
        rot = {"periodico": "Artigos em periódicos", "congresso": "Trabalhos em congressos", "livro": "Livros e capítulos",
               "orientacoes": "Orientações", "projetos": "Projetos", "tecnica": "Produção técnica", "eventos": "Eventos"}
        if e.get("totais"):
            partes.append(("Totais que mudaram\n", "h2"))
            for k, (a, b) in e["totais"].items():
                partes += [("%s: %d → %d  " % (rot.get(k, k), a, b), "item"), (("+%d" % (b - a)) if b > a else ("−%d" % (a - b)), "mais" if b > a else "menos"), ("\n", "")]
        for chave, titulo, tag in (("entraram", "Membros que entraram", "mais"), ("sairam", "Membros que saíram", "menos")):
            if e.get(chave):
                partes.append(("%s (%d)\n" % (titulo, len(e[chave])), "h2"))
                partes += [("•  " + n + "\n", "item") for n in e[chave]]
        if e.get("cvs_atualizados"):
            partes.append(("Currículos atualizados no Lattes (%d)\n" % len(e["cvs_atualizados"]), "h2"))
            for c in e["cvs_atualizados"]:
                partes += [("•  %s  " % c["nome"], "item"), ("em %s\n" % c["data"], "cinza")]
        for chave, titulo, tag, sinal in (("novas", "Publicações novas", "mais", "+"), ("removidas", "Publicações removidas", "menos", "−")):
            lista = e.get(chave) or []
            if not lista:
                continue
            partes.append(("%s (%d)\n" % (titulo, len(lista)), "h2"))
            for p in lista[:300]:
                partes += [(sinal + "  ", tag), (p["ti"] + "\n", "ti"),
                           ("     %s%s%s\n" % (p["ano"] + " · " if p["ano"] else "", historico.TIPOS.get(p["tipo"], p["tipo"]),
                                               (" · " + ", ".join(p["m"])) if p["m"] else ""), "cinza")]
            if len(lista) > 300:
                partes.append(("… e mais %d\n" % (len(lista) - 300), "cinza"))
        if len(partes) == 2:
            partes.append(("\nNada mudou em relação ao envio anterior.", "cinza"))
        self._texto(partes)

    def _texto(self, partes):
        d = self.detalhe
        d.configure(state="normal")
        d.delete("1.0", "end")
        for txt, tag in partes:
            d.insert("end", txt, tag)
        d.configure(state="disabled")

    def _abrir_lattes(self, _e):
        sel = self.t_cvs.selection()
        if sel:
            webbrowser.open("http://lattes.cnpq.br/" + sel[0])

    def _abrir_pub(self, _e):
        sel = self.t_pubs.selection()
        if not sel:
            return
        p = self._pubs_ordem[int(sel[0])]
        if p.get("doi"):
            webbrowser.open("https://doi.org/" + p["doi"])
        else:
            webbrowser.open(SITE + "/publicacoes/")

    # ------------------------------------------------------------------ tarefas
    def rodar(self, cmd, rotulo, confirmar, dica, args=()):
        if self.proc:
            messagebox.showinfo(rotulo, "Já tem uma tarefa rodando; espere ela terminar.", parent=self)
            return
        if not acesso.tem_login():
            self.pedir_login(lambda: self.rodar(cmd, rotulo, confirmar, dica, args))
            return
        if confirmar and not messagebox.askyesno(rotulo, dica + "\n\nComeçar agora?", parent=self):
            return
        os.makedirs(LOGS, exist_ok=True)
        nome = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_" + cmd + ".txt"
        self.log_arq = open(os.path.join(LOGS, nome), "w", encoding="utf-8")
        self._escrever("\n▶ %s (%s)\n" % (rotulo, datetime.datetime.now().strftime("%d/%m/%Y %H:%M")), "cmd")
        self.n_hist = len(self.hist)
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        try:
            self.proc = subprocess.Popen([python_console(), "-u", os.path.join(AQUI, "main.py"), cmd, *args], cwd=AQUI, env=env,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as e:
            self._escrever("Não deu para começar: %s\n" % e, "erro")
            self.proc = None
            return
        threading.Thread(target=self._bombear, args=(self.proc,), daemon=True).start()
        for b in self.botoes:
            b.configure(state="disabled")
        self.parar_b.configure(state="normal")
        self.status.configure(text="Rodando: " + rotulo)
        self.barra.pack(side="right", padx=4, before=self.status)
        self.barra.start(12)
        self.abas.select(self.aba_registro)

    def _bombear(self, proc):
        for linha in iter(proc.stdout.readline, b""):
            self.fila.put(linha.decode("utf-8", "replace").replace("\r", ""))
        proc.wait()
        self.fila.put(None)

    def _ler_fila(self):
        try:
            while True:
                linha = self.fila.get_nowait()
                if linha is None:
                    self._terminou()
                else:
                    baixo = linha.lower()
                    tag = "erro" if ("erro" in baixo or "falhou" in baixo or "traceback" in baixo) else ("ok" if linha.startswith("Pronto") else "")
                    self._escrever(linha, tag)
        except queue.Empty:
            pass
        try:
            while True:
                self.ui.get_nowait()()
        except queue.Empty:
            pass
        self.after(100, self._ler_fila)

    def _escrever(self, txt, tag=""):
        self.log.configure(state="normal")
        self.log.insert("end", txt, tag)
        self.log.see("end")
        self.log.configure(state="disabled")
        if self.log_arq:
            self.log_arq.write(txt)
            self.log_arq.flush()

    def _terminou(self):
        codigo = self.proc.returncode if self.proc else 0
        self.proc = None
        self.barra.stop()
        self.barra.pack_forget()
        for b in self.botoes:
            b.configure(state="normal")
        self.parar_b.configure(state="disabled")
        self.status.configure(text="Terminou." if codigo == 0 else "Terminou com erro (veja o Registro).")
        if codigo != 0:
            self._escrever("\n(terminou com erro, código %s)\n" % codigo, "erro")
        if self.log_arq:
            self.log_arq.close()
            self.log_arq = None
        self.recarregar()
        if not self._sujo():  # a tarefa mexeu no site (publicacoes, perfis): le de novo
            self.sincronizar()
        if len(self.hist) > self.n_hist:  # houve envio ao site: mostra o que mudou
            self.abas.select(self.aba_hist)

    def parar(self):
        if self.proc and messagebox.askyesno("Parar", "Parar a tarefa agora?\n\nSe parar no meio do envio, o site fica com a versão anterior "
                                             "e o lote incompleto é apagado no próximo envio.", parent=self):
            self.proc.kill()

    def fechar(self):
        if self._sujo() and not messagebox.askyesno("Fechar", "Há alterações não salvas no site. Fechar assim mesmo?", parent=self):
            return
        if self.proc:
            if not messagebox.askyesno("Fechar", "Uma tarefa ainda está rodando. Parar e fechar?", parent=self):
                return
            self.proc.kill()
        self.destroy()


def historico_chave(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


class Dica:
    """Balao com a explicacao do botao."""

    def __init__(self, w, texto):
        self.w, self.texto, self.top = w, texto, None
        w.bind("<Enter>", self.mostrar)
        w.bind("<Leave>", self.esconder)

    def mostrar(self, _e):
        x, y = self.w.winfo_rootx(), self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.top = tk.Toplevel(self.w)
        self.top.wm_overrideredirect(True)
        self.top.wm_geometry("+%d+%d" % (x, y))
        tk.Label(self.top, text=self.texto, bg=TINTA, fg="white", relief="flat", padx=10, pady=6,
                 font=(FONTE, 9), wraplength=320, justify="left").pack()

    def esconder(self, _e):
        if self.top:
            self.top.destroy()
            self.top = None


if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)  # texto nitido em tela com escala
        # App proprio na barra de tarefas (com o icone do GEMEC), nao agrupado no pythonw
        windll.shell32.SetCurrentProcessExplicitAppUserModelID("GEMEC.PainelDoSite")
    except Exception:  # noqa: BLE001
        pass
    App().mainloop()
