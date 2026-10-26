"""Conteudo do site do GEMEC pela REST API do WordPress, para a aba "Conteúdo do
site" do app: membros, linhas de pesquisa, publicacoes, oportunidades,
parceiros e paginas.

Os campos de cada tipo espelham as caixas do painel do WordPress (plugins
gemec-core e gemec-parceiros); se um campo mudar la, tem que mudar aqui.
As chamadas ficam atras de uma trava: o app as faz fora da thread da janela.
"""
import html
import os
import re
import threading

import acesso
import gm

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = gm.BASE
SITUACOES = "publish,future,draft,pending,private"

_trava = threading.Lock()
_logado = False


class ErroSite(Exception):
    pass


# --- campos -------------------------------------------------------------------
# (chave do meta, rotulo, tipo, opcoes, dica)
# tipos: texto, longo, lista (opcoes = [(valor, rotulo)]), data, marca, membros, arquivo

CATEGORIAS = [("professor", "Professores pesquisadores"), ("visitante", "Pesquisadores visitantes"),
              ("posdoc", "Pós-doutorado"), ("doutorado", "Doutorado"), ("mestrado", "Mestrado"),
              ("graduacao", "Graduação"), ("egresso", "Egressos")]

ICONES = [("trelica", "Treliça (estruturas)"), ("onda", "Onda (vibrações)"), ("pulso", "Lupa e sinal (monitoramento)"),
          ("ajuste", "Ajustes (otimização)"), ("camadas", "Camadas (compósitos)"), ("rede", "Rede neural (inteligência artificial)"),
          ("aviao", "Aeronave (controle de voo)"), ("malha", "Malha (elementos finitos)"), ("engrenagem", "Engrenagem (projeto mecânico)")]

TIPOS_PUB = [("periodico", "Artigo em periódico"), ("congresso", "Trabalho em congresso"), ("livro", "Livro ou capítulo")]

TIPOS_VAGA = [("posdoc", "Pós-doutorado"), ("doutorado", "Doutorado"), ("mestrado", "Mestrado"),
              ("ic", "Iniciação científica"), ("tcc", "TCC"), ("outro", "Outra")]

GRUPOS_PARCEIRO = [("laboratorio", "Laboratórios parceiros"), ("fomento", "Agências de fomento e instituições"),
                   ("empresa", "Empresas"), ("tecnologia", "Equipamentos e software")]

PUBLICADO = [("publish", "Publicado"), ("draft", "Rascunho")]

