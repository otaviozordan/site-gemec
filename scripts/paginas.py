"""Conteudo das paginas em blocos (formato do editor do WordPress 6.1)."""

def p(txt, cls=None):
    if cls:
        return f'<!-- wp:paragraph {{"className":"{cls}"}} -->\n<p class="{cls}">{txt}</p>\n<!-- /wp:paragraph -->'
    return f'<!-- wp:paragraph -->\n<p>{txt}</p>\n<!-- /wp:paragraph -->'

def h(txt, nivel=2, cls=None):
    attrs = {}
    if nivel != 2:
        attrs["level"] = nivel
    if cls:
        attrs["className"] = cls
    import json
    a = (" " + json.dumps(attrs, ensure_ascii=False)) if attrs else ""
    c = f' class="{cls}"' if cls else ""
    return f'<!-- wp:heading{a} -->\n<h{nivel}{c}>{txt}</h{nivel}>\n<!-- /wp:heading -->'

def sc(code):
    return f'<!-- wp:shortcode -->\n{code}\n<!-- /wp:shortcode -->'

def grupo(cls, *filhos):
    return f'<!-- wp:group {{"className":"{cls}"}} -->\n<div class="wp-block-group {cls}">' + "\n".join(filhos) + '</div>\n<!-- /wp:group -->'

def botoes(*bts, cls=None):
    itens = []
    for rotulo, url, estilo in bts:
        if estilo == "outline":
            itens.append(f'<!-- wp:button {{"className":"is-style-outline"}} -->\n<div class="wp-block-button is-style-outline"><a class="wp-block-button__link wp-element-button" href="{url}">{rotulo}</a></div>\n<!-- /wp:button -->')
        else:
            itens.append(f'<!-- wp:button -->\n<div class="wp-block-button"><a class="wp-block-button__link wp-element-button" href="{url}">{rotulo}</a></div>\n<!-- /wp:button -->')
    a = f' {{"className":"{cls}"}}' if cls else ""
    c = f" {cls}" if cls else ""
    return f'<!-- wp:buttons{a} -->\n<div class="wp-block-buttons{c}">' + "\n".join(itens) + '</div>\n<!-- /wp:buttons -->'

def colunas(cols, cls=None):
    """cols: lista de (largura ou None, classe ou None, [blocos])"""
    a = f' {{"className":"{cls}"}}' if cls else ""
    c = f" {cls}" if cls else ""
    out = [f'<!-- wp:columns{a} -->\n<div class="wp-block-columns{c}">']
    for larg, ccls, blocos in cols:
        attrs, estilo, classe = {}, "", "wp-block-column"
        if larg:
            attrs["width"] = larg
            estilo = f' style="flex-basis:{larg}"'
        if ccls:
            attrs["className"] = ccls
            classe += " " + ccls
        import json
        aa = (" " + json.dumps(attrs)) if attrs else ""
        out.append(f'<!-- wp:column{aa} -->\n<div class="{classe}"{estilo}>' + "\n".join(blocos) + '</div>\n<!-- /wp:column -->')
    out.append('</div>\n<!-- /wp:columns -->')
    return "\n".join(out)

def imagem(id_, url, alt=""):
    return (f'<!-- wp:image {{"id":{id_},"sizeSlug":"large","linkDestination":"none","className":"g-foto"}} -->\n'
            f'<figure class="wp-block-image size-large g-foto"><img src="{url}" alt="{alt}" class="wp-image-{id_}"/></figure>\n<!-- /wp:image -->')

def card(selo, titulo, texto, bt=None, off=False):
    filhos = [p(selo, "g-selo"), h(titulo, 3), p(texto)]
    if bt:
        filhos.append(botoes(bt + ("fill",), cls="g-azul"))
    return grupo("g-card" + (" g-card-off" if off else ""), *filhos)


# ------------------------------------------------------------------ paginas

