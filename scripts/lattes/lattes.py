"""Relatorio do grupo com o scriptLattes (Mena-Chalco & Cesar-Jr., 2009).

Os curriculos sao baixados pelo proprio scriptLattes (baixaLattes.py: Chrome
headless via Selenium; o chromedriver vem do Selenium Manager):

  python lattes.py baixar     baixa de novo o CV de cada membro para cache/;
                              quem falhar fica com a copia anterior
  python lattes.py gerar      monta a lista a partir de dados.py, roda o
                              scriptLattes e copia o relatorio para
                              plugins/gemec-lattes/relatorio/
  python lattes.py faltam     lista quem ainda nao tem CV no cache
  python lattes.py enviar     manda ao site o resumo de cada pesquisador e as
                              publicacoes (extraidas por extrair.py) e sobe o
                              plugin gemec-lattes com o relatorio novo
  python lattes.py semanal    baixar + gerar + enviar (todos os membros)
  python lattes.py membro <id16>   baixa so o CV de um membro, gera e envia
                              (os outros entram com o CV que ja esta no cache);
                              com um ORCID, refaz o site com as obras dele no OpenAlex
  python lattes.py cv <id16>  so baixa um CV para o cache (nao mexe no site)

Membros sem Lattes e com ORCID no cadastro (pesquisadores estrangeiros) tem as
publicacoes trazidas do OpenAlex, como no Altimetro (estrangeiros.py).
  python lattes.py auto       o que a tarefa do Windows roda de hora em hora:
                              membro novo no site -> baixa so ele e envia;
                              semanal vencida (7 dias) -> semanal. Precisa de
                              GEMEC_SENHA

Se o Lattes bloquear o robo, da para salvar um CV a mao no navegador (Ctrl+S,
"Pagina da Web, somente HTML") em scripts/lattes/baixados/; "abrir" abre no
navegador os que faltam. O que estiver la entra no cache na proxima execucao.
"""
import datetime, glob, html, json, os, re, shutil, subprocess, sys, tempfile, time, webbrowser

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from dados import MEMBROS  # noqa: E402

SCRIPTLATTES = os.path.join(AQUI, "scriptLattes")
BAIXADOS = os.path.join(AQUI, "baixados")   # o que a pessoa salvou, nome livre
CACHE = os.path.join(AQUI, "cache")         # <id16> em UTF-8, como o scriptLattes espera
SAIDA = os.path.join(AQUI, "saida")         # saida bruta do scriptLattes
RELATORIO = os.path.join(AQUI, "..", "..", "plugins", "gemec-lattes", "relatorio")
MARCA_SEMANAL = os.path.join(AQUI, "ultima_semanal.txt")  # quando rodou a atualizacao completa
SITE_JSON = os.path.join(AQUI, "site.json") # resumos e publicacoes para o site
LOTE = 150                                  # publicacoes por requisicao ao site

# categoria do membro -> rotulo no relatorio (egressos ficam de fora)
ROTULOS = {
    "professor": "Professores", "visitante": "Pesquisadores visitantes", "posdoc": "Pós-doutorado",
    "doutorado": "Doutorandos", "mestrado": "Mestrandos", "graduacao": "Graduandos", "egresso": "Egressos",
}
ORDEM = list(ROTULOS)
# Arquivos da saida que nao vao para o site: dados intermediarios e os JSON
# individuais (trazem sexo e endereco; o relatorio em si nao precisa deles).
NAO_PUBLICAR = ("json", "*.txt", "*.csv", "*.gdf", "*.graphml", "*.gexf", "*.xml", "*.config", "*.list")


_MEMBROS = None
_OCULTOS = set()  # ids Lattes dos membros ocultos (preenchido por todos())
_CADASTROS = []   # (nome, categoria, lattes, orcid) de cada membro lido do site
ORCID_RE = r"\d{4}-\d{4}-\d{4}-\d{3}[\dXx]"
MODO = "Envio ao site"  # nome do envio no historico do app (semanal/auto trocam)


