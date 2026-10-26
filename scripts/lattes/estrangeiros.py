"""Publicacoes do OpenAlex para os membros sem Lattes (pesquisadores
estrangeiros), como no Altimetro.

O membro e achado pelo ORCID do cadastro no site (sem Lattes de 16 digitos).
As obras dele entram no site.json junto com as do Lattes: o que ja veio de
algum CV (mesmo DOI ou titulo) so ganha o membro; o resto vira publicacao
nova. Ficam ligadas a ele pela chave "orcid:<ORCID>", que o plugin
gemec-lattes casa com o campo ORCID do cadastro. Coautores do grupo sao
reconhecidos pelo ORCID ou pelo nome de citacao (mesma regra de extrair.py).

A ultima copia de cada membro fica em openalex/<ORCID>.json: se o OpenAlex
nao responder, vale a anterior (como o cache dos CVs).
"""
import html
import json
import os
import re
import sys

from rapidfuzz import fuzz

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import busca  # noqa: E402
from extrair import chave_nome, doi_de, limpar, titulo_norm  # noqa: E402

PASTA = os.path.join(AQUI, "openalex")
CAMPOS = "id,title,publication_year,type,doi,primary_location,authorships"


def chave(orcid):
    return "orcid:" + orcid.upper()


def obras(orcid):
    out = []
    for pagina in range(1, 26):  # ate 5 mil obras; page= nao pede chave de API
        d = busca._get("https://api.openalex.org/works", params={
            "filter": "author.orcid:" + orcid, "per-page": 200, "page": pagina, "select": CAMPOS})
        res = d.get("results") or []
        out += res
        if len(res) < 200:
            return out
    return out


def baixar(orcid, nome):
    arq = os.path.join(PASTA, orcid.upper() + ".json")
    try:
        ws = obras(orcid)
    except Exception as e:  # noqa: BLE001 - um membro com problema nao para os outros
        velho = os.path.exists(arq)
        print(f"  OpenAlex falhou para {nome}: {type(e).__name__}" + (" (fica a copia anterior)" if velho else ""))
        return json.load(open(arq, encoding="utf-8")) if velho else []
    os.makedirs(PASTA, exist_ok=True)
    with open(arq, "w", encoding="utf-8") as f:
        json.dump(ws, f, ensure_ascii=False)
    return ws


def tipo_de(w):
    """Tipo no site; None para o que o site nao mostra (preprint, dataset...)."""
    t = w.get("type") or ""
    fonte = ((w.get("primary_location") or {}).get("source") or {}).get("type") or ""
    if t in ("article", "review", "letter"):
        return {"journal": "periodico", "conference": "congresso"}.get(fonte)
    if t == "proceedings-article":
        return "congresso"
    if t in ("book", "book-chapter"):
        return "livro"
    return None


def juntar(site, estrangeiros, orcids):
    """estrangeiros: {ORCID: nome} dos membros sem Lattes.
    orcids: {ORCID: chave do membro} de todos os membros com ORCID (id16 de
    quem tem Lattes, "orcid:..." de quem nao tem). Mexe em site["publicacoes"]."""
    pubs = site["publicacoes"]
    chaves = {k: set(v) for k, v in site.get("chaves", {}).items()}
    for orcid, nome in estrangeiros.items():
        k = chave_nome(nome)
        if k:
            chaves.setdefault(k, set()).add(chave(orcid))
    por_doi = {p["doi"]: p for p in pubs if p.get("doi")}
    por_tn = {titulo_norm(p["titulo"]): p for p in pubs}
    total = {"novas": 0, "ja_no_lattes": 0}

    for orcid, nome in sorted(estrangeiros.items(), key=lambda x: x[1]):
        print(f"  OpenAlex: {nome} ({orcid})")
        dono = chave(orcid)
        for w in baixar(orcid, nome):
            tipo = tipo_de(w)
            titulo = limpar(html.unescape(w.get("title") or ""))
            if not tipo or len(titulo) < 5:
                continue
            doi = doi_de(w.get("doi"))
            ano = str(w.get("publication_year") or "")
            ano = ano if re.fullmatch(r"\d{4}", ano) else ""
            autores, quem = [], {dono}
            for a in w.get("authorships") or []:
                au = a.get("author") or {}
                n = limpar(au.get("display_name") or "")
                if not n:
                    continue
                o = re.search(busca.ORCID_RE, au.get("orcid") or "")
                ids = set(chaves.get(chave_nome(n), set()))
                if o and o.group().upper() in orcids:
                    ids.add(orcids[o.group().upper()])
                quem |= ids
                autores.append({"nome": n, "membro": bool(ids)})

            tn = titulo_norm(titulo)
            igual = (por_doi.get(doi) if doi else None) or por_tn.get(tn)
            if igual is None and len(tn) >= 25:
                igual = next((p for p in pubs if abs(int(p.get("ano") or 0) - int(ano or 0)) <= 1
                              and fuzz.ratio(tn[:200], titulo_norm(p["titulo"])[:200]) >= 92), None)
            if igual is not None:
                igual["lattes"] = sorted(set(igual["lattes"]) | quem)
                for a in igual["autores"]:  # o estrangeiro em negrito tambem no item do Lattes
                    if chave_nome(a["nome"]) == chave_nome(nome):
                        a["membro"] = True
                if not igual.get("doi") and doi:
                    igual["doi"] = doi
                total["ja_no_lattes"] += 1
                continue
            item = {"chave": ("doi:" + doi) if doi else ("t:" + tn[:150] + ":" + ano), "titulo": titulo, "tipo": tipo,
                    "ano": ano, "doi": doi, "veiculo": limpar(((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""),
                    "autores": autores, "lattes": sorted(quem)}
            pubs.append(item)
            total["novas"] += 1
            if doi:
                por_doi[doi] = item
            por_tn[tn] = item
    site["estrangeiros"] = {chave(o): n for o, n in estrangeiros.items()}
    return total