INICIO = "\n\n".join([
    grupo("g-secao",
        colunas([
            ("38%", "g-col-fixa", [p("Sobre o grupo", "g-eyebrow"), h("Mecânica experimental e computacional a serviço da engenharia", 2, "g-titulo-secao")]),
            (None, None, [
                p('Bem-vindo ao <strong>Grupo de Estudos em Mecânica Experimental e Computacional</strong> (GEMEC) do Instituto de Engenharia Mecânica da Universidade Federal de Itajubá.', "g-lead"),
                p("O GEMEC aplica metodologias teóricas, experimentais e numéricas a problemas de projeto, materiais e processos de fabricação. O grupo desenvolve novas soluções, pesquisas e tecnologias em mecânica experimental e computacional, inteligência artificial e otimização, nas áreas de mecânica, aeroespacial e civil."),
                p("As principais frentes de atuação são mecânica estrutural, vibrações mecânicas, análise modal experimental, materiais compósitos e inteligentes, detecção e identificação de danos, métodos inversos, modelagem e simulação, método dos elementos finitos, otimização, controle de sistemas mecânicos e aeroespaciais, controle não linear e inteligência artificial aplicada."),
                botoes(("Conheça as linhas de pesquisa", "/pesquisa/", "outline")),
            ]),
        ])),
    grupo("g-secao g-faixa", sc("[gemec_numeros]")),
    grupo("g-secao",
        p("Pesquisa", "g-eyebrow"),
        h("Linhas de pesquisa", 2, "g-titulo-secao"),
        p("Sete frentes que combinam teoria, experimento e simulação numérica.", "g-sub"),
        sc("[gemec_linhas]"),
        botoes(("Ver todos os tópicos", "/pesquisa/", "outline"))),
    grupo("g-secao",
        p("Colaboração", "g-eyebrow"),
        h("Parceiros e apoiadores", 2, "g-titulo-secao"),
        p("Agências de fomento, empresas e fornecedores de tecnologia que apoiam as pesquisas do grupo.", "g-sub"),
        sc('[gemec_parceiros modo="faixa"]'),
        botoes(("Todos os parceiros", "/parceiros/", "outline"))),
    grupo("g-secao",
        grupo("g-cta",
            grupo("g-cta-txt", h("Quer fazer parte do GEMEC?", 2), p("Há oportunidades de iniciação científica, mestrado e pós-doutorado.")),
            botoes(("Ver oportunidades", "/oportunidades/", "fill")))),
])

PESQUISA = "\n\n".join([
    p("As pesquisas do GEMEC combinam modelagem teórica, ensaios em laboratório e simulação numérica. Cada linha abaixo reúne os tópicos em que o grupo orienta trabalhos e desenvolve projetos.", "g-lead"),
    sc('[gemec_linhas modo="completo"]'),
    grupo("g-secao",
        grupo("g-cta",
            grupo("g-cta-txt", h("Projetos, orientações e produção científica", 2), p("A produção de cada professor está no Currículo Lattes, com link no perfil de cada um na página Membros.")),
            botoes(("Relatório Lattes do grupo", "/relatorio-lattes/", "fill"), ("Ver os professores", "/membros/#professor", "outline")))),
])

MEMBROS = sc("[gemec_equipe]")

PUBLICACOES = sc("[gemec_publicacoes]")

LATTES = sc("[gemec_lattes]")

ESTATISTICAS = sc("[gemec_estatisticas]")

def _lista(*itens):
    lis = "\n".join(f"<!-- wp:list-item -->\n<li>{i}</li>\n<!-- /wp:list-item -->" for i in itens)
    return f"<!-- wp:list -->\n<ul>{lis}</ul>\n<!-- /wp:list -->"

def _pesquisador(subarea, nome, papel, destaque, legenda, linhas):
    return grupo("g-impacto-card",
        p(subarea, "g-selo"),
        h(nome, 3),
        p(papel, "g-impacto-papel"),
        p(destaque, "g-impacto-num"),
        p(legenda, "g-impacto-legenda"),
        *[p(f"<span>{r}</span> <strong>{v}</strong>", "g-impacto-linha") for r, v in linhas])