def todos_do_site():
    """[(nome, categoria, url_lattes)] dos membros publicados no site (API publica).
    O site e quem manda: quem foi cadastrado ou mudou de categoria la entra aqui
    sem mexer em dados.py, que fica so de reserva se o site nao responder."""
    import requests
    s = requests.Session()
    s.verify = os.path.join(os.path.dirname(AQUI), "bundle.pem")
    out, pag = [], 1
    while True:
        r = s.get("https://gemec.unifei.edu.br/?rest_route=/wp/v2/gemec_membro",
                  params={"per_page": 100, "page": pag, "_fields": "title,meta"}, timeout=60)
        r.raise_for_status()
        for m in r.json():
            meta = m.get("meta") or {}
            out.append((html.unescape(m["title"]["rendered"]), meta.get("gemec_categoria", ""), meta.get("gemec_lattes", "")))
            _CADASTROS.append(out[-1] + (meta.get("gemec_orcid", ""),))
        if pag >= int(r.headers.get("X-WP-TotalPages", 1)):
            break
        pag += 1
    return out + ocultos_do_site()


def ocultos_do_site():
    """Membros ocultos (post Privado no site): o CV deles e baixado e as
    publicacoes vao ao site (ligadas a eles), mas ficam fora do relatorio do
    scriptLattes e das estatisticas. A API so os mostra com login (GEMEC_SENHA)."""
    if not os.environ.get("GEMEC_SENHA"):
        return []
    import gm
    try:
        gm.login()
        out, pag = [], 1
        while True:
            r = gm.rest(f"/wp/v2/gemec_membro?status=private&context=edit&per_page=100&page={pag}&_fields=title,meta")
            r.raise_for_status()
            for m in r.json():
                meta = m.get("meta") or {}
                out.append((m["title"]["raw"], meta.get("gemec_categoria", ""), meta.get("gemec_lattes", "")))
                _CADASTROS.append(out[-1] + (meta.get("gemec_orcid", ""),))
                _OCULTOS.update(re.findall(r"\d{16}", meta.get("gemec_lattes", "")))
            if pag >= int(r.headers.get("X-WP-TotalPages", 1)):
                return out
            pag += 1
    except Exception as e:  # noqa: BLE001
        print("  aviso: nao deu para ler os membros ocultos do site (" + type(e).__name__ + "); ficam de fora")
        return []


def todos():
    global _MEMBROS
    if _MEMBROS is None:
        try:
            _MEMBROS = todos_do_site()
        except Exception as e:  # noqa: BLE001
            print("  site indisponivel (" + type(e).__name__ + "); usando dados.py")
            _MEMBROS = [(n, c, x.get("lattes", "")) for n, c, _f, x in MEMBROS]
            for _n, _c, _f, x in MEMBROS:
                if x.get("oculto"):
                    _OCULTOS.update(re.findall(r"\d{16}", x.get("lattes", "")))
    return _MEMBROS


def ocultos():
    todos()
    return _OCULTOS


def membros():
    """[(id16, nome, rotulo)] dos membros com Lattes, por categoria (egressos no fim)."""
    out, vistos = [], set()
    for nome, cat, url in sorted(todos(), key=lambda t: ORDEM.index(t[1]) if t[1] in ORDEM else 99):
        m = re.search(r"(\d{16})", url or "")
        if m and cat in ROTULOS and m.group(1) not in vistos:
            vistos.add(m.group(1))
            out.append((m.group(1), nome, ROTULOS[cat]))
    return out


def estrangeiros():
    """{ORCID: nome} dos membros sem Lattes e com ORCID no cadastro."""
    todos()
    out = {}
    for nome, cat, url, orcid in _CADASTROS:
        o = re.search(ORCID_RE, orcid or "")
        if cat in ROTULOS and o and not re.search(r"\d{16}", url or ""):
            out[o.group().upper()] = nome
    return out


def orcids_membros():
    """{ORCID: chave do membro} de quem tem ORCID: o id16 se tiver Lattes."""
    todos()
    out = {}
    for _n, cat, url, orcid in _CADASTROS:
        o = re.search(ORCID_RE, orcid or "")
        if o and cat in ROTULOS:
            lid = re.search(r"\d{16}", url or "")
            out[o.group().upper()] = lid.group() if lid else "orcid:" + o.group().upper()
    return out


def ler_texto(caminho):
    dados = open(caminho, "rb").read()
    for cod in ("utf-8", "cp1252"):
        try:
            return dados.decode(cod)
        except UnicodeDecodeError:
            pass
    return dados.decode("latin-1")


def id_do_cv(html, nome_arquivo, conhecidos):
    """O CV traz 'Endereco para acessar este CV: http://lattes.cnpq.br/<id16>'."""
    m = re.search(r"acessar este CV:?\s*(?:<[^>]+>\s*)*\s*https?://lattes\.cnpq\.br/(\d{16})", html)
    if m:
        return m.group(1)
    achados = [i for i in re.findall(r"lattes\.cnpq\.br/(\d{16})", html) if i in conhecidos]
    if len(set(achados)) == 1:
        return achados[0]
    m = re.search(r"(\d{16})", nome_arquivo)
    return m.group(1) if m else None