TIPOS = {
    "membros": {
        "rotulo": "Membros", "singular": "membro", "rest": "gemec_membro", "titulo": "Nome", "foto": "Foto",
        "ordem": True, "pagina": "/membros/",
        "situacoes": [("publish", "Publicado"), ("private", "Oculto (só publicações)"), ("draft", "Rascunho")],
        "colunas": [("titulo", "Nome", 250), ("gemec_categoria", "Categoria", 170), ("situacao", "Situação", 150), ("ordem", "Ordem", 60)],
        "dica": "Oculto: o Lattes é importado e os papers aparecem em Publicações, mas a pessoa some de Membros e das estatísticas.",
        "campos": [
            ("gemec_categoria", "Categoria", "lista", CATEGORIAS, "Seção da página Membros em que a pessoa aparece.", "graduacao"),
            ("gemec_lattes", "Currículo Lattes", "texto", None, "URL completa, ex.: http://lattes.cnpq.br/0000000000000000. "
             "Dele vêm resumo, publicações e estatísticas a cada atualização."),
            ("gemec_orcid", "ORCID", "texto", None, "Ex.: 0000-0003-0811-6334. Quem não tem Lattes (pesquisador estrangeiro) "
             "tem as publicações trazidas do OpenAlex por este ORCID."),
            ("gemec_destaque", "Destaque", "lista", [("", "Não"), ("1", "Sim — fixo no topo da seção")],
             "Quem está em destaque aparece primeiro, na ordem do campo Ordem. Os demais, pelo número de publicações.", ""),
            ("gemec_titulacao", "Titulação (egressos)", "lista", [("", "Não informada"), ("doutorado", "Doutorado"), ("mestrado", "Mestrado"), ("graduacao", "Graduação")],
             "Só para egressos: a maior titulação. Separa Egressos em Doutores, Mestres e Graduação.", ""),
            ("gemec_papel", "Papel", "texto", None, "Ex.: Líder do grupo, Vice-líder, Bolsista de IC. Vazio não exibe."),
            ("gemec_formacao", "Formação / vínculo", "texto", None, "Ex.: Doutor em Engenharia Mecânica (UNIFEI). Para egressos, o que fazem hoje."),
            ("gemec_temas", "Temas de pesquisa", "longo", None, "Separados por vírgula. Viram etiquetas no card e no perfil."),
            ("gemec_bio", "Biografia", "longo", None, "Um ou dois parágrafos, exibidos no perfil. Aceita <strong> e <em>. Vazia, o site usa o resumo do Lattes."),
            ("gemec_email", "E-mail", "texto", None, "Só o endereço, sem mailto:"),
            ("gemec_scholar", "Google Acadêmico", "texto", None, "URL completa do perfil."),
            ("gemec_rg", "ResearchGate", "texto", None, "URL completa do perfil."),
            ("gemec_linkedin", "LinkedIn", "texto", None, "URL completa do perfil."),
            ("gemec_github", "GitHub", "texto", None, "URL completa do perfil, ex.: https://github.com/usuario"),
        ],
    },
    "linhas": {
        "rotulo": "Linhas de pesquisa", "singular": "linha de pesquisa", "rest": "gemec_linha", "titulo": "Título",
        "ordem": True, "pagina": "/pesquisa/", "situacoes": PUBLICADO,
        "colunas": [("titulo", "Linha", 320), ("situacao", "Situação", 110), ("ordem", "Ordem", 60)],
        "dica": "Aparecem na página Pesquisa e nos cards da página inicial, na ordem do campo Ordem.",
        "campos": [
            ("gemec_icone", "Ícone", "lista", ICONES, "Desenho que aparece no topo do card.", "trelica"),
            ("gemec_resumo", "Descrição curta", "longo", None, "Um ou dois períodos. Aparece nos cards da página inicial."),
            ("gemec_topicos", "Tópicos", "longo", None, "Um tópico por linha. Aparecem como lista na página Pesquisa."),
        ],
    },
    "publicacoes": {
        "rotulo": "Publicações", "singular": "publicação", "rest": "gemec_publicacao", "titulo": "Título",
        "novo": False, "pagina": "/publicacoes/", "situacoes": PUBLICADO,
        "colunas": [("gemec_data", "Data", 90), ("gemec_tipo", "Tipo", 150), ("titulo", "Título", 380), ("oculta", "No site", 80)],
        "dica": "Vêm só do Currículo Lattes e são refeitas a cada atualização: edições aqui são sobrescritas. "
                "A marca Ocultar se mantém. Selecione várias na lista para ocultar ou mostrar de uma vez.",
        "campos": [
            ("gemec_oculta", "Ocultar do site", "marca", None, "Para um trabalho errado ou repetido. A importação do Lattes respeita esta marca."),
            ("gemec_tipo", "Tipo", "lista", TIPOS_PUB, "", "periodico"),
            ("gemec_data", "Data de publicação", "data", None, "AAAA-MM-DD. Define a ordem na página."),
            ("gemec_autores", "Autores", "longo", None, "Membros do GEMEC entre <strong>...</strong>."),
            ("gemec_veiculo", "Veículo", "texto", None, "Revista, congresso ou livro."),
            ("gemec_doi", "DOI", "texto", None, "Só o código, ex.: 10.1007/s00366-018-0620-8"),
            ("gemec_pdf", "PDF de acesso aberto", "texto", None, ""),
            ("gemec_link", "Link", "texto", None, "Usado quando não há DOI."),
            ("gemec_membros", "Membros do GEMEC nesta publicação", "membros", None, "Clique num nome para marcar ou desmarcar."),
        ],
    },
    "oportunidades": {
        "rotulo": "Oportunidades", "singular": "oportunidade", "rest": "gemec_vaga", "titulo": "Título",
        "ordem": True, "pagina": "/oportunidades/", "situacoes": PUBLICADO,
        "colunas": [("titulo", "Vaga", 280), ("gemec_tipo", "Tipo", 140), ("aberta", "Inscrições", 110), ("gemec_prazo", "Prazo", 90), ("situacao", "Situação", 90)],
        "dica": "O título é o nome da vaga no card. Depois do prazo a vaga passa sozinha para Encerradas.",
        "campos": [
            ("gemec_tipo", "Tipo de vaga", "lista", TIPOS_VAGA, "", "ic"),
            ("gemec_resumo", "Descrição", "longo", None, "Uma ou duas frases: tema, bolsa, requisitos. Aceita <strong> e <em>."),
            ("gemec_link", "Edital", "arquivo", None, "Link do edital (Google Drive, site da PRPPG) ou envie o PDF pelo botão."),
            ("gemec_rotulo", "Texto do botão", "texto", None, "Opcional. Padrão: “Acessar o edital”."),
            ("gemec_inicio", "Inscrições a partir de", "data", None, "Opcional. AAAA-MM-DD."),
            ("gemec_prazo", "Inscrições até", "data", None, "Opcional. AAAA-MM-DD. Sem data, fica aberta até alguém tirá-la."),
        ],
    },
    "parceiros": {
        "rotulo": "Parceiros", "singular": "parceiro", "rest": "gemec_parceiro", "titulo": "Nome", "foto": "Logo",
        "ordem": True, "pagina": "/parceiros/", "situacoes": PUBLICADO,
        "colunas": [("titulo", "Parceiro", 300), ("gemec_grupo", "Grupo", 210), ("situacao", "Situação", 90), ("ordem", "Ordem", 60)],
        "dica": "Para laboratórios, o nome por extenso. Prefira logo PNG com fundo transparente.",
        "campos": [
            ("gemec_grupo", "Grupo", "lista", GRUPOS_PARCEIRO, "Em qual bloco da página Parceiros ele aparece.", "empresa"),
            ("gemec_sigla", "Sigla", "texto", None, "Para laboratórios: ex.: LVA. Aparece no lugar do logo quando não houver imagem."),
            ("gemec_descricao", "Descrição", "longo", None, "Para laboratórios: uma ou duas frases sobre o laboratório e a colaboração."),
            ("gemec_url", "Site", "texto", None, "Opcional. Com endereço, o logo ou o card vira link."),
        ],
    },
    "paginas": {
        "rotulo": "Páginas", "singular": "página", "rest": "pages", "titulo": "Título", "conteudo": True,
        "ordem": True, "situacoes": [("publish", "Publicado"), ("draft", "Rascunho"), ("private", "Privado")],
        "colunas": [("titulo", "Página", 300), ("slug", "Endereço", 180), ("situacao", "Situação", 90)],
        "dica": "O conteúdo está em blocos do editor do WordPress. O texto padrão das páginas está em scripts/paginas.py; "
                "rodar publicar.py sobrescreve o que for editado aqui.",
        "campos": [],
    },
}


