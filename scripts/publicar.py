"""Publica o novo site do GEMEC em etapas.
Uso: GEMEC_SENHA=... python publicar.py etapa [etapa...]
Etapas: zips plugins tema conteudo paginas config ativar-tema desativar impacto"""
import os, re, sys, zipfile
import gm
from dados import MEMBROS, LINHAS, PARCEIROS, LABS, ORCID, TITULACAO, VAGAS, TEMAS
import paginas as P

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIST = os.path.join(RAIZ, "dist")

def zipar(origem, nome):
    os.makedirs(DIST, exist_ok=True)
    destino = os.path.join(DIST, nome + ".zip")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for raiz, _, arqs in os.walk(origem):
            for a in arqs:
                cam = os.path.join(raiz, a)
                z.write(cam, os.path.join(nome, os.path.relpath(cam, origem)))
    return destino

def etapa_zips():
    for nome in ("gemec-core", "gemec-seguranca", "gemec-parceiros", "gemec-lattes", "gemec-ranking"):
        print(zipar(os.path.join(RAIZ, "plugins", nome), nome))
    print(zipar(os.path.join(RAIZ, "tema", "gemec"), "gemec"))

def etapa_plugins():
    # gemec-core antes de gemec-parceiros: as funcoes de parceiros sairam do core
    # e foram para o plugin novo; ao contrario, os dois as declarariam ao mesmo tempo.
    for nome in ("gemec-core", "gemec-seguranca", "gemec-parceiros", "gemec-lattes", "gemec-ranking"):
        ok, msg = gm.enviar_zip("plugin", os.path.join(DIST, nome + ".zip"))
        print(nome, "enviado" if ok else "FALHOU: " + msg)
        r = gm.rest(f"/wp/v2/plugins/{nome}/{nome}", "POST", json={"status": "active"})
        print("  ativar:", r.status_code, r.json().get("status") if r.ok else r.text[:400])

def etapa_tema():
    ok, msg = gm.enviar_zip("theme", os.path.join(DIST, "gemec.zip"))
    print("tema", "enviado" if ok else "FALHOU: " + msg)

def existentes(tipo):
    r = gm.ok(gm.rest(f"/wp/v2/{tipo}?per_page=100&status=any&context=edit"))
    return {x["title"]["raw"]: x["id"] for x in r}

def salvar(tipo, titulo, corpo, ids):
    if titulo in ids:
        return gm.ok(gm.rest(f"/wp/v2/{tipo}/{ids[titulo]}", "POST", json=corpo))["id"], "atualizado"
    return gm.ok(gm.rest(f"/wp/v2/{tipo}", "POST", json=corpo))["id"], "criado"