def normalizar():
    os.makedirs(BAIXADOS, exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)
    conhecidos = {i for i, _, _ in membros()}
    for caminho in sorted(glob.glob(os.path.join(BAIXADOS, "*"))):
        if os.path.isdir(caminho):
            continue  # pasta "_arquivos" que o navegador cria ao salvar a pagina completa
        html = ler_texto(caminho)
        if "Curr" not in html or "lattes.cnpq.br" not in html:
            print("  ignorado (nao parece um CV Lattes):", os.path.basename(caminho))
            continue
        if "captcha" in html.lower() and "Endere" not in html:
            print("  ignorado (pagina do captcha, nao o CV):", os.path.basename(caminho))
            continue
        lid = id_do_cv(html, os.path.basename(caminho), conhecidos)
        if not lid:
            print("  ignorado (sem ID Lattes de 16 digitos):", os.path.basename(caminho))
            continue
        if lid not in conhecidos:
            print("  aviso: CV de", lid, "nao e de nenhum membro em dados.py; fica de fora")
        with open(os.path.join(CACHE, lid), "w", encoding="utf-8") as f:
            f.write(html)


def valido(html, lid):
    return "Curr" in html and id_do_cv(html, "", {lid}) == lid


def baixar_cv(lid, raiz_tmp=None):
    """Baixa um CV para o cache; excecao se nao vier o CV (fica a copia anterior)."""
    sys.path.insert(0, SCRIPTLATTES)
    from scriptLattes.baixaLattes import baixaCVLattes
    raiz_tmp = raiz_tmp or os.path.join(AQUI, "_baixando")
    os.makedirs(raiz_tmp, exist_ok=True)
    tmp = tempfile.mkdtemp(dir=raiz_tmp)
    baixaCVLattes(lid, tmp)
    html = ler_texto(os.path.join(tmp, lid))
    if not valido(html, lid):
        raise ValueError("pagina baixada nao e o CV")
    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, lid), "w", encoding="utf-8") as f:
        f.write(html)
    shutil.rmtree(tmp, ignore_errors=True)


def cmd_cv(lid):
    m = re.search(r"\d{16}", lid or "")
    if not m:
        raise SystemExit("Informe o link ou o id de 16 digitos do Lattes.")
    print("baixando o CV", m.group())
    baixar_cv(m.group())
    print("CV salvo em", os.path.join(CACHE, m.group()))


def cmd_baixar(so_faltam=None, lista=None):
    """Baixa cada CV com o baixaLattes do scriptLattes, numa pasta temporaria:
    o baixaCVLattes pula o que ja existe no destino e desiste com excecao.
    lista: [(id16, nome, rotulo)] para baixar so esses."""
    normalizar()
    if so_faltam is None:
        so_faltam = "--faltam" in sys.argv
    if lista is None:
        lista = [(i, n, None) for i, n in faltam()] if so_faltam else membros()
    # Uma subpasta nova por CV dentro de _baixando/: no OneDrive ou no Google
    # Drive a sincronizacao trava os arquivos, e apagar e recriar a mesma pasta
    # entre um CV e outro falhava. O que nao der para apagar no fim fica la.
    raiz_tmp = os.path.join(AQUI, "_baixando")
    os.makedirs(raiz_tmp, exist_ok=True)
    ok, falhas = 0, []
    for k, (lid, nome, _r) in enumerate(lista, 1):
        print(f"[{k}/{len(lista)}] {nome}")
        try:
            baixar_cv(lid, raiz_tmp)
        except Exception as e:  # noqa: BLE001 - um CV com problema nao para os outros
            falhas.append(nome)
            print("  falhou:", str(e).splitlines()[0] if str(e) else type(e).__name__,
                  "(fica a copia anterior)" if os.path.exists(os.path.join(CACHE, lid)) else "")
            continue
        ok += 1
    shutil.rmtree(raiz_tmp, ignore_errors=True)
    print(f"\n{ok} de {len(lista)} curriculos baixados." + (" Falharam: " + ", ".join(falhas) if falhas else ""))


def faltam():
    return [(i, n) for i, n, _ in membros() if not os.path.exists(os.path.join(CACHE, i))]


