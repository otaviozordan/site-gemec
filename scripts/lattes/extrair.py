"""Le os CVs com o proprio parser do scriptLattes e grava o que o site usa:
resumo de cada pesquisador e publicacoes do grupo, sem duplicatas.

Chamado por lattes.py (python extrair.py <config> <saida.json> [nomes.json]) com o
scriptLattes no sys.path. O JSON individual que o scriptLattes grava perde o
DOI dos congressos e o titulo do livro dos capitulos; por isso le-se os objetos.
"""
import contextlib, io, json, os, re, sys, unicodedata

from rapidfuzz import fuzz

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "scriptLattes"))
from scriptLattes.grupo import Grupo  # noqa: E402

PARTICULAS = {"de", "da", "do", "dos", "das", "e", "del", "van", "von"}
SUFIXOS = {"junior", "jr", "neto", "filho", "sobrinho"}

# lista do scriptLattes -> (tipo no site, atributo do veiculo)
LISTAS = (
    ("listaArtigoEmPeriodico", "periodico", "revista"),
    ("listaTrabalhoCompletoEmCongresso", "congresso", "nomeDoEvento"),
    ("listaResumoExpandidoEmCongresso", "congresso", "nomeDoEvento"),
    ("listaCapituloDeLivroPublicado", "livro", "livro"),
    ("listaLivroPublicado", "livro", "editora"),
)


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))


def chave_nome(nome):
    """'GOMES, G. F.', 'Gomes, Guilherme Ferreira' e 'Guilherme Ferreira Gomes' -> 'gomes,gf'."""
    t = sem_acento(nome).lower().strip(" .;")
    if "," in t:
        fam, dado = t.split(",", 1)
    else:
        partes = re.split(r"[\s.]+", t)
        partes = [p for p in partes if p]
        while len(partes) > 1 and partes[-1] in SUFIXOS:
            partes.pop()
        if len(partes) < 2:
            return ""
        fam, dado = partes[-1], " ".join(partes[:-1])
    fam = [p for p in re.split(r"[^a-z]+", fam) if p and p not in PARTICULAS and p not in SUFIXOS]
    ini = [p[0] for p in re.split(r"[^a-z]+", dado) if p and p not in PARTICULAS]
    if not fam or not ini:
        return ""
    return "".join(fam) + "," + "".join(ini)


def titulo_norm(t):
    return re.sub(r"[^a-z0-9]+", "", sem_acento(t).lower())


def limpar(s):
    return re.sub(r"\s+", " ", str(s or "")).strip(" .,;")


def doi_de(s):
    m = re.search(r"10\.\d{4,9}/\S+", str(s or ""))
    return m.group(0).rstrip(".,;").lower() if m else ""


def main(config, destino, arquivo_nomes=None):
    with contextlib.redirect_stdout(io.StringIO()):  # o parser fala muito
        g = Grupo(config)
        g.carregarDadosCVLattes()

    # Chaves de nome de cada membro: o nome do cadastro (vale tambem para quem
    # nao tem CV processado, como os egressos) e as formas de citacao do CV.
    nomes = {}
    if arquivo_nomes:
        for lid, nome in json.load(open(arquivo_nomes, encoding="utf-8")).items():
            k = chave_nome(nome)
            if k:
                nomes.setdefault(k, set()).add(lid)
    membros = {}
    for m in g.listaDeMembros:
        formas = [m.nomeCompleto] + str(m.nomeEmCitacoesBibliograficas or "").split(";")
        for f in formas:
            k = chave_nome(f)
            if k:
                nomes.setdefault(k, set()).add(m.idLattes)
        membros[m.idLattes] = {
            "nome": m.nomeCompleto,
            "resumo": limpar(m.textoResumo),
            "atualizado": limpar(m.atualizacaoCV),
        }

    pubs = []  # cada uma: dict com 'tn' (titulo normalizado) para casar duplicatas
    por_doi, por_tn = {}, {}
    for m in g.listaDeMembros:
        for lista, tipo, attr_veiculo in LISTAS:
            for it in getattr(m, lista, []):
                titulo = limpar(getattr(it, "titulo", ""))
                if len(titulo) < 5:
                    continue
                ano = str(getattr(it, "ano", "") or "")
                ano = ano if re.fullmatch(r"\d{4}", ano) else ""
                doi = doi_de(getattr(it, "doi", ""))
                autores, dono_achado, quem = [], False, {m.idLattes}
                for a in re.split(r"\s*;\s*", str(getattr(it, "autores", "") or "")):
                    a = limpar(a)
                    if not a:
                        continue
                    ids = nomes.get(chave_nome(a), set())
                    quem |= ids
                    autores.append({"nome": a, "membro": bool(ids)})
                tn = titulo_norm(titulo)
                item = {"titulo": titulo, "tipo": tipo, "ano": ano, "doi": doi, "autores": autores,
                        "veiculo": limpar(getattr(it, attr_veiculo, "")), "lattes": quem, "tn": tn}

                # Mesmo trabalho no CV de outro membro: por DOI, titulo igual ou quase igual.
                igual = por_doi.get(doi) if doi else None
                if igual is None:
                    igual = por_tn.get(tn)
                if igual is None and len(tn) >= 25:
                    for outro in pubs:
                        if abs(int(outro["ano"] or 0) - int(ano or 0)) <= 1 and fuzz.ratio(tn[:200], outro["tn"][:200]) >= 92:
                            igual = outro
                            break
                if igual is not None:
                    igual["lattes"] |= quem
                    for c in ("doi", "veiculo", "ano"):
                        if not igual[c] and item[c]:
                            igual[c] = item[c]
                    # Quem tem mais autores marcados como membro fica com a lista
                    if sum(x["membro"] for x in autores) > sum(x["membro"] for x in igual["autores"]):
                        igual["autores"] = autores
                    if igual["doi"]:
                        por_doi[igual["doi"]] = igual
                    continue
                pubs.append(item)
                if doi:
                    por_doi[doi] = item
                por_tn[tn] = item

    saida = []
    for p in pubs:
        saida.append({
            "chave": ("doi:" + p["doi"]) if p["doi"] else ("t:" + p["tn"][:150] + ":" + p["ano"]),
            "titulo": p["titulo"], "tipo": p["tipo"], "ano": p["ano"], "doi": p["doi"],
            "veiculo": p["veiculo"], "autores": p["autores"], "lattes": sorted(p["lattes"]),
        })
    with open(destino, "w", encoding="utf-8") as f:
        # chaves: nome de citacao -> membros; relatorio_json.py usa a mesma regra
        # para atribuir aos membros os itens das estatisticas (coautorias).
        json.dump({"membros": membros, "publicacoes": saida, "chaves": {k: sorted(v) for k, v in nomes.items()}},
                  f, ensure_ascii=False, indent=1)
    print(f"{len(membros)} curriculos, {len(saida)} publicacoes -> {destino}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(*sys.argv[1:4])