def etapa_conteudo():
    ids = existentes("gemec_membro")
    for i, (nome, cat, foto, extra) in enumerate(MEMBROS):
        meta = {"gemec_categoria": cat}
        meta.update({"gemec_" + k: v for k, v in extra.items()})
        if nome in TEMAS and "temas" not in extra:
            meta["gemec_temas"] = TEMAS[nome]
        if nome in TITULACAO:
            meta["gemec_titulacao"] = TITULACAO[nome]
        if nome in ORCID:
            meta["gemec_orcid"] = ORCID[nome]
        corpo = {"title": nome, "status": "publish", "menu_order": (i + 1) * 10, "meta": meta, "featured_media": foto or 0}
        print("membro", *salvar("gemec_membro", nome, corpo, ids), nome)
    ids = existentes("gemec_linha")
    for i, (titulo, icone, resumo, topicos) in enumerate(LINHAS):
        corpo = {"title": titulo, "status": "publish", "menu_order": (i + 1) * 10,
                 "meta": {"gemec_icone": icone, "gemec_resumo": resumo, "gemec_topicos": "\n".join(topicos)}}
        print("linha", *salvar("gemec_linha", titulo, corpo, ids), titulo)
    ids = existentes("gemec_vaga")
    for i, (titulo, tipo, resumo, link) in enumerate(VAGAS):
        corpo = {"title": titulo, "status": "publish", "menu_order": (i + 1) * 10,
                 "meta": {"gemec_tipo": tipo, "gemec_resumo": resumo, "gemec_link": link}}
        if titulo in ids:
            continue  # ja existe: quem manda agora e o painel
        print("oportunidade", *salvar("gemec_vaga", titulo, corpo, ids), titulo)
    ids = existentes("gemec_parceiro")
    for i, (nome, sigla, logo, url, desc) in enumerate(LABS):
        corpo = {"title": nome, "status": "publish", "menu_order": i + 1, "featured_media": logo or 0,
                 "meta": {"gemec_grupo": "laboratorio", "gemec_sigla": sigla, "gemec_url": url or "", "gemec_descricao": desc}}
        print("laboratorio", *salvar("gemec_parceiro", nome, corpo, ids), nome)
    for i, (nome, grupo, logo, url) in enumerate(PARCEIROS):
        corpo = {"title": nome, "status": "publish", "menu_order": (i + 1) * 10, "featured_media": logo,
                 "meta": {"gemec_grupo": grupo, "gemec_url": url or ""}}
        print("parceiro", *salvar("gemec_parceiro", nome, corpo, ids), nome)

def etapa_paginas():
    foto = gm.ok(gm.rest("/wp/v2/media/318"))
    url_foto = foto["media_details"]["sizes"].get("large", {}).get("source_url", foto["source_url"])
    lista = [
        # id, titulo, ordem, resumo, conteudo, imagem destacada
        (44, "Início", 1, "Pesquisa em mecânica estrutural, vibrações, monitoramento da integridade estrutural, compósitos, otimização e inteligência artificial aplicada, no Instituto de Engenharia Mecânica da UNIFEI.", P.INICIO, 334),
        (259, "Pesquisa", 2, "Sete linhas que combinam teoria, experimento e simulação numérica.", P.PESQUISA, None),
        (11, "Membros", 3, "Professores, pesquisadores e estudantes que fazem o GEMEC.", P.MEMBROS, None),
        ("publicacoes", "Publicações", 4, "Artigos, trabalhos em congressos e capítulos dos membros do GEMEC, atualizados automaticamente.", P.PUBLICACOES, None),
        ("impacto", "Impacto científico", 6, "Dois pesquisadores do GEMEC estão na edição 2026 da lista Stanford/Elsevier, que reúne os cientistas de maior impacto de citações em cada área.", P.IMPACTO, None),
        (17, "Parceiros", 5, "Laboratórios parceiros, agências de fomento, empresas e fornecedores de tecnologia que apoiam as pesquisas do grupo.", P.PARCEIROS, None),
        (412, "Oportunidades", 6, "Editais abertos para pós-doutorado, mestrado e iniciação científica.", P.OPORTUNIDADES, None),
        (293, "Arquivos", 7, "Modelos e documentos de uso do grupo.", P.ARQUIVOS, None),
        ("relatorio-lattes", "Relatório Lattes", 9, "Produção, orientações, projetos e rede de colaboração dos membros do GEMEC, segundo o Currículo Lattes (scriptLattes).", P.LATTES, None),
        (19, "Contato", 8, "Endereço e contato da coordenação do GEMEC.", P.contato(url_foto), None),
    ]
    for pid, titulo, ordem, resumo, conteudo, img in lista:
        corpo = {"title": titulo, "menu_order": ordem, "excerpt": resumo, "content": conteudo, "template": ""}
        if img:
            corpo["featured_media"] = img
        if isinstance(pid, str):  # pagina nova, achada pelo endereco
            achadas = gm.ok(gm.rest(f"/wp/v2/pages?slug={pid}&status=any&context=edit"))
            if achadas:
                pid = achadas[0]["id"]
            else:
                corpo.update({"slug": pid, "status": "publish"})
                r = gm.ok(gm.rest("/wp/v2/pages", "POST", json=corpo))
                print("pagina criada", r["id"], r["link"]); continue
        r = gm.ok(gm.rest(f"/wp/v2/pages/{pid}", "POST", json=corpo))
        print("pagina", pid, r["slug"], r["link"])