# Edicao 2026 (dados de 2025) da lista Stanford/Elsevier. Numeros de
# scripts/ranking/resumo_metricas.json, sem autocitacoes salvo onde dito.
IMPACTO = "\n\n".join([grupo("g-impacto",
    p("A edição de 2026 da lista Stanford/Elsevier, publicada em 7 de outubro, inclui dois pesquisadores do GEMEC: "
      "o professor <strong>Guilherme Ferreira Gomes</strong>, líder do grupo, e o pesquisador visitante "
      "<strong>João Luiz Junho Pereira</strong>. Os dois são os únicos nomes da UNIFEI na lista referente a 2025.", "g-lead"),

    h("O que é a lista"),
    p("A lista é preparada por John Ioannidis, da Universidade Stanford, com dados da base Scopus, da Elsevier. "
      "Ela ordena pesquisadores de todas as áreas por um indicador de citações, o <em>c-score</em>, e reúne os "
      "100 mil mais bem colocados do mundo e os que estão entre os 2% melhores da própria subárea. Como cada área "
      "cita em um ritmo diferente, a comparação mais justa é dentro da subárea: são 174, como Materiais ou "
      "Inteligência Artificial."),
    p("Há duas versões, uma para a carreira inteira e outra só com as citações recebidas em um ano. "
      "Esta página usa a versão anual de 2025, que tem 249.310 pesquisadores."),

    h("Como o c-score funciona"),
    p("O c-score soma seis indicadores, cada um em escala logarítmica: o total de citações, o índice h, o índice hm "
      "(que divide o crédito entre os coautores) e as citações dos trabalhos em que a pessoa é autora única, "
      "primeira autora ou última autora. Por isso ele valoriza não só quanto um trabalho é citado, mas também o "
      "papel do pesquisador nele. Os números abaixo descontam as autocitações, a leitura mais conservadora."),

    h("Os resultados do GEMEC"),
    colunas([
        (None, None, [_pesquisador("Materiais", "Guilherme Ferreira Gomes", "Líder do GEMEC · primeira publicação em 2017",
            "Top 0,40%", "1.310º entre os 330.896 pesquisadores de Materiais do mundo",
            [("Citações recebidas em 2025", "871"), ("Índice h em 2025", "13"),
             ("No Brasil, em Materiais", "4º de 30 na lista"), ("Na lista de carreira", "top 1,79%")])]),
        (None, None, [_pesquisador("Inteligência Artificial", "João Luiz Junho Pereira", "Pesquisador visitante · primeira publicação em 2020",
            "Top 2,25%", "11.629º entre os 517.648 pesquisadores de Inteligência Artificial e Processamento de Imagens",
            [("Citações recebidas em 2025", "358"), ("Índice h em 2025", "8"),
             ("Contando autocitações", "top 1,83%"), ("Trabalhos citados em 2025", "40")])]),
    ], cls="g-impacto-cards"),
    p("Entre os dez primeiros de Materiais no Brasil, Guilherme é o de carreira mais recente: a primeira publicação "
      "dele é de 2017, e a dos outros nove vai de 1971 a 2013. João, com primeira publicação em 2020, entrou na lista "
      "com apenas seis anos de carreira."),

    h("Explore os dados"),
    p("O painel abaixo mostra as mesmas medidas em detalhe. Use o seletor <strong>Sem autocitações / Todas as "
      "citações</strong> para trocar a base, escolha um recorte (Materiais no Brasil ou no mundo, Engenharia no "
      "Brasil, UNIFEI) e passe o mouse sobre os pontos. A tabela permite buscar qualquer pesquisador do recorte e "
      "compará-lo com Guilherme."),
    sc("[gemec_ranking]"),

    h("Como ler esses números"),
    _lista("A lista mede o impacto de citações, não a qualidade ou a relevância de um trabalho.",
           "A subárea de cada pesquisador é definida pela própria base, conforme as revistas em que publica. "
           "A de Guilherme é Materiais, com Engenharia Mecânica e Transportes como segunda.",
           "As posições no Brasil contam só quem está na lista e tem afiliação no país.",
           "A lista não é um prêmio nem um certificado de Stanford ou da Elsevier: é uma base de dados pública "
           "com indicadores padronizados, atualizada uma vez por ano."),

    h("Fonte", 3),
    p("Ioannidis, J. P. A. (2026). <em>August 2026 data-update for “Updated science-wide author databases of "
      "standardized citation indicators”</em>. Elsevier Data Repository, V9. "
      '<a href="https://doi.org/10.17632/btchxktzyw.9">doi:10.17632/btchxktzyw.9</a>. '
      "Metodologia: Ioannidis, Boyack e Baas (2020), <em>PLOS Biology</em>, "
      '<a href="https://doi.org/10.1371/journal.pbio.3000918">doi:10.1371/journal.pbio.3000918</a>. '
      "Dados sob licença CC BY-NC 3.0.", "g-impacto-fonte"),
)])

