"""Completa os perfis dos membros no site com o que esta no Curriculo Lattes.

So preenche campo VAZIO; o que alguem ja escreveu no painel nao e tocado:
  formacao    a mais alta (ex.: "Mestrado em andamento em Engenharia Mecanica (UNIFEI)")
  orcid       se o CV tiver
  titulacao   so egressos: maior titulo concluido (graduacao, mestrado, doutorado)
  temas       palavras-chave da formacao mais alta (ou dos projetos de pesquisa)
  foto        a do Lattes, se o membro nao tiver foto e o Lattes tiver uma

Usa os CVs ja baixados em lattes/cache/ (rode antes o download).

    python perfis.py            grava no site
    python perfis.py --simular  so mostra o que mudaria
"""
import html
import io
import os
import re
import sys

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(AQUI, "lattes", "cache")
FOTO_URL = "http://servicosweb.cnpq.br/wspessoa/servletrecuperafoto?tipo=1&id="
NIVEL = [("Pós-Doutorado", "posdoc"), ("Doutorado", "doutorado"), ("Mestrado", "mestrado"),
         ("Graduação", "graduacao"), ("Especialização", "especializacao")]
ORDEM = [k for _r, k in NIVEL]


# --- leitura do CV -----------------------------------------------------------

def _texto(s):
    s = re.sub(r"<br[^>]*>", "\n", s)
    s = re.sub(r'<span class="ajaxCAPES"[^>]*></span>', "", s)
    s = re.sub(r'<a class="tooltip-oasis".*?</a>', "", s, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def _secao(t, nome):
    i = t.find(f'<a name="{nome}"')
    if i < 0:
        return ""
    j = t.find('<div class="title-wrapper">', i)
    return t[i:j if j > 0 else i + 50000]


def _linhas(sec):
    """(rotulo da esquerda, texto da direita) de cada linha de uma secao do CV."""
    return [(_texto(a).strip(), _texto(b).strip()) for a, b in re.findall(
        r'text-align-right"><b>(.*?)</b></div></div><div class="layout-cell layout-cell-9"><div class="layout-cell-pad-5">(.*?)</div></div>',
        sec, re.S)]


def ler_cv(lid):
    t = open(os.path.join(CACHE, lid), encoding="utf-8").read()
    m = re.search(r"orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", t)
    f = re.search(r"servletrecuperafoto\?tipo=1&amp;id=(K\w+)", t)
    n = re.search(r'<h2 class="nome"[^>]*>(.*?)<', t, re.S)
    forms = []
    for anos, tx in _linhas(_secao(t, "FormacaoAcademicaTitulacao")):
        ls = [x.strip(" .") for x in tx.split("\n") if x.strip(" .")]
        if ls:
            kw = next((x.split(":", 1)[1].strip() for x in ls if x.startswith("Palavras-chave")), "")
            forms.append({"anos": anos, "curso": ls[0], "inst": ls[1] if len(ls) > 1 else "", "kw": kw})
    kw_proj = [x.split(":", 1)[1].strip(" .") for _r, tx in _linhas(_secao(t, "ProjetosPesquisa"))
               for x in tx.split("\n") if x.strip().startswith("Palavras-chave")]
    return {"orcid": m.group(1) if m else "", "foto": f.group(1) if f else "", "formacao": forms, "kw_projetos": kw_proj,
            "nome": html.unescape(n.group(1)).strip() if n else ""}


def _instituicao(inst):
    """'Universidade Federal de Itajuba, UNIFEI, Brasil' -> 'Universidade Federal de Itajuba (UNIFEI)'."""
    p = [x.strip() for x in inst.strip(" .").split(",") if x.strip()]
    if len(p) >= 3 and len(p[-2]) <= 15:
        return "%s (%s)%s" % (", ".join(p[:-2]), p[-2], "" if p[-1] == "Brasil" else ", " + p[-1])
    return ", ".join(p)


def formacao_lattes(lid):
    """Formacao academica do CV como no Lattes, da mais recente para a mais
    antiga, sem ensino medio/fundamental: anos, curso, instituicao, titulo do
    trabalho e orientacao."""
    t = open(os.path.join(CACHE, lid), encoding="utf-8").read()
    out = []
    for anos, tx in _linhas(_secao(t, "FormacaoAcademicaTitulacao")):
        ls = [x.strip() for x in tx.split("\n") if x.strip()]
        if not ls or ls[0].lower().startswith("ensino"):
            continue
        item = {"anos": re.sub(r"\s*-\s*", "–", anos.strip()), "curso": ls[0].strip(" ."),
                "inst": _instituicao(ls[1]) if len(ls) > 1 else "", "titulo": "", "orientador": "", "coorientador": ""}
        if re.fullmatch(r"\d{4}", item["anos"]) and "andamento" in item["curso"]:
            item["anos"] = "desde " + item["anos"]
        for x in ls[2:]:
            k, _, v = x.partition(":")
            k = {"Título": "titulo", "Orientador": "orientador", "Coorientador": "coorientador"}.get(k.strip())
            if k and v.strip(" ."):
                item[k] = v.strip(" .")
        out.append(item)
    return out


def areas_lattes(lid):
    """Areas de atuacao do CV (tabela do CNPq): 'Engenharia Aeroespacial · Dinamica de Voo'."""
    t = open(os.path.join(CACHE, lid), encoding="utf-8").read()
    out = []
    for _n, tx in _linhas(_secao(t, "AreasAtuacao")):
        d = {}
        for parte in tx.strip(" .").split("/"):
            k, _, v = parte.partition(":")
            d[k.strip().lower()] = v.strip(" .")
        nivel = [d.get("área") or d.get("grande área"), d.get("subárea"), d.get("especialidade")]
        txt = " · ".join(x for x in nivel if x)
        if txt and txt not in out:
            out.append(txt)
    return out


# --- regras --------------------------------------------------------------------

def _nivel(curso):
    return next((k for rot, k in NIVEL if curso.lower().startswith(rot.lower())), "")


def _em_andamento(f):
    return "andamento" in f["curso"] or not re.search(r"\d{4}\s*-\s*\d{4}", f["anos"])


def _sigla(inst):
    p = [x.strip() for x in inst.split(",")]
    return p[1] if len(p) >= 3 and p[1] and len(p[1]) <= 12 else p[0]


def formacao(cv):
    fs = sorted((f for f in cv["formacao"] if _nivel(f["curso"]) not in ("", "posdoc")), key=lambda f: ORDEM.index(_nivel(f["curso"])))
    if not fs:
        return ""
    f = fs[0]
    curso = re.sub(r"\s*\(.*?\)\s*$", "", f["curso"]).strip(" .")
    curso = re.sub(r"^(\S+) em \1 ", r"\1 em ", curso)  # "Doutorado em Doutorado Engenharia..."
    if _em_andamento(f) and "andamento" not in curso:
        curso = re.sub(r"^(\S+)", r"\1 em andamento", curso, count=1)
    return f"{curso} ({_sigla(f['inst'])})"


def titulacao(cv):
    for k in ("doutorado", "mestrado", "graduacao"):
        if any(_nivel(f["curso"]) == k and not _em_andamento(f) for f in cv["formacao"]):
            return k
    return ""


def temas(cv):
    kws = []
    for f in sorted(cv["formacao"], key=lambda f: ORDEM.index(_nivel(f["curso"])) if _nivel(f["curso"]) else 9):
        if f["kw"]:
            kws = f["kw"].split(";")
            break
    if not kws:
        kws = [k for p in cv["kw_projetos"] for k in p.split(";")]
    out = []
    for k in (k.strip(" .") for k in kws):
        if k and k.lower() not in (o.lower() for o in out):
            out.append(k[0].upper() + k[1:])
    return ", ".join(out[:5])


def foto_jpeg(kid):
    """A foto do Lattes em JPEG; None se nao houver (o Lattes devolve uma imagem padrao pequena)."""
    from PIL import Image
    r = requests.get(FOTO_URL + kid, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    try:
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    if not r.ok or min(im.size) < 150:
        return None
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def do_lattes(lid):
    """O que o cadastro de um membro pode puxar do CV ja baixado (lattes/cache/):
    nome e os campos gemec_*; a foto vai em "foto" (JPEG) ou None."""
    cv = ler_cv(lid)
    return {"nome": cv["nome"], "gemec_formacao": formacao(cv), "gemec_orcid": cv["orcid"],
            "gemec_titulacao": titulacao(cv), "gemec_temas": temas(cv),
            "foto": foto_jpeg(cv["foto"]) if cv["foto"] else None}


# --- site ----------------------------------------------------------------------

def membros(gm):
    out, pag = [], 1
    while True:
        d = gm.ok(gm.rest(f"/wp/v2/gemec_membro?context=edit&per_page=100&page={pag}"))
        out += d
        if len(d) < 100:
            return out
        pag += 1


def completar(simular=False, so=None):
    """so: ids Lattes para completar so esses membros."""
    sys.path.insert(0, AQUI)
    import gm
    gm.login()
    n = 0
    for m in membros(gm):
        me, nome = m["meta"], html.unescape(m["title"]["raw"])
        lid = re.search(r"\d{16}", me.get("gemec_lattes") or "")
        if not lid or not os.path.exists(os.path.join(CACHE, lid.group())) or (so and lid.group() not in so):
            continue
        cv = ler_cv(lid.group())
        mud = {}
        if not me.get("gemec_formacao"):
            mud["gemec_formacao"] = formacao(cv)
        if not me.get("gemec_orcid"):
            mud["gemec_orcid"] = cv["orcid"]
        if me.get("gemec_categoria") == "egresso" and not me.get("gemec_titulacao"):
            mud["gemec_titulacao"] = titulacao(cv)
        if not me.get("gemec_temas"):
            mud["gemec_temas"] = temas(cv)
        mud = {k: v for k, v in mud.items() if v}
        corpo = {"meta": mud} if mud else {}
        img = foto_jpeg(cv["foto"]) if not m.get("featured_media") and cv["foto"] else None
        if img:
            if simular:
                corpo["featured_media"] = 0
            else:
                media = gm.ok(gm.rest("/wp/v2/media", "POST", data=img, headers={
                    "Content-Type": "image/jpeg", "Content-Disposition": f'attachment; filename="lattes-{cv["foto"]}.jpg"'}))
                gm.rest(f"/wp/v2/media/{media['id']}", "POST", json={"title": nome, "alt_text": nome})
                corpo["featured_media"] = media["id"]
        if not corpo:
            continue
        if not simular:
            gm.ok(gm.rest(f"/wp/v2/gemec_membro/{m['id']}", "POST", json=corpo))
        n += 1
        o_que = [f"{k[6:]}: {v}" for k, v in mud.items()] + (["foto"] if "featured_media" in corpo else [])
        print(f"  {nome}: " + "; ".join(o_que))
    print(f"perfis: {n} {'mudariam' if simular else 'completados'}" if n else "perfis: nada a completar")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    completar(simular="--simular" in sys.argv)