def etapa_config():
    r = gm.ok(gm.rest("/wp/v2/settings", "POST", json={
        "title": "GEMEC", "description": "Grupo de Estudos em Mecânica Experimental e Computacional",
        "timezone": "America/Sao_Paulo", "date_format": "d/m/Y", "time_format": "H:i",
        "default_comment_status": "closed", "default_ping_status": "closed"}))
    print("settings:", r["title"], "|", r["description"], "|", r["timezone"])
    itens = gm.ok(gm.rest("/wp/v2/menu-items?menus=2&per_page=100&context=edit"))
    ordem = {"Gemec": ("Início", 1), "Início": ("Início", 1), "Pesquisa": ("Pesquisa", 2), "Membros": ("Membros", 3),
             "Publicações": ("Publicações", 4), "Estatísticas": ("Estatísticas", 5), "Impacto": ("Impacto", 6),
             "Parceiros": ("Parceiros", 7), "Oportunidades": ("Oportunidades", 8), "Arquivos": ("Arquivos", 9),
             "Contato": ("Contato", 10)}
    titulos = {it["title"]["raw"] or it["title"]["rendered"] for it in itens}
    tem_op = "Oportunidades" in titulos
    if "Publicações" not in titulos:
        pub = gm.ok(gm.rest("/wp/v2/pages?slug=publicacoes"))
        if pub:
            gm.ok(gm.rest("/wp/v2/menu-items", "POST", json={"title": "Publicações", "menus": 2, "menu_order": 4,
                  "type": "post_type", "object": "page", "object_id": pub[0]["id"], "status": "publish"}))
            print("menu: + Publicações")
    for it in itens:
        t = it["title"]["raw"] or it["title"]["rendered"]
        if t in ordem:
            novo, pos = ordem[t]
            gm.ok(gm.rest(f"/wp/v2/menu-items/{it['id']}", "POST", json={"title": novo, "menu_order": pos}))
            print("menu:", t, "->", novo, pos)
    if not tem_op:
        gm.ok(gm.rest("/wp/v2/menu-items", "POST", json={"title": "Oportunidades", "menus": 2, "menu_order": 5,
              "type": "post_type", "object": "page", "object_id": 412, "status": "publish"}))
        print("menu: + Oportunidades")
    menu_impacto()
    r = gm.rest("/wp/v2/menus/2", "POST", json={"locations": ["principal"]})
    print("local do menu:", r.status_code, r.json().get("locations") if r.ok else r.text[:300])

def menu_impacto():
    """Estatísticas e Impacto como itens próprios do menu principal, depois de Publicações."""
    itens = gm.ok(gm.rest("/wp/v2/menu-items?menus=2&per_page=100&context=edit"))
    por_titulo = {(it["title"]["raw"] or it["title"]["rendered"]): it for it in itens}
    pag = gm.ok(gm.rest("/wp/v2/pages?slug=impacto"))
    if not pag:
        print("menu: página impacto não existe, rode a etapa paginas"); return
    # pela página, não pelo título: o item herda o título da página ("Impacto científico")
    achado = [it for it in itens if it.get("object_id") == pag[0]["id"]]
    if achado:
        imp = achado[0]["id"]
    else:
        imp = gm.ok(gm.rest("/wp/v2/menu-items", "POST", json={"title": "Impacto", "menus": 2, "menu_order": 6,
              "type": "post_type", "object": "page", "object_id": pag[0]["id"], "status": "publish"}))["id"]
        print("menu: + Impacto")
    est = por_titulo.get("Estatísticas")
    if est and (est["parent"] or est["menu_order"] != 5):
        gm.ok(gm.rest(f"/wp/v2/menu-items/{est['id']}", "POST", json={"parent": 0, "menu_order": 5}))
        print("menu: Estatísticas -> item próprio")
    if imp:
        gm.ok(gm.rest(f"/wp/v2/menu-items/{imp}", "POST", json={"title": "Impacto", "menu_order": 6, "parent": 0}))