def opcao(campo):
    return campo[5] if len(campo) > 5 else ""


def rotulo_de(tipo, chave, valor):
    """Rotulo legivel de um valor de lista (para as colunas)."""
    for c in TIPOS[tipo]["campos"]:
        if c[0] == chave and c[2] == "lista":
            return dict(c[3]).get(valor, valor)
    return valor


# --- acesso ---------------------------------------------------------------------

def _login():
    """Entra com o login de config.json (acesso.py), limpando a sessao anterior."""
    global _logado
    c = acesso.aplicar()
    gm.USER = c["usuario"]
    gm.s.cookies.clear()
    gm.s.headers.pop("X-WP-Nonce", None)
    _logado = False
    try:
        gm.login()
    except SystemExit:
        raise ErroSite("Não deu para entrar no site com o usuário “%s”. Confira usuário e senha em Configurações." % c["usuario"]) from None
    _logado = True


def sair():
    """Esquece a sessao: o proximo pedido entra de novo (login trocado)."""
    global _logado
    with _trava:
        _logado = False


def eu():
    """Quem esta logado: nome, usuario e papeis."""
    d = _pedir("/wp/v2/users/me?context=edit&_fields=id,name,username,roles,email").json()
    return {"nome": d.get("name", ""), "usuario": d.get("username", ""), "papeis": d.get("roles", []), "email": d.get("email", "")}


def testar_login(usuario, senha):
    """Tenta entrar com outro login sem mexer no atual; devolve eu() dele."""
    import requests
    s = requests.Session()
    s.verify = gm.s.verify
    s.headers.update(gm.s.headers)
    s.headers.pop("X-WP-Nonce", None)
    try:
        s.get(gm.BASE + "/wp-login.php", timeout=60)
        s.post(gm.BASE + "/wp-login.php", data={"log": usuario, "pwd": senha, "wp-submit": "Log In",
               "redirect_to": gm.BASE + "/wp-admin/", "testcookie": "1"}, timeout=60)
    except OSError as e:
        raise ErroSite("Sem resposta do site: %s" % e) from None
    if not any(c.name.startswith("wordpress_logged_in") for c in s.cookies):
        raise ErroSite("Usuário ou senha não conferem.")
    return usuario