def cmd_abrir():
    normalizar()
    lista = [(i, n) for i, n, _ in membros()] if "--todos" in sys.argv else faltam()
    if not lista:
        print("Todos os membros ja tem CV salvo em cache/.")
        return
    print(f"Salve cada curriculo em {BAIXADOS}\n(Ctrl+S, tipo 'Pagina da Web, somente HTML'; o nome do arquivo tanto faz)\n")
    for i, nome in lista:
        print(" ", nome, "->", "http://lattes.cnpq.br/" + i)
        webbrowser.open("http://lattes.cnpq.br/" + i)
        time.sleep(1.5)


def cmd_faltam():
    normalizar()
    lista = faltam()
    print(f"{len(membros()) - len(lista)} de {len(membros())} CVs salvos.")
    for i, nome in lista:
        print("  falta:", nome, "http://lattes.cnpq.br/" + i)


def cmd_gerar():
    normalizar()
    todos_cvs = [(i, n, r) for i, n, r in membros() if os.path.exists(os.path.join(CACHE, i))]
    # Membros ocultos ficam fora do relatorio (e das estatisticas); so as
    # publicacoes e o resumo deles vao ao site (extracao com a lista completa).
    presentes = [p for p in todos_cvs if p[0] not in ocultos()]
    if not presentes:
        raise SystemExit(f"Nenhum CV em {CACHE}. Rode antes 'python lattes.py baixar'.")
    for i, n in faltam():
        print("  sem CV (fica fora do relatorio):", n)

    # So entram na lista os CVs que ja estao no cache (o download e feito antes,
    # por 'baixar'): uma falha de rede nao derruba o scriptLattes no meio.
    lista = os.path.join(AQUI, "gemec.list")
    with open(lista, "w", encoding="utf-8") as f:
        for i, n, r in presentes:
            f.write(f"{i} , {n} , , {r}\n")
    termos = os.path.join(AQUI, "termos.txt")
    open(termos, "a").close()

    if os.path.isdir(SAIDA):
        shutil.rmtree(SAIDA)
    def escrever_config(nome, lista, saida):
        caminho = os.path.join(AQUI, nome)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(open(os.path.join(AQUI, "gemec.config.modelo"), encoding="utf-8").read()
                    .replace("{LISTA}", lista).replace("{SAIDA}", saida + os.sep)
                    .replace("{CACHE}", CACHE + os.sep).replace("{TERMOS}", termos)
                    .replace("{ANO}", str(datetime.date.today().year)))
        return caminho
    config = escrever_config("gemec.config", lista, SAIDA)
    config_site = config
    if len(todos_cvs) > len(presentes):
        lista_site = os.path.join(AQUI, "gemec-site.list")
        with open(lista_site, "w", encoding="utf-8") as f:
            for i, n, r in todos_cvs:
                f.write(f"{i} , {n} , , {r}\n")
        config_site = escrever_config("gemec-site.config", lista_site, os.path.join(AQUI, "_saida_site"))
        print("  ocultos (so publicacoes e resumo no site):", ", ".join(n for i, n, _r in todos_cvs if i in ocultos()))

    # PYTHONUTF8: o scriptLattes imprime setas e simbolos que o console do Windows (cp1252) nao aceita
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTLATTES, "scriptLattes.py"), config], cwd=SCRIPTLATTES, env=env)
    if r.returncode != 0 or not os.path.exists(os.path.join(SAIDA, "index.html")):
        raise SystemExit("O scriptLattes falhou (veja a saida acima).")

    # Nomes de todos os membros (egressos inclusive): reconhecem coautores do
    # grupo nas publicacoes mesmo sem o CV deles.
    arq_nomes = os.path.join(AQUI, "nomes.json")
    with open(arq_nomes, "w", encoding="utf-8") as f:
        json.dump({m.group(1): nome for nome, _c, url in todos()
                   for m in [re.search(r"(\d{16})", url or "")] if m}, f, ensure_ascii=False)
    r = subprocess.run([sys.executable, os.path.join(AQUI, "extrair.py"), config_site, SITE_JSON, arq_nomes], cwd=SCRIPTLATTES, env=env)
    if r.returncode != 0:
        raise SystemExit("A extracao para o site falhou (veja a saida acima).")
    shutil.rmtree(os.path.join(AQUI, "_saida_site"), ignore_errors=True)
    # Marca os ocultos no site.json (o app mostra; o envio nao os conta como CV do relatorio).
    site = json.load(open(SITE_JSON, encoding="utf-8"))
    site["ocultos"] = sorted(i for i in site.get("membros", {}) if i in ocultos())
    # Formacao academica e areas de atuacao de cada CV, para o perfil no site.
    import perfis
    for lid, m in site.get("membros", {}).items():
        if os.path.exists(os.path.join(CACHE, lid)):
            m["formacao"] = perfis.formacao_lattes(lid)
            m["areas"] = perfis.areas_lattes(lid)
    # Membros sem Lattes (estrangeiros): publicacoes do OpenAlex pelo ORCID.
    est = estrangeiros()
    if est:
        from estrangeiros import juntar
        r = juntar(site, est, orcids_membros())
        print(f"  OpenAlex ({len(est)} sem Lattes): {r['novas']} publicacoes novas, {r['ja_no_lattes']} ja estavam no Lattes")
    with open(SITE_JSON, "w", encoding="utf-8") as f:
        json.dump(site, f, ensure_ascii=False)

    if os.path.isdir(RELATORIO):
        shutil.rmtree(RELATORIO)
    shutil.copytree(SAIDA, RELATORIO, ignore=shutil.ignore_patterns(*NAO_PUBLICAR))
    with open(os.path.join(RELATORIO, "..", "relatorio.txt"), "w", encoding="utf-8") as f:
        f.write(f"{datetime.date.today():%d/%m/%Y}\n{len(presentes)}\n")
    # Resumo do relatorio para a pagina Estatisticas (vai junto com o plugin).
    from relatorio_json import resumir
    resumir(RELATORIO, os.path.join(RELATORIO, ".."), f"{datetime.date.today():%d/%m/%Y}", len(presentes), SITE_JSON)
    print(f"\nRelatorio com {len(presentes)} curriculos copiado para {os.path.normpath(RELATORIO)}")
    print("Para mandar ao site: python lattes.py enviar")