def etapa_impacto():
    """Só o necessário para a página Impacto: plugin, página e menu."""
    zipar(os.path.join(RAIZ, "plugins", "gemec-ranking"), "gemec-ranking")
    ok, msg = gm.enviar_zip("plugin", os.path.join(DIST, "gemec-ranking.zip"))
    print("gemec-ranking", "enviado" if ok else "FALHOU: " + msg)
    r = gm.rest("/wp/v2/plugins/gemec-ranking/gemec-ranking", "POST", json={"status": "active"})
    print("  ativar:", r.status_code, r.json().get("status") if r.ok else r.text[:400])
    achadas = gm.ok(gm.rest("/wp/v2/pages?slug=impacto&status=any&context=edit"))
    corpo = {"title": "Impacto científico", "menu_order": 6, "content": P.IMPACTO, "template": "",
             "excerpt": "Dois pesquisadores do GEMEC estão na edição 2026 da lista Stanford/Elsevier, que reúne os cientistas de maior impacto de citações em cada área."}
    if achadas:
        r = gm.ok(gm.rest(f"/wp/v2/pages/{achadas[0]['id']}", "POST", json=corpo))
    else:
        corpo.update({"slug": "impacto", "status": "publish"})
        r = gm.ok(gm.rest("/wp/v2/pages", "POST", json=corpo))
    print("pagina", r["id"], r["link"])
    itens = gm.ok(gm.rest("/wp/v2/menu-items?menus=2&per_page=100&context=edit"))
    ordem = {"Parceiros": 7, "Oportunidades": 8, "Arquivos": 9, "Contato": 10}
    for it in itens:
        t = it["title"]["raw"] or it["title"]["rendered"]
        if t in ordem and it["menu_order"] != ordem[t]:
            gm.ok(gm.rest(f"/wp/v2/menu-items/{it['id']}", "POST", json={"menu_order": ordem[t]}))
    menu_impacto()

def etapa_ativar_tema():
    h = gm.s.get(gm.BASE + "/wp-admin/themes.php").text.replace("\\/", "/").replace("\\u0026", "&").replace("&amp;", "&")
    m = re.search(r'action=activate&stylesheet=gemec&_wpnonce=([0-9a-f]+)', h)
    if not m:
        raise SystemExit("nonce de ativacao do tema nao encontrado")
    r = gm.s.get(gm.BASE + f"/wp-admin/themes.php?action=activate&stylesheet=gemec&_wpnonce={m.group(1)}")
    print("ativar tema:", r.status_code, r.url)

# Plugins de terceiros: so desativados (reversivel). Apagar fica a criterio do grupo.
TERCEIROS = ["tinymce-advanced/tinymce-advanced", "column-shortcodes/column-shortcodes",
             "feature-a-page-widget/feature-a-page-widget", "jetpack/jetpack", "mashsharer/mashshare",
             "gallery-by-supsystic/index", "slider-wd/slider-wd", "spacer/index", "title-remover/title-remover",
             "wp-cerber/wp-cerber", "wordpress-seo/wp-seo"]

def etapa_desativar():
    for pl in TERCEIROS:
        r = gm.rest(f"/wp/v2/plugins/{pl}", "POST", json={"status": "inactive"})
        print("desativar", pl, r.status_code, r.json().get("status") if r.ok else r.text[:200])

if __name__ == "__main__":
    gm.login()
    for e in sys.argv[1:]:
        print("==", e)
        globals()["etapa_" + e.replace("-", "_")]()