def trocar_senha(nova):
    """Muda a senha do usuario logado no WordPress e grava em config.json."""
    _pedir("/wp/v2/users/me", "POST", json={"password": nova})
    acesso.gravar(acesso.ler()["usuario"], nova)
    sair()


def _pedir(caminho, metodo="GET", **kw):
    kw.setdefault("timeout", 90)
    with _trava:
        if not _logado:
            _login()
        try:
            r = gm.rest(caminho, metodo, **kw)
            if r.status_code in (401, 403) and "nonce" in r.text:  # sessao venceu com o app aberto
                _login()
                r = gm.rest(caminho, metodo, **kw)
        except OSError as e:
            raise ErroSite("Sem resposta do site: %s" % e) from None
    if r.status_code >= 400:
        try:
            msg = r.json().get("message") or r.text[:300]
        except ValueError:
            msg = r.text[:300]
        raise ErroSite("O site recusou (%s): %s" % (r.status_code, re.sub(r"<[^>]+>", "", msg)))
    return r


def _item(d):
    meta = d.get("meta") or {}
    if not isinstance(meta, dict):  # sem metadados registrados o WordPress manda []
        meta = {}
    return {
        "id": d["id"],
        "titulo": html.unescape((d.get("title") or {}).get("raw", "")),
        "situacao": d.get("status", ""),
        "ordem": d.get("menu_order", 0),
        "meta": meta,
        "foto": d.get("featured_media", 0),
        "link": d.get("link", ""),
        "slug": d.get("slug", ""),
        "conteudo": (d.get("content") or {}).get("raw", ""),
    }


def listar(tipo):
    t = TIPOS[tipo]
    campos = "id,title,status,menu_order,meta,featured_media,link,slug" + (",content" if t.get("conteudo") else "")
    # Ordem por id: pela data (padrao) as paginas repetem itens de mesma data.
    out, pag = {}, 1
    while True:
        r = _pedir(f"/wp/v2/{t['rest']}?context=edit&per_page=100&page={pag}&status={SITUACOES}&orderby=id&order=asc&_fields={campos}")
        out.update((d["id"], _item(d)) for d in r.json())
        if pag >= int(r.headers.get("X-WP-TotalPages", 1)):
            return list(out.values())
        pag += 1


def salvar(tipo, id_, corpo):
    """Cria (id_ None) ou atualiza. corpo no formato da REST API (title, status, meta...)."""
    t = TIPOS[tipo]
    caminho = f"/wp/v2/{t['rest']}" + (f"/{id_}" if id_ else "")
    r = _pedir(caminho + "?context=edit", "POST", json=corpo)
    return _item(r.json())


def lixeira(tipo, id_):
    _pedir(f"/wp/v2/{TIPOS[tipo]['rest']}/{id_}", "DELETE")


def enviar_arquivo(caminho, titulo=""):
    """Sobe um arquivo para a biblioteca de midia; devolve {id, url}."""
    ext = os.path.splitext(caminho)[1].lower()
    tipo = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".svg": "image/svg+xml", ".pdf": "application/pdf"}.get(ext, "application/octet-stream")
    nome = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(caminho))
    with open(caminho, "rb") as f:
        dados = f.read()
    m = _pedir("/wp/v2/media", "POST", data=dados, headers={"Content-Type": tipo, "Content-Disposition": f'attachment; filename="{nome}"'}).json()
    if titulo:
        _pedir(f"/wp/v2/media/{m['id']}", "POST", json={"title": titulo, "alt_text": titulo})
    return {"id": m["id"], "url": m.get("source_url", "")}


def miniatura(media_id):
    """Bytes da miniatura de uma imagem da biblioteca (None se nao houver)."""
    if not media_id:
        return None
    try:
        m = _pedir(f"/wp/v2/media/{media_id}?_fields=source_url,media_details").json()
    except ErroSite:
        return None
    tamanhos = (m.get("media_details") or {}).get("sizes") or {}
    url = (tamanhos.get("thumbnail") or tamanhos.get("medium") or {}).get("source_url") or m.get("source_url")
    if not url:
        return None
    with _trava:
        try:
            r = gm.s.get(url, timeout=60)
        except OSError:
            return None
    return r.content if r.ok else None


def painel(id_):
    return f"{SITE}/wp-admin/post.php?post={id_}&action=edit"
