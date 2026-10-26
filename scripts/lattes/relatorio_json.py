"""Resume o relatorio do scriptLattes para a pagina Estatisticas.

Cada pagina do relatorio traz os itens ja sem duplicatas em `const DATA = [...]`.
Daqui saem dois arquivos no plugin gemec-lattes:

  relatorio.json  contagens, membros com as metricas, premios e o grafo de
                  colaboracao (lido pelo PHP a cada visita; pequeno)
  listas.json     todos os itens (producao bibliografica, tecnica e artistica,
                  orientacoes, projetos e eventos), cada um com os membros em
                  cujo curriculo aparece (lido pelo navegador, sob demanda)

Os membros de cada item vem das paginas por membro (membro-<id>.html). Chamado
por lattes.py gerar; tambem roda sozinho:

    python relatorio_json.py <pasta do relatorio> <pasta de destino>
"""
import glob, json, os, re, sys, unicodedata

ORIENTACAO = {"0": "posdoc", "1": "doutorado", "2": "mestrado", "3": "especializacao", "4": "tcc", "5": "ic", "6": "outra"}


def limpar(s, maximo=0):
    s = re.sub(r"\s+", " ", str(s if s is not None else "")).strip()
    # o scriptLattes troca travessoes e hifens especiais por "?",
    # e aspas curvas tambem: "?" abrindo uma palavra vira aspas (no inicio, some)
    s = re.sub(r"(?<=\w)\?(?=\w)", "-", s).replace(" ? ", " – ")
    abriu = bool(re.match(r"^\?\s*\w", s))
    s = re.sub(r"(?<=\s)\?(?=\w)", '"', re.sub(r"^\?\s*(?=\w)", "", s))
    s = re.sub(r'("[^"?]{1,200})\?(?=[\s.,;:)]|$)', r'\1"', s)  # fecha as aspas abertas acima
    if abriu:  # a aspa de abertura sumiu: some tambem a de fechamento
        s = re.sub(r"(?<=\w)\?(?=[,;:)]|$)", "", s, count=1)
    if maximo and len(s) > maximo:
        s = s[:maximo].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"
    return s