def cmd_enviar():
    import gm
    from publicar import zipar
    dados = json.load(open(SITE_JSON, encoding="utf-8"))
    cvs = {i: datetime.date.fromtimestamp(os.path.getmtime(os.path.join(CACHE, i))).isoformat()
           for i in dados["membros"] if os.path.exists(os.path.join(CACHE, i))}
    for i, m in dados["membros"].items():
        m["salvo"] = cvs.get(i, "")
    gm.login()
    r = gm.ok(gm.rest("/gemec/v1/lattes/membros", "POST", json={"membros": dados["membros"]}))
    print("resumos:", r["atualizados"], "atualizados;", "sem cadastro no site:", ", ".join(r["sem_cadastro"]) or "nenhum")

    # Publicacoes refeitas do zero: o lote novo entra como rascunho e so no fim
    # (concluir) e publicado e o resto do Lattes apagado. Se cair no meio, o
    # site fica com a versao anterior e o lote incompleto sai no proximo envio.
    lote = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    apagadas = 0
    while True:
        r = gm.ok(gm.rest("/gemec/v1/lattes/limpar", "POST", json={"lote": lote}))
        apagadas += r["apagadas"]
        if not r["faltam"]:
            break
    if apagadas:
        print("lotes incompletos apagados:", apagadas)
    pubs = dados["publicacoes"]
    criadas = 0
    for n in range(0, len(pubs), LOTE):
        criadas += gm.ok(gm.rest("/gemec/v1/lattes/publicacoes", "POST", json={"lote": lote, "itens": pubs[n:n + LOTE]}))["criadas"]
        print(f"  publicacoes {min(n + LOTE, len(pubs))}/{len(pubs)}")
    publicadas = apagadas = 0
    while True:
        r = gm.ok(gm.rest("/gemec/v1/lattes/concluir", "POST", json={"lote": lote, "cvs": len(set(dados["membros"]) - set(dados.get("ocultos", [])))}))
        publicadas += r["publicadas"]
        apagadas += r["apagadas"]
        if not r["faltam"]:
            break
    print(f"publicacoes: {criadas} criadas do zero, {publicadas} publicadas, {apagadas} antigas apagadas; no site: {r['total']}")

    ok, msg = gm.enviar_zip("plugin", zipar(os.path.join(AQUI, "..", "..", "plugins", "gemec-lattes"), "gemec-lattes"))
    # Confere no proprio site: o relatorio.txt publicado tem que ser o que acabou de ser gerado.
    local = open(os.path.join(RELATORIO, "..", "relatorio.txt"), encoding="utf-8").read().split()
    try:
        no_site = gm.s.get(gm.BASE + "/wp-content/plugins/gemec-lattes/relatorio.txt",
                           params={"v": lote}, timeout=60).text.split()
    except Exception as e:  # noqa: BLE001
        no_site = "(nao deu para ler: " + type(e).__name__ + ")"
    if ok and no_site == local:
        print("relatorio (plugin gemec-lattes): enviado e conferido no site")
    elif no_site == local:
        print("relatorio (plugin gemec-lattes): o WordPress nao confirmou o envio, mas o site ja mostra o relatorio de hoje")
        print("  resposta do WordPress:", msg)
    else:
        print("relatorio (plugin gemec-lattes): FALHOU - o site esta com", repr(no_site), "e o gerado e", repr(local))
        if msg:
            print("  resposta do WordPress:", msg)
    # Historico para o app: o que mudou desde o envio anterior.
    try:
        import historico
        e = historico.registrar(MODO)
        print("historico:", historico.resumo(e))
    except Exception as e:  # noqa: BLE001 (o envio ja deu certo; o historico e extra)
        print("historico nao registrado:", e)


