"""Busca de pesquisadores no ORCID e no OpenAlex, como no Altimetro: pelo nome
(para escolher entre homonimos) ou pelo ORCID. Serve so para preencher o
cadastro do membro (ORCID, temas); as publicacoes do site continuam vindo so
do Lattes.
"""
import re

import requests

ORCID_RE = r"\d{4}-\d{4}-\d{4}-\d{3}[\dXx]"
AGENTE = "GEMEC painel do site (https://gemec.unifei.edu.br)"
CAMPOS_OA = "id,display_name,orcid,works_count,last_known_institutions,topics,counts_by_year"
PARTICULAS = {"da", "de", "do", "das", "dos", "e"}


def _get(url, **kw):
    r = requests.get(url, headers={"User-Agent": AGENTE, "Accept": "application/json"}, timeout=60, **kw)
    r.raise_for_status()
    return r.json()


def _oa(a):
    anos = [c["year"] for c in a.get("counts_by_year") or [] if c.get("works_count")]
    orcid = re.search(ORCID_RE, a.get("orcid") or "")
    return {"fonte": "OpenAlex", "id": (a.get("id") or "").rsplit("/", 1)[-1], "nome": a.get("display_name", ""),
            "orcid": orcid.group().upper() if orcid else "", "obras": a.get("works_count", 0),
            "instituicao": ", ".join(i.get("display_name", "") for i in a.get("last_known_institutions") or []),
            "temas": ", ".join(t.get("display_name", "") for t in (a.get("topics") or [])[:5]),
            "anos": f"{min(anos)}–{max(anos)}" if anos else ""}


def openalex(texto):
    """Perfis de autor do OpenAlex pelo nome, ou o perfil de um ORCID."""
    m = re.search(ORCID_RE, texto)
    if m:
        try:
            return [_oa(_get(f"https://api.openalex.org/authors/orcid:{m.group()}", params={"select": CAMPOS_OA}))]
        except requests.HTTPError:
            return []
    d = _get("https://api.openalex.org/authors", params={"search": texto, "per-page": 25, "select": CAMPOS_OA})
    return [_oa(a) for a in d.get("results") or []]


def _orcid_item(x):
    return {"fonte": "ORCID", "id": x.get("orcid-id", ""), "orcid": x.get("orcid-id", ""),
            "nome": " ".join(p for p in (x.get("given-names"), x.get("family-names")) if p),
            "instituicao": ", ".join((x.get("institution-name") or [])[:3]), "obras": "", "anos": "", "temas": ""}


def orcid(texto):
    """Registros do ORCID pelo nome (primeiro nome + ultimo sobrenome), ou um ORCID."""
    m = re.search(ORCID_RE, texto)
    if m:
        q = "orcid:" + m.group()
    else:
        partes = [p for p in re.findall(r"[^\W\d_]+", texto) if p.lower() not in PARTICULAS]
        if not partes:
            return []
        q = f"given-names:{partes[0]}" + (f" AND family-name:{partes[-1]}" if len(partes) > 1 else "")
        if len(partes) > 2:  # sobrenomes do meio, se o ORCID tiver
            q += " AND (" + " OR ".join(f"family-name:{p}" for p in partes[1:-1]) + f" OR family-name:{partes[-1]})"
    d = _get("https://pub.orcid.org/v3.0/expanded-search/", params={"q": q, "rows": 25})
    return [_orcid_item(x) for x in d.get("expanded-result") or []]


def link(item):
    if item["fonte"] == "ORCID":
        return "https://orcid.org/" + item["orcid"]
    return "https://openalex.org/" + item["id"]