PARCEIROS = sc("[gemec_parceiros]")

OPORTUNIDADES = "\n\n".join([
    sc("[gemec_oportunidades]"),
    grupo("g-secao",
        h("Processo seletivo da pós-graduação", 2, "g-titulo-secao"),
        p('O ingresso no mestrado e no doutorado segue os editais do Programa de Pós-Graduação em Engenharia Mecânica da UNIFEI. Veja os <a href="https://prppg.unifei.edu.br/ppgeme/">editais do PPGEM</a> e a <a href="https://unifei.edu.br/ensino/pos-graduacao/">pós-graduação na UNIFEI</a>. Dúvidas podem ser enviadas à <a href="/contato/">coordenação do grupo</a>.')),
])

ARQUIVOS = colunas([
    (None, None, [card(".pptx", "Template de apresentação", "Modelo de slides do GEMEC para seminários, defesas e congressos.",
                       ("Baixar o modelo", "https://gemec.unifei.edu.br/wp-content/uploads/2023/01/Presentation-template.pptx"))]),
    (None, None, [card(".docx · em breve", "Template de dissertação e tese", "Modelo em Word para dissertações e teses. Em preparação.", off=True)]),
    (None, None, [card(".tex · em breve", "Template de dissertação e tese", "Modelo em LaTeX para dissertações e teses. Em preparação.", off=True)]),
], cls="g-cards")

def contato(url_foto):
    return colunas([
        (None, None, [
            grupo("g-contato-bloco",
                h("Endereço", 3),
                p("<strong>Grupo de Estudos em Mecânica Experimental e Computacional</strong><br>Instituto de Engenharia Mecânica<br>Universidade Federal de Itajubá<br>Av. BPS, 1303, Pinheirinho, Itajubá – MG")),
            grupo("g-contato-bloco",
                h("Coordenação", 3),
                p('<strong>Prof. Dr. Guilherme Ferreira Gomes</strong> (coordenador)<br><a href="mailto:guilhermefergom@unifei.edu.br">guilhermefergom@unifei.edu.br</a>', "g-contato-pessoa"),
                p('<strong>Prof. Dr. Yohan Alí Diaz Mendéz</strong><br><a href="mailto:yohan.g8@unifei.edu.br">yohan.g8@unifei.edu.br</a>', "g-contato-pessoa")),
            grupo("g-contato-bloco",
                h("Processo seletivo", 3),
                p('Editais em <a href="/oportunidades/">Oportunidades</a> e no site da <a href="https://unifei.edu.br/ensino/pos-graduacao/">pós-graduação da UNIFEI</a>.')),
        ]),
        ("46%", None, [imagem(318, url_foto, "Prédio da UNIFEI em Itajubá")]),
    ])