def chave(s):
    """Texto so com letras e numeros, sem acento: compara itens entre paginas."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def curso(s):
    """'Tese (Doutorado em X) - Universidade Y' -> 'Doutorado em X · Universidade Y'."""
    s = limpar(s, 220)
    m = re.match(r"^[^()]*\(([^)]*)\)?\s*-\s*(.+)$", s) or re.match(r"^\(?([^)]*)\)\s*-\s*(.+)$", s)
    return (m.group(1).strip() + " · " + m.group(2).strip()) if m else s.strip("(). ")


def ano(x):
    a = str(x.get("ano") or "")
    return int(a) if re.fullmatch(r"\d{4}", a) else 0


def ler(pasta, nome, var="DATA"):
    """(titulo h3, DATA) de uma pagina do relatorio; ('', []) se nao existir."""
    arq = os.path.join(pasta, nome)
    if not os.path.exists(arq):
        return "", []
    h = open(arq, encoding="utf-8", errors="replace").read()
    t = re.search(r"<h3>(.*?)</h3>", h)
    m = re.search(r"(?:const|var) " + var + r" = (\[.*?\]|\{.*?\});\s*\n", h, re.S)
    return (limpar(re.sub(r"<[^>]+>", "", t.group(1))) if t else ""), (json.loads(m.group(1)) if m else [])


def paginas(pasta, prefixo):
    """[(codigo, rotulo, DATA)] das paginas <prefixo><n>-0.html (ex.: PB0, PB1...)."""
    out = []
    for arq in sorted(glob.glob(os.path.join(pasta, prefixo + "[0-9]-0.html"))):
        rot, d = ler(pasta, os.path.basename(arq))
        if d:
            out.append((os.path.basename(arq).split("-")[0], rot, d))
    return out


def secoes_dos_membros(pasta, ids):
    """{id Lattes: {secao: texto normalizado}} das paginas por membro."""
    out = {}
    for lid in ids:
        arq = os.path.join(pasta, "membro-%s.html" % lid)
        if not os.path.exists(arq):
            continue
        h = open(arq, encoding="utf-8", errors="replace").read()
        # "Lista de colaboracoes" repete as producoes em comum: fica de fora.
        h = h[:h.rfind("Lista de colabora")] if "Lista de colabora" in h else h
        partes = re.split(r'<li id="((?:PB|PT|PA|OA|OC)\d|Pj0|Pm0|Ep0|Eo0)">', h)
        secs = {}
        for i in range(1, len(partes) - 1, 2):
            secs[partes[i]] = secs.get(partes[i], "") + "|" + chave(re.sub(r"<[^>]+>", " ", partes[i + 1]))
        out[lid] = secs
    return out


def quem(secs, secao, *textos, todos=False):
    """Indices dos membros em cuja pagina (secao) aparece o primeiro texto util
    (com todos=True, todos os textos nao vazios: titulos repetidos entre alunos)."""
    ks = [chave(t)[:90] for t in textos]
    ks = [k for k in ks if len(k) >= 6] if todos else [next((k for k in ks if len(k) >= 10), max(ks, key=len, default=""))]
    ks = [k for k in ks if len(k) >= 6]
    if not ks:
        return []
    return [i for i, (_lid, s) in enumerate(secs) if all(k in s.get(secao, "") for k in ks)]


def mais(d, *ks):
    for k in ks[:-1]:
        d = d.setdefault(k, {})
    d[ks[-1]] = d.get(ks[-1], 0) + 1


def por_autores(chaves, pos):
    """Funcao: texto de autores -> indices dos membros citados, pela mesma regra
    de extrair.py (nome de citacao), que e a que liga as publicacoes do site
    aos membros. Sem o mapa (site.json antigo), nao atribui nada."""
    if not chaves:
        return lambda au: set()
    from extrair import chave_nome  # noqa: E402 (o mesmo criterio do site)

    def f(au):
        out = set()
        for a in re.split(r"\s*;\s*", str(au or "")):
            for lid in chaves.get(chave_nome(a), ()):
                if lid in pos:
                    out.add(pos[lid])
        return out
    return f


def resumir(pasta, destino, data="", cvs=0, site_json=None):
    _, dm = ler(pasta, "membros.html", "DATA_MEMBROS")
    _, met = ler(pasta, "metricas.html")
    met = met or {}
    ids = [m["id_lattes"] for m in dm]
    secs_por_id = secoes_dos_membros(pasta, ids)
    secs = [(lid, secs_por_id.get(lid, {})) for lid in ids]

    # Membros, na ordem do relatorio, com as metricas das tres tabelas.
    por_nome = {}
    for tab in ("producao", "orientacoes", "projetos"):
        for linha in met.get(tab, []):
            por_nome.setdefault(linha["nome"], {}).update(linha)
    campos = {"pb_total": "pb", "periodicos": "periodicos", "livros": "livros", "capitulos": "capitulos", "congressos": "congressos",
              "resumos": "resumos", "aceitos": "aceitos", "tec_total": "tec", "art_total": "art", "concl_total": "oc", "and_total": "oa",
              "concl_dout": "oc_dout", "concl_mest": "oc_mest", "concl_tcc": "oc_tcc", "concl_ic": "oc_ic", "concl_posdoc": "oc_posdoc",
              "concl_espec": "oc_espec", "and_dout": "oa_dout", "and_mest": "oa_mest", "and_tcc": "oa_tcc", "and_ic": "oa_ic",
              "and_posdoc": "oa_posdoc", "projetos": "projetos", "premios": "premios", "part_event": "ev_part", "org_event": "ev_org"}
    membros = []
    for m in dm:
        x = por_nome.get(m["nome"], {})
        membros.append({"lattes": m["id_lattes"], "nome": limpar(m["nome"]), "rotulo": limpar(m.get("rotulo_grupo")),
                        "bolsa": limpar(m.get("bolsa")), "atualizacao": limpar(m.get("atualizacao")),
                        "area": limpar(m.get("area")), "instituicao": limpar(m.get("instituicao"), 160),
                        "met": {c: int(x.get(k) or 0) for k, c in campos.items()}})

    res = {"gerado": data, "cvs": cvs or len(membros), "membros": membros}
    pos = {m["lattes"]: i for i, m in enumerate(membros)}
    chaves = {}
    if site_json and os.path.exists(site_json):
        chaves = json.load(open(site_json, encoding="utf-8")).get("chaves", {})
    citados = por_autores(chaves, pos)
    listas = {"membros": [m["nome"] for m in membros]}

    # Producao bibliografica, tecnica e artistica: mesmo formato.
    for nome, prefixo in (("biblio", "PB"), ("tecnica", "PT"), ("artistica", "PA")):
        tipos, itens, anos, vistos = [], [], {}, {}
        for cod, rot, d in paginas(pasta, prefixo):
            k = cod.lower()
            tipos.append({"k": k, "rot": rot, "n": 0})
            for x in d:
                a = ano(x)
                titulo = x.get("titulo")
                it = {"t": k, "a": a, "ti": limpar(titulo, 400), "au": limpar(x.get("autores"), 450),
                      "v": limpar(x.get("veiculo") or x.get("editora") or x.get("natureza"), 220),
                      "doi": limpar(x.get("doi")),
                      # membros: donos do curriculo onde o item aparece + membros citados entre os autores
                      "m": sorted(set(quem(secs, cod, titulo)) | citados(x.get("autores")))}
                # O scriptLattes so junta itens do mesmo ano: o mesmo trabalho com
                # ano diferente em dois curriculos (online x impresso) vira um so.
                ck = (k, chave(titulo)[:120])
                igual = next((o for o in vistos.get(ck, []) if abs(o["a"] - a) <= 1 or not (o["a"] and a)), None) if len(ck[1]) >= 15 else None
                if igual:
                    igual["m"] = sorted(set(igual["m"]) | set(it["m"]))
                    igual["a"] = max(igual["a"], a)
                    for c in ("doi", "v", "au"):
                        igual[c] = igual[c] or it[c]
                    continue
                vistos.setdefault(ck, []).append(it)
                itens.append(it)
        for it in itens:
            if it["a"]:
                mais(anos, str(it["a"]), it["t"])
        for t in tipos:
            t["n"] = sum(1 for it in itens if it["t"] == t["k"])
        tipos = [t for t in tipos if t["n"]]
        res[nome] = {"tipos": tipos, "anos": anos, "n": len(itens)}
        listas[nome] = sorted(itens, key=lambda i: -i["a"])
        listas[nome + "_tipos"] = {t["k"]: t["rot"] for t in tipos}

    # Orientacoes: so as paginas por nivel (as de total repetem os mesmos itens).
    itens, conta, anos = [], {}, {}
    for sit, pref in (("a", "OA"), ("c", "OC")):
        for cod, _rot, d in paginas(pasta, pref):
            t = ORIENTACAO.get(cod[2], "outra")
            for x in d:
                a = ano(x)
                mais(conta, t, sit)
                if sit == "c" and a:
                    mais(anos, str(a), t)
                itens.append({"s": sit, "t": t, "a": a, "n": limpar(x.get("orientado_a")), "ti": limpar(x.get("titulo_do_trabalho"), 300),
                              "c": curso(x.get("curso_instituicao")), "f": limpar(x.get("agencia_de_fomento"), 120),
                              "p": limpar(x.get("tipo_de_orientacao")), "m": quem(secs, cod, x.get("titulo_do_trabalho"), x.get("orientado_a"), todos=True)})
    res["orientacoes"] = {"conta": conta, "anos": anos, "n": len(itens)}
    listas["orientacoes"] = sorted(itens, key=lambda i: (-i["a"], i["n"]))

    # Projetos.
    itens, anos, andamento = [], {}, 0
    for x in ler(pasta, "Pj-0.html")[1]:
        desc = []
        for s in x.get("descricao") or []:
            s = limpar(re.sub(r"^\s*Descrição:\s*", "", str(s)), 600)
            if s and s not in desc:
                desc.append(s)
        fim = limpar(x.get("ano_conclusao"))
        fim = "" if fim.lower() == "atual" else fim
        ini = limpar(x.get("ano_inicio")) or str(ano(x) or "")
        andamento += fim == ""
        if ini.isdigit():
            mais(anos, ini, "s1")
        itens.append({"n": limpar(x.get("nome"), 300), "i": ini, "f": fim, "d": " ".join(desc[:1]),
                      "e": [[limpar(i.get("nome")), limpar(i.get("papel"))] for i in (x.get("integrantes") or []) if i.get("nome")][:20],
                      "m": quem(secs, "Pj0", x.get("nome"))})
    res["projetos"] = {"n": len(itens), "andamento": andamento, "anos": anos}
    listas["projetos"] = sorted(itens, key=lambda p: (p["f"] != "", -int(p["i"]) if p["i"].isdigit() else 0))

    # Eventos: participacao e organizacao.
    itens, anos, tipos = [], {}, {}
    for x in ler(pasta, "Ep-0.html")[1]:
        a, tp = ano(x), limpar(x.get("tipo_de_evento"))
        if a:
            mais(anos, str(a), "s1")
        mais(tipos, tp or "Outro")
        itens.append({"k": "p", "a": a, "ev": limpar(x.get("evento"), 220), "ti": limpar(x.get("apresentacao"), 300), "tp": tp,
                      "m": quem(secs, "Ep0", x.get("apresentacao"), x.get("evento"))})
    org = ler(pasta, "Eo-0.html")[1]
    for x in org:
        a = ano(x)
        if a:
            mais(anos, str(a), "s2")
        itens.append({"k": "o", "a": a, "ev": limpar(x.get("evento"), 220), "tp": limpar(x.get("natureza")), "au": limpar(x.get("autores"), 400),
                      "m": quem(secs, "Eo0", x.get("evento"))})
    res["eventos"] = {"part": len(itens) - len(org), "org": len(org), "tipos": tipos, "anos": anos}
    listas["eventos"] = sorted(itens, key=lambda e: -e["a"])

    # Grafo e parcerias: dois membros colaboram em cada item (producao
    # bibliografica ou tecnica, ja sem duplicatas) que tem os dois. Assim conta
    # tambem o trabalho que esta no Lattes de so um deles, como no site.
    pares = {}
    for letra, nome in (("b", "biblio"), ("t", "tecnica")):
        for n, it in enumerate(listas[nome]):
            ms = sorted(set(it["m"]))
            for x in range(len(ms)):
                for y in range(x + 1, len(ms)):
                    pares.setdefault("%d-%d" % (ms[x], ms[y]), []).append(letra + str(n))
    listas["pares"] = pares
    res["grafo"] = {"nos": [{"lattes": m["lattes"], "nome": m["nome"]} for m in membros],
                    "arestas": sorted(([int(a), int(b), len(v)] for a, b, v in ((k.split("-") + [v]) for k, v in pares.items())), key=lambda e: -e[2])}

    # ids dos premios (membros_ids) sao os nos do grafo do scriptLattes.
    _, g = ler(pasta, "grafoDeColaboracoes.html", "graphData")
    nos, idx = [], {}
    for n in (g or {}).get("nodes", []):
        m = re.search(r"(\d{16})", str(n.get("url", "")))
        idx[str(n.get("id"))] = len(nos)
        nos.append({"lattes": m.group(1) if m else ""})

    # Premios (poucos: vao no resumo). membros_ids sao os ids dos nos do grafo.
    res["premios"] = sorted(({"ano": ano(x), "desc": limpar(x.get("descricao"), 400).replace("., ", ", ").rstrip("."),
                              "lattes": [nos[idx[i]]["lattes"] for i in re.findall(r"\d+", str(x.get("membros_ids") or "")) if i in idx]}
                             for x in ler(pasta, "Pm-0.html")[1]), key=lambda x: -x["ano"])

    # Premios por membro, para a ficha de cada um.
    listas["premios"] = [{"a": p["ano"], "ti": p["desc"], "m": [pos[l] for l in p["lattes"] if l in pos]} for p in res["premios"]]

    os.makedirs(destino, exist_ok=True)
    for nome, dados in (("relatorio.json", res), ("listas.json", listas)):
        with open(os.path.join(destino, nome), "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))
    return res, listas


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    r, l = resumir(sys.argv[1], sys.argv[2])
    sem = {k: sum(1 for i in l[k] if not i["m"]) for k in ("biblio", "tecnica", "orientacoes", "projetos", "eventos")}
    print(f"{len(r['membros'])} membros; itens: " + ", ".join(f"{k} {len(l[k])}" for k in sem) + f"; sem membro: {sem} -> {sys.argv[2]}")
