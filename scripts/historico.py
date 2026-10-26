"""Historico das atualizacoes do site, para o app (app.py).

A cada envio ao site (lattes.py enviar), registrar() tira um retrato do que foi
mandado (site.json + relatorio.json), compara com o retrato anterior e grava em
historico/historico.json o que mudou: publicacoes novas e removidas, membros que
entraram ou sairam, curriculos atualizados no Lattes e os totais.

    historico/ultimo.json      retrato do ultimo envio (base da proxima comparacao)
    historico/historico.json   uma entrada por envio, a mais nova primeiro
"""
import datetime, json, os

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
PASTA = os.path.join(RAIZ, "historico")
HISTORICO = os.path.join(PASTA, "historico.json")
ULTIMO = os.path.join(PASTA, "ultimo.json")
SITE_JSON = os.path.join(AQUI, "lattes", "site.json")
RELATORIO_JSON = os.path.join(RAIZ, "plugins", "gemec-lattes", "relatorio.json")
MAXIMO = 200  # entradas guardadas

TIPOS = {"periodico": "Artigo em periódico", "congresso": "Trabalho em congresso", "livro": "Livro ou capítulo"}


def ler(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def gravar(caminho, dados):
    os.makedirs(PASTA, exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)


def retrato():
    """O que esta no site agora, pelo que foi gerado para o ultimo envio."""
    site = ler(SITE_JSON, {})
    rel = ler(RELATORIO_JSON, {})
    membros = {i: [m.get("nome", ""), m.get("atualizado", "")] for i, m in site.get("membros", {}).items()}
    membros.update({i: [n, ""] for i, n in site.get("estrangeiros", {}).items()})  # sem Lattes (OpenAlex)
    pubs = {}
    for p in site.get("publicacoes", []):
        pubs[p["chave"]] = [p.get("titulo", ""), p.get("tipo", ""), str(p.get("ano") or ""), p.get("veiculo", ""), p.get("lattes", [])]
    totais = {t: sum(1 for p in pubs.values() if p[1] == t) for t in TIPOS}
    for k, rot in (("orientacoes", "n"), ("projetos", "n"), ("tecnica", "n")):
        if isinstance(rel.get(k), dict):
            totais[k] = rel[k].get(rot, 0)
    if isinstance(rel.get("eventos"), dict):
        totais["eventos"] = rel["eventos"].get("part", 0) + rel["eventos"].get("org", 0)
    return {"membros": membros, "pubs": pubs, "totais": totais, "ocultos": site.get("ocultos", [])}


def comparar(antes, agora):
    nomes = {i: m[0] for i, m in {**antes["membros"], **agora["membros"]}.items()}

    def item(p):
        return {"ti": p[0], "tipo": p[1], "ano": p[2], "v": p[3], "m": sorted({nomes.get(i, i) for i in p[4]})}

    novas = [item(p) for k, p in agora["pubs"].items() if k not in antes["pubs"]]
    removidas = [item(p) for k, p in antes["pubs"].items() if k not in agora["pubs"]]
    for lista in (novas, removidas):
        lista.sort(key=lambda x: (x["ano"], x["ti"]), reverse=True)
    cvs = [{"nome": m[0], "data": m[1]} for i, m in agora["membros"].items()
           if i in antes["membros"] and m[1] and m[1] != antes["membros"][i][1]]
    cvs.sort(key=lambda x: data_iso(x["data"]), reverse=True)
    totais = {k: [antes["totais"].get(k, 0), v] for k, v in agora["totais"].items() if antes["totais"].get(k, 0) != v}
    return {
        "novas": novas,
        "removidas": removidas,
        "entraram": sorted(m[0] for i, m in agora["membros"].items() if i not in antes["membros"]),
        "sairam": sorted(m[0] for i, m in antes["membros"].items() if i not in agora["membros"]),
        "cvs_atualizados": cvs,
        "totais": totais,
    }


def data_iso(dmy):
    """'16/10/2026' -> '2026-10-16' (ordena); vazio se nao for data."""
    try:
        return datetime.datetime.strptime(dmy, "%d/%m/%Y").date().isoformat()
    except (TypeError, ValueError):
        return ""


def registrar(modo="envio"):
    """Chamado depois de um envio que deu certo. Devolve a entrada gravada."""
    agora = retrato()
    antes = ler(ULTIMO, None)
    entrada = {"data": datetime.datetime.now().isoformat(timespec="seconds"), "modo": modo,
               "cvs": len(set(agora["membros"]) - set(agora["ocultos"])), "publicacoes": len(agora["pubs"])}
    if antes:
        entrada.update(comparar(antes, agora))
    else:
        entrada["primeiro"] = True
    hist = ler(HISTORICO, [])
    hist.insert(0, entrada)
    gravar(HISTORICO, hist[:MAXIMO])
    gravar(ULTIMO, agora)
    return entrada


def resumo(e):
    """Uma linha para a lista do app."""
    if e.get("primeiro"):
        return "Primeiro registro: %d publicações, %d currículos" % (e["publicacoes"], e["cvs"])
    partes = []
    if e.get("novas"):
        partes.append("+%d publicaç%s" % (len(e["novas"]), "ões" if len(e["novas"]) > 1 else "ão"))
    if e.get("removidas"):
        partes.append("−%d removida%s" % (len(e["removidas"]), "s" if len(e["removidas"]) > 1 else ""))
    if e.get("entraram"):
        partes.append("%d membro%s novo%s" % (len(e["entraram"]), *(("s", "s") if len(e["entraram"]) > 1 else ("", ""))))
    if e.get("sairam"):
        partes.append("%d saiu" % len(e["sairam"]) if len(e["sairam"]) == 1 else "%d saíram" % len(e["sairam"]))
    if e.get("cvs_atualizados"):
        n = len(e["cvs_atualizados"])
        partes.append("%d currículo%s atualizado%s" % (n, *(("s", "s") if n > 1 else ("", ""))))
    return ", ".join(partes) if partes else "Nada mudou"