def cmd_semanal():
    global MODO
    MODO = "Atualização completa"
    print(f"== {datetime.datetime.now():%d/%m/%Y %H:%M}")
    cmd_baixar()
    cmd_gerar()
    cmd_enviar()
    velhos = [n for i, n, _ in membros() if os.path.exists(os.path.join(CACHE, i))
              and time.time() - os.path.getmtime(os.path.join(CACHE, i)) > 30 * 86400]
    if velhos:
        print("CVs que nao baixam ha mais de 30 dias (veja o link do Lattes no cadastro do membro):", ", ".join(velhos))
    with open(MARCA_SEMANAL, "w") as f:
        f.write(datetime.datetime.now().isoformat())


def cmd_membro(lid):
    """Baixa so o CV de um membro e refaz o site. O relatorio e as publicacoes
    sao sempre do grupo todo: os outros membros entram com o CV do cache."""
    global MODO
    m = re.search(r"\d{16}", lid or "")
    alvo = [x for x in membros() if m and x[0] == m.group()]
    o = re.search(ORCID_RE, lid or "")
    if not alvo and o and o.group().upper() in estrangeiros():
        nome = estrangeiros()[o.group().upper()]
        MODO = "Um membro: " + nome
        print(f"== {datetime.datetime.now():%d/%m/%Y %H:%M} so {nome} (sem Lattes: obras do OpenAlex)")
        cmd_gerar()
        cmd_enviar()
        return None
    if not alvo:
        raise SystemExit(f"'{lid}' nao e o Lattes de nenhum membro do site (confira o link e a categoria no cadastro).")
    lid, nome = alvo[0][0], alvo[0][1]
    MODO = "Um membro: " + nome
    print(f"== {datetime.datetime.now():%d/%m/%Y %H:%M} so {nome}")
    cam = os.path.join(CACHE, lid)
    antes = os.path.getmtime(cam) if os.path.exists(cam) else None
    cmd_baixar(lista=alvo)
    if not os.path.exists(cam) or os.path.getmtime(cam) == antes:
        raise SystemExit(f"O CV de {nome} nao baixou; o site nao foi mexido.")
    cmd_gerar()
    cmd_enviar()
    return lid


def cmd_auto():
    """O que a tarefa do Windows roda de hora em hora. Quase sempre termina na
    hora (uma consulta ao site); trabalha quando ha membro novo com Lattes no
    cadastro ou quando a atualizacao completa da semana venceu."""
    ultima = os.path.getmtime(MARCA_SEMANAL) if os.path.exists(MARCA_SEMANAL) else 0
    if time.time() - ultima >= 7 * 86400:
        cmd_semanal()
        return
    novos = faltam()
    if not novos:
        return
    global MODO
    MODO = "Membros novos"
    print(f"== {datetime.datetime.now():%d/%m/%Y %H:%M} membros novos:", ", ".join(n for _i, n in novos))
    cmd_baixar(so_faltam=True)
    if len(faltam()) == len(novos):
        print("Nenhum CV novo baixou; tenta de novo na proxima hora.")
        return
    cmd_gerar()
    cmd_enviar()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"baixar": cmd_baixar, "abrir": cmd_abrir, "gerar": cmd_gerar, "faltam": cmd_faltam, "enviar": cmd_enviar,
     "semanal": cmd_semanal, "auto": cmd_auto,
     "membro": lambda: cmd_membro(sys.argv[2] if len(sys.argv) > 2 else ""),
     "cv": lambda: cmd_cv(sys.argv[2] if len(sys.argv) > 2 else "")}.get(cmd, lambda: print(__doc__))()
