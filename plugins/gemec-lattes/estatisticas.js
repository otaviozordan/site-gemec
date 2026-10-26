/* Estatisticas: o Relatorio Lattes navegavel.
   - listas completas (listas.json, comprimido pelo plugin) com busca e filtros;
     clicar num grafico, nivel ou tipo filtra a lista certa e rola ate ela
   - ficha de cada membro (como as paginas por membro do relatorio): toda a
     producao, orientacoes, projetos, eventos, premios e colaboracoes
   - grafo de colaboracoes com forcas, zoom, busca e painel do pesquisador
     (d3 do proprio relatorio) */
(function () {
	var cfg = window.GEMEC_LATTES;
	// Pagina Estatisticas ou perfil de um membro (abas da ficha dentro da pagina).
	var raiz = document.querySelector('[data-gemec-est]') || document.querySelector('[data-gemec-perfil]');
	var proprio = raiz && raiz.hasAttribute('data-gemec-perfil') ? +raiz.getAttribute('data-gemec-perfil') : -1;
	if (!raiz || !cfg) {
		return;
	}
	var membros = cfg.membros || [];
	var PASSO = 5; // itens a vista em cada lista; o resto com "Mostrar todos"
	var dados = null;
	var esperando = [];
	var listas = {};

	function esc(s) {
		return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
	}
	function fmt(n) { return Number(n).toLocaleString('pt-BR'); }
	function normal(s) { return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
	function etq(txt, cls) { return txt ? '<span class="gemec-est-etq' + (cls ? ' gemec-est-etq-' + cls : '') + '">' + esc(txt) + '</span>' : ''; }
	function curto(n) { var p = String(n).split(/\s+/); return p.length > 1 ? p[0] + ' ' + p[p.length - 1] : n; }
	function link(m) {
		var p = membros[m];
		if (!p) { return ''; }
		return '<a href="' + esc(p.u || 'http://lattes.cnpq.br/' + p.l) + '" data-ficha="' + m + '">' + esc(p.n) + '</a>';
	}
	// Rosto do membro (foto ou iniciais), com link que abre a ficha.
	function rosto(m) {
		var p = membros[m];
		if (!p) { return ''; }
		var ini = p.n.split(/\s+/).filter(function (x) { return x.length > 2; });
		ini = ((ini[0] || '')[0] || '') + ((ini[ini.length - 1] || '')[0] || '');
		return '<a class="gemec-rosto" href="' + esc(p.u || 'http://lattes.cnpq.br/' + p.l) + '" data-ficha="' + m + '" title="' + esc(p.n) + '" aria-label="' + esc(p.n) + '">' +
			(p.f ? '<img src="' + esc(p.f) + '" alt="" loading="lazy">' : '<span>' + esc(ini.toUpperCase()) + '</span>') + '</a>';
	}
	function pe(rot, ms, extra) {
		var h = '';
		ms = (ms || []).filter(function (m) { return m !== proprio; });
		if (ms.length) { h += '<span class="gemec-rostos">' + ms.map(rosto).join('') + '</span><span class="gemec-est-item-quem">' + rot + ' ' + ms.map(link).join(', ') + '</span>'; }
		if (extra) { h += extra; }
		return h ? '<p class="gemec-est-item-pe">' + h + '</p>' : '';
	}
	function doi(d) {
		if (!d) { return ''; }
		var u = /^https?:/i.test(d) ? d : 'https://doi.org/' + d.replace(/^doi:\s*/i, '');
		return '<a class="gemec-est-doi" href="' + esc(u) + '" target="_blank" rel="noopener">DOI <span aria-hidden="true">&#8599;</span></a>';
	}
	var porNome = {};
	membros.forEach(function (p, i) { porNome[normal(p.n)] = i; });
	function nomeEquipe(n) { return porNome[normal(n)] !== undefined ? link(porNome[normal(n)]) : esc(n); }
	function quandoProntos(fn) { if (dados) { fn(dados); } else { esperando.push(fn); } }

	var NIVEL = { posdoc: 'Pós-doutorado', doutorado: 'Doutorado', mestrado: 'Mestrado', especializacao: 'Especialização', tcc: 'TCC', ic: 'Iniciação científica', outra: 'Outra natureza' };
	var PAPEL = { Coorientador: 'Coorientação', Supervisor: 'Supervisão' };

	/* ----------------------------------------------------- tipos de lista */
	function producao(chave) {
		return {
			itens: function (d) { return d[chave] || []; },
			filtros: function (d) {
				var tipos = d[chave + '_tipos'] || {};
				return [{ k: 't', rot: 'Tipo', tipo: 'sel', todos: 'Todos os tipos', ops: Object.keys(tipos).map(function (k) { return [k, tipos[k]]; }), de: function (it) { return it.t; } }];
			},
			grupo: function (it, d) { return [it.t, (d[chave + '_tipos'] || {})[it.t] || '']; },
			busca: function (it) { return [it.ti, it.au, it.v, it.a].join(' '); },
			html: function (it, d) {
				var tipos = d[chave + '_tipos'] || {};
				return '<div class="gemec-est-item-topo">' + etq(tipos[it.t]) + (it.a ? '<span class="gemec-est-ano">' + it.a + '</span>' : '') + '</div>' +
					'<p class="gemec-est-item-t">' + esc(it.ti) + '</p>' +
					(it.au ? '<p class="gemec-est-item-m">' + esc(it.au) + '</p>' : '') +
					(it.v ? '<p class="gemec-est-item-v">' + esc(it.v) + '</p>' : '') +
					pe('Membros:', it.m, doi(it.doi));
			}
		};
	}

	var LISTAS = {
		biblio: producao('biblio'),
		tecnica: producao('tecnica'),
		artistica: producao('artistica'),
		orientacoes: {
			itens: function (d) { return d.orientacoes || []; },
			filtros: function () {
				return [
					{ k: 's', rot: 'Situação', tipo: 'seg', todos: 'Todas', ops: [['c', 'Concluídas'], ['a', 'Em andamento']], de: function (it) { return it.s; } },
					{ k: 't', rot: 'Nível', tipo: 'sel', todos: 'Todos os níveis', ops: Object.keys(NIVEL).map(function (k) { return [k, NIVEL[k]]; }), de: function (it) { return it.t; } }
				];
			},
			grupo: function (it) { return [it.s + it.t, (it.s === 'a' ? 'Em andamento · ' : 'Concluídas · ') + NIVEL[it.t]]; },
			busca: function (it) { return [it.n, it.ti, it.c, it.f, it.a].join(' '); },
			html: function (it) {
				var meta = [it.ti ? '<strong>' + esc(it.n) + '</strong>' : '', esc(it.c), it.f ? 'Fomento: ' + esc(it.f) : ''].filter(Boolean);
				return '<div class="gemec-est-item-topo">' + etq(NIVEL[it.t]) + (it.s === 'a' ? etq('Em andamento', 'and') : '') + etq(PAPEL[it.p], 'mudo') +
					(it.a ? '<span class="gemec-est-ano">' + it.a + '</span>' : '') + '</div>' +
					'<p class="gemec-est-item-t">' + esc(it.ti || it.n) + '</p>' +
					(meta.length ? '<p class="gemec-est-item-m">' + meta.join(' · ') + '</p>' : '') +
					pe(it.p === 'Supervisor' ? 'Supervisão:' : 'Orientação:', it.m);
			}
		},
		projetos: {
			itens: function (d) { return d.projetos || []; },
			ano: function (it) { return +it.i || 0; },
			filtros: function () {
				return [{ k: 's', rot: 'Situação', tipo: 'seg', todos: 'Todos', ops: [['a', 'Em andamento'], ['c', 'Concluídos']], de: function (it) { return it.f ? 'c' : 'a'; } }];
			},
			grupo: function (it) { return it.f ? ['c', 'Concluídos'] : ['a', 'Em andamento']; },
			busca: function (it) { return [it.n, it.d, it.i, it.f, it.e.map(function (e) { return e[0]; }).join(' ')].join(' '); },
			html: function (it) {
				var coord = it.e.filter(function (e) { return /coord/i.test(e[1]); }).map(function (e) { return nomeEquipe(e[0]); });
				var outros = it.e.filter(function (e) { return !/coord/i.test(e[1]); }).map(function (e) { return nomeEquipe(e[0]); });
				var periodo = it.f ? (it.i === it.f ? it.f : it.i + '–' + it.f) : 'Desde ' + it.i;
				var meta = [coord.length ? 'Coordenação: ' + coord.join(', ') : '', outros.length ? 'Equipe: ' + outros.join(', ') : ''].filter(Boolean);
				return '<div class="gemec-est-item-topo">' + (it.f ? etq('Concluído') : etq('Em andamento', 'and')) + '<span class="gemec-est-ano">' + esc(periodo) + '</span></div>' +
					'<p class="gemec-est-item-t">' + esc(it.n) + '</p>' +
					(meta.length ? '<p class="gemec-est-item-m">' + meta.join(' · ') + '</p>' : '') +
					(it.d ? '<details class="gemec-est-item-d"><summary>Resumo</summary><p>' + esc(it.d) + '</p></details>' : '');
			}
		},
		eventos: {
			itens: function (d) { return d.eventos || []; },
			filtros: function (d) {
				var tipos = {};
				(d.eventos || []).forEach(function (e) { if (e.tp) { tipos[e.tp] = 1; } });
				return [
					{ k: 'k', rot: 'Participação ou organização', tipo: 'seg', todos: 'Todos', ops: [['p', 'Participação'], ['o', 'Organização']], de: function (it) { return it.k; } },
					{ k: 'tp', rot: 'Tipo de evento', tipo: 'sel', todos: 'Todos os tipos', ops: Object.keys(tipos).sort().map(function (k) { return [k, k]; }), de: function (it) { return it.tp; } }
				];
			},
			grupo: function (it) { return it.k === 'o' ? ['o', 'Organização de eventos'] : ['p', 'Participação em eventos']; },
			busca: function (it) { return [it.ev, it.ti, it.tp, it.au, it.a].join(' '); },
			html: function (it) {
				var org = it.k === 'o';
				return '<div class="gemec-est-item-topo">' + (org ? etq('Organização', 'and') : etq('Participação')) + etq(it.tp, 'mudo') + (it.a ? '<span class="gemec-est-ano">' + it.a + '</span>' : '') + '</div>' +
					'<p class="gemec-est-item-t">' + esc(org ? it.ev : (it.ti || it.ev)) + '</p>' +
					(!org && it.ti ? '<p class="gemec-est-item-v">' + esc(it.ev) + '</p>' : '') +
					(org && it.au ? '<p class="gemec-est-item-m">' + esc(it.au) + '</p>' : '') +
					pe('Membros:', it.m);
			}
		},
		premios: {
			itens: function (d) { return d.premios || []; },
			filtros: function () { return []; },
			grupo: function () { return ['p', 'Prêmios e títulos']; },
			busca: function (it) { return [it.ti, it.a].join(' '); },
			html: function (it) {
				return '<div class="gemec-est-item-topo">' + etq('Prêmio') + (it.a ? '<span class="gemec-est-ano">' + it.a + '</span>' : '') + '</div><p class="gemec-est-item-t">' + esc(it.ti) + '</p>' + pe('Membros:', it.m);
			}
		}
	};
	function anoDe(spec, it) { return spec.ano ? spec.ano(it) : it.a; }

	/* ------------------------------------------------- listas da pagina */
	function montar(caixa, chave, d) {
		var spec = LISTAS[chave];
		var itens = spec.itens(d);
		var filtros = spec.filtros(d);
		var idx = itens.map(function (it) { return normal(spec.busca(it)); });
		var estado;
		function zerar() {
			estado = { q: '', m: '', ano: 0, limite: PASSO };
			filtros.forEach(function (f) { estado[f.k] = ''; });
		}
		zerar();

		filtros.forEach(function (f) {
			var c = {};
			itens.forEach(function (it) { var v = f.de(it); c[v] = (c[v] || 0) + 1; });
			f.ops = f.ops.filter(function (o) { return c[o[0]]; }).map(function (o) { return [o[0], o[1], c[o[0]]]; });
		});
		var porMembro = {};
		itens.forEach(function (it) { (it.m || []).forEach(function (m) { porMembro[m] = (porMembro[m] || 0) + 1; }); });
		var opsMembro = Object.keys(porMembro).map(Number).sort(function (a, b) { return (membros[a] ? membros[a].n : '').localeCompare(membros[b] ? membros[b].n : '', 'pt-BR'); });

		var h = '<div class="gemec-est-barra-ferr" role="search"><label class="gemec-est-busca"><span class="screen-reader-text">Buscar</span><input type="search" placeholder="Buscar em ' + fmt(itens.length) + ' itens" autocomplete="off"></label>';
		filtros.forEach(function (f) {
			if (f.tipo === 'seg' && f.ops.length > 1) {
				h += '<div class="gemec-est-seg" role="group" aria-label="' + esc(f.rot) + '" data-k="' + f.k + '"><button type="button" data-v="" aria-pressed="true">' + esc(f.todos) + '</button>' +
					f.ops.map(function (o) { return '<button type="button" data-v="' + esc(o[0]) + '" aria-pressed="false">' + esc(o[1]) + ' <span>' + fmt(o[2]) + '</span></button>'; }).join('') + '</div>';
			} else if (f.tipo === 'sel' && f.ops.length > 1) {
				h += '<label class="gemec-est-sel"><span class="screen-reader-text">' + esc(f.rot) + '</span><select data-k="' + f.k + '"><option value="">' + esc(f.todos) + '</option>' +
					f.ops.map(function (o) { return '<option value="' + esc(o[0]) + '">' + esc(o[1]) + ' (' + fmt(o[2]) + ')</option>'; }).join('') + '</select></label>';
			}
		});
		if (opsMembro.length > 1) {
			h += '<label class="gemec-est-sel"><span class="screen-reader-text">Membro</span><select data-k="m"><option value="">Todos os membros</option>' +
				opsMembro.map(function (m) { return '<option value="' + m + '">' + esc(membros[m] ? membros[m].n : '') + ' (' + fmt(porMembro[m]) + ')</option>'; }).join('') + '</select></label>';
		}
		h += '</div><div class="gemec-est-ativos"></div><p class="gemec-est-conta" aria-live="polite"></p><ol class="gemec-est-itens"></ol>' +
			'<p class="gemec-est-vazio" hidden>Nenhum item encontrado. Tente outra busca ou limpe os filtros.</p><button type="button" class="gemec-est-mais" hidden></button>';
		caixa.innerHTML = h;

		var lista = caixa.querySelector('.gemec-est-itens');
		var conta = caixa.querySelector('.gemec-est-conta');
		var ativos = caixa.querySelector('.gemec-est-ativos');
		var vazio = caixa.querySelector('.gemec-est-vazio');
		var mais = caixa.querySelector('.gemec-est-mais');
		var campo = caixa.querySelector('input[type="search"]');

		function sincronizar() {
			campo.value = estado.q;
			caixa.querySelectorAll('.gemec-est-seg').forEach(function (g) {
				var v = estado[g.getAttribute('data-k')];
				g.querySelectorAll('button').forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-v') === String(v) ? 'true' : 'false'); });
			});
			caixa.querySelectorAll('select').forEach(function (s) { s.value = String(estado[s.getAttribute('data-k')]); });
		}
		function aplicar() {
			var termos = normal(estado.q).split(/\s+/).filter(Boolean);
			var m = estado.m === '' ? null : +estado.m;
			var ok = [];
			itens.forEach(function (it, i) {
				for (var j = 0; j < filtros.length; j++) {
					if (estado[filtros[j].k] !== '' && String(filtros[j].de(it)) !== String(estado[filtros[j].k])) { return; }
				}
				if (m !== null && (it.m || []).indexOf(m) < 0) { return; }
				if (estado.ano && anoDe(spec, it) !== estado.ano) { return; }
				for (var t = 0; t < termos.length; t++) {
					if (idx[i].indexOf(termos[t]) < 0) { return; }
				}
				ok.push(it);
			});
			lista.innerHTML = ok.slice(0, estado.limite).map(function (it) { return '<li class="gemec-est-item">' + spec.html(it, d) + '</li>'; }).join('');
			vazio.hidden = ok.length > 0;
			mais.hidden = ok.length <= estado.limite;
			mais.textContent = 'Mostrar todos os ' + fmt(ok.length) + ' itens';
			conta.textContent = ok.length === itens.length ? fmt(itens.length) + ' itens' : fmt(ok.length) + ' de ' + fmt(itens.length) + ' itens';
			var filtrado = estado.q || estado.m !== '' || estado.ano || filtros.some(function (f) { return estado[f.k] !== ''; });
			ativos.innerHTML = (estado.ano ? '<button type="button" class="gemec-est-chip" data-tira="ano">Ano: ' + estado.ano + ' <span aria-hidden="true">&times;</span></button>' : '') +
				(filtrado ? '<button type="button" class="gemec-est-limpar">Limpar filtros</button>' : '');
		}
		caixa.addEventListener('click', function (ev) {
			var bt = ev.target.closest('.gemec-est-seg button');
			if (bt) {
				estado[bt.parentNode.getAttribute('data-k')] = bt.getAttribute('data-v');
				estado.limite = PASSO;
				sincronizar();
				aplicar();
			} else if (ev.target.closest('[data-tira="ano"]')) {
				estado.ano = 0;
				aplicar();
			} else if (ev.target.closest('.gemec-est-limpar')) {
				zerar();
				sincronizar();
				aplicar();
			}
		});
		caixa.addEventListener('change', function (ev) {
			if (ev.target.tagName !== 'SELECT') { return; }
			estado[ev.target.getAttribute('data-k')] = ev.target.value;
			estado.limite = PASSO;
			aplicar();
		});
		var adiar;
		campo.addEventListener('input', function () {
			clearTimeout(adiar);
			adiar = setTimeout(function () { estado.q = campo.value; estado.limite = PASSO; aplicar(); }, 120);
		});
		mais.addEventListener('click', function () { estado.limite = Infinity; aplicar(); });
		aplicar();

		// Filtro vindo de fora (grafico, nivel): comeca do zero e rola ate a lista.
		return function (f) {
			zerar();
			Object.keys(f).forEach(function (k) { if (k in estado) { estado[k] = f[k]; } });
			sincronizar();
			aplicar();
			var bloco = caixa.closest('.gemec-est-bloco') || caixa;
			var topo = parseFloat(getComputedStyle(raiz).getPropertyValue('--est-topo')) || 80;
			window.scrollTo({ top: bloco.getBoundingClientRect().top + window.scrollY - topo - 70, behavior: 'smooth' });
		};
	}

	var caixas = raiz.querySelectorAll('[data-lista]');
	if (cfg.url && window.fetch) {
		fetch(cfg.url).then(function (r) {
			if (!r.ok) { throw new Error(r.status); }
			return r.json();
		}).then(function (d) {
			dados = d;
			caixas.forEach(function (caixa) {
				var k = caixa.getAttribute('data-lista');
				if (LISTAS[k]) { listas[k] = montar(caixa, k, d); }
			});
			esperando.forEach(function (fn) { fn(d); });
			esperando = [];
		}).catch(function () {
			caixas.forEach(function (caixa) {
				caixa.innerHTML = '<p class="gemec-est-vazio">N&atilde;o foi poss&iacute;vel carregar a lista agora. Tente recarregar a p&aacute;gina.</p>';
			});
		});
	}

	// Clique nos graficos: [lista, filtro a partir do rotulo clicado].
	function tipoPorRotulo(d, chave, rot) {
		var tipos = d[chave + '_tipos'] || {};
		return Object.keys(tipos).filter(function (k) { return tipos[k] === rot; })[0] || '';
	}
	var CLIQUES = {
		'pub-anos': ['biblio', function (r) { return { ano: +r }; }],
		'pb-tipos': ['biblio', function (r, d) { return { t: tipoPorRotulo(d, 'biblio', r) }; }],
		'pub-revistas': ['biblio', function (r) { return { q: r }; }],
		'ori-anos': ['orientacoes', function (r) { return { s: 'c', ano: +r }; }],
		'pj-anos': ['projetos', function (r) { return { ano: +r }; }],
		'pt-anos': ['tecnica', function (r) { return { ano: +r }; }],
		'pt-tipos': ['tecnica', function (r, d) { return { t: tipoPorRotulo(d, 'tecnica', r) }; }],
		'ev-anos': ['eventos', function (r) { return { ano: +r }; }],
		'ev-tipos': ['eventos', function (r) { return { k: 'p', tp: r }; }]
	};
	raiz.addEventListener('gemec-est-clique', function (ev) {
		var c = CLIQUES[ev.detail.tab];
		if (!c) { return; }
		quandoProntos(function (d) { if (listas[c[0]]) { listas[c[0]](c[1](ev.detail.rot, d)); } });
	});

	/* ------------------------------------------------------- ficha */
	var ficha = null;
	var porUrl = {};
	membros.forEach(function (p, i) { if (p.u) { porUrl[p.u.replace(/\/$/, '')] = i; } });

	function criarFicha() {
		ficha = document.createElement('dialog');
		ficha.className = 'gemec-est-ficha';
		ficha.setAttribute('aria-labelledby', 'gemec-est-ficha-t');
		ficha.innerHTML = '<div class="gemec-est-ficha-in"></div>';
		raiz.appendChild(ficha);
		ficha.addEventListener('click', function (ev) {
			if (ev.target === ficha || ev.target.closest('.gemec-est-ficha-fechar')) { ficha.close(); }
		});
	}
	document.addEventListener('click', function (ev) {
		var todos = ev.target.closest('[data-todos]');
		if (todos) {
			todos.previousElementSibling.querySelectorAll('li[hidden]').forEach(function (li) { li.hidden = false; });
			todos.remove();
			return;
		}
		var aba = ev.target.closest('.gemec-est-ficha-abas [data-aba]');
		if (aba) { mostrarAba(aba.closest('.gemec-est-ficha-in, [data-gemec-perfil]'), aba.getAttribute('data-aba')); }
	});
	function mostrarAba(caixa, k) {
		caixa.querySelectorAll('.gemec-est-ficha-abas [data-aba]').forEach(function (b) { b.setAttribute('aria-selected', b.getAttribute('data-aba') === k ? 'true' : 'false'); });
		caixa.querySelectorAll('.gemec-est-ficha-painel').forEach(function (p) { p.hidden = p.getAttribute('data-painel') !== k; });
	}

	function itensDoMembro(d, chave, i) {
		return LISTAS[chave].itens(d).filter(function (it) { return (it.m || []).indexOf(i) >= 0; });
	}
	function agrupado(d, chave, itens) {
		var spec = LISTAS[chave], grupos = {}, ordem = [];
		itens.forEach(function (it) {
			var g = spec.grupo(it, d);
			if (!grupos[g[0]]) { grupos[g[0]] = { rot: g[1], itens: [] }; ordem.push(g[0]); }
			grupos[g[0]].itens.push(it);
		});
		ordem.sort();
		return ordem.map(function (k) {
			var g = grupos[k];
			return '<h4 class="gemec-est-ficha-grupo">' + esc(g.rot) + ' <span>' + fmt(g.itens.length) + '</span></h4><ol class="gemec-est-itens">' +
				g.itens.map(function (it, n) { return '<li class="gemec-est-item"' + (n >= PASSO ? ' hidden' : '') + '>' + spec.html(it, d) + '</li>'; }).join('') + '</ol>' +
				(g.itens.length > PASSO ? '<button type="button" class="gemec-est-mais" data-todos>Mostrar todos os ' + fmt(g.itens.length) + '</button>' : '');
		}).join('');
	}
	function refItem(d, r, oculto) {
		var lista = r[0] === 'b' ? 'biblio' : 'tecnica', it = (d[lista] || [])[+r.slice(1)];
		if (!it) { return ''; }
		return '<li class="gemec-est-item"' + (oculto ? ' hidden' : '') + '><div class="gemec-est-item-topo">' + etq((d[lista + '_tipos'] || {})[it.t]) + (it.a ? '<span class="gemec-est-ano">' + it.a + '</span>' : '') +
			'</div><p class="gemec-est-item-t">' + esc(it.ti) + '</p>' + (it.v ? '<p class="gemec-est-item-v">' + esc(it.v) + '</p>' : '') + '</li>';
	}

	// Tipos que o site ja mostra em Publicacoes (no perfil, o resto vira "Outras producoes").
	var PUB_SITE = { pb0: 1, pb1: 1, pb2: 1, pb4: 1, pb5: 1 };

	/* Numeros, abas e paineis da ficha do membro i. perfil: true no perfil do
	   site, onde as publicacoes ja estao na pagina (nPubs) e a producao
	   bibliografica mostra so os outros tipos. */
	function partesFicha(d, i, perfil, nPubs) {
		var p = membros[i];
		var abas = [['biblio', perfil ? 'Outras produções' : 'Produção bibliográfica'], ['tecnica', 'Produção técnica'], ['orientacoes', 'Orientações'], ['projetos', 'Projetos'], ['eventos', 'Eventos'], ['premios', 'Prêmios']];
		var porAba = {};
		abas.forEach(function (a) { porAba[a[0]] = itensDoMembro(d, a[0], i); });
		if (perfil) { porAba.biblio = porAba.biblio.filter(function (it) { return !PUB_SITE[it.t]; }); }
		var colab = Object.keys(d.pares || {}).map(function (k) {
			var ab = k.split('-').map(Number);
			return ab[0] === i ? { j: ab[1], r: d.pares[k] } : ab[1] === i ? { j: ab[0], r: d.pares[k] } : null;
		}).filter(Boolean).sort(function (a, b) { return b.r.length - a.r.length; });

		var nOC = porAba.orientacoes.filter(function (o) { return o.s === 'c'; }).length;
		var nums = [perfil ? [nPubs, 'publicações'] : [porAba.biblio.length, 'produções bibliográficas'], [porAba.tecnica.length, 'produções técnicas'], [nOC, 'orientações concluídas'],
			[porAba.orientacoes.length - nOC, 'em andamento'], [porAba.projetos.length, 'projetos'], [colab.length, 'coautores no grupo']];
		var lista = abas.filter(function (a) { return porAba[a[0]].length; }).map(function (a) { return [a[0], a[1], porAba[a[0]].length]; });
		if (colab.length) { lista.push(['colab', 'Colaborações', colab.length]); }
		var paineis = {};
		lista.forEach(function (a) {
			if (a[0] === 'colab') {
				paineis.colab = '<p class="gemec-est-sub">Membros do grupo com quem ' + esc(curto(p.n)) + ' tem produções em comum. Abra um nome para ver os trabalhos.</p>' +
					colab.map(function (c) {
						var o = membros[c.j] || {};
						return '<details class="gemec-est-colab"><summary><span>' + esc(o.n) + '</span><b>' + fmt(c.r.length) + '</b></summary>' +
							'<ol class="gemec-est-itens">' + c.r.map(function (r, n) { return refItem(d, r, n >= PASSO); }).join('') + '</ol>' +
							(c.r.length > PASSO ? '<button type="button" class="gemec-est-mais" data-todos>Mostrar todos os ' + fmt(c.r.length) + '</button>' : '') +
							'<p><a href="' + esc(o.u || 'http://lattes.cnpq.br/' + o.l) + '" data-ficha="' + c.j + '">Abrir a ficha de ' + esc(curto(o.n || '')) + '</a></p></details>';
					}).join('');
			} else {
				paineis[a[0]] = agrupado(d, a[0], porAba[a[0]]);
			}
		});
		return { nums: nums, abas: lista, paineis: paineis };
	}
	function htmlNums(nums) {
		// zeros so ocupam espaco (o primeiro numero fica sempre)
		nums = nums.filter(function (n, k) { return k === 0 || n[0] > 0; });
		return '<div class="gemec-est-ficha-nums">' + nums.map(function (n) { return '<div><b>' + fmt(n[0]) + '</b><span>' + n[1] + '</span></div>'; }).join('') + '</div>';
	}
	function htmlAbas(abas, ativa) {
		return '<div class="gemec-est-ficha-abas" role="tablist">' + abas.map(function (a) {
			return '<button type="button" role="tab" data-aba="' + a[0] + '" aria-selected="' + (a[0] === ativa ? 'true' : 'false') + '">' + a[1] + (a[2] !== '' ? ' <span>' + fmt(a[2]) + '</span>' : '') + '</button>';
		}).join('') + '</div>';
	}
	function htmlPaineis(partes, ativa) {
		return partes.abas.map(function (a) {
			return '<div class="gemec-est-ficha-painel" role="tabpanel" data-painel="' + a[0] + '"' + (a[0] === ativa ? '' : ' hidden') + '>' + partes.paineis[a[0]] + '</div>';
		}).join('');
	}

	function abrirFicha(i, abaInicial) {
		var p = membros[i];
		if (!p) { return; }
		if (!ficha) { criarFicha(); }
		var caixa = ficha.querySelector('.gemec-est-ficha-in');
		caixa.innerHTML = '<p class="gemec-est-carrega">Carregando a ficha&hellip;</p>';
		if (!ficha.open) { ficha.showModal(); }
		quandoProntos(function (d) {
			var partes = partesFicha(d, i, false);
			var ativa = partes.abas.some(function (a) { return a[0] === abaInicial; }) ? abaInicial : (partes.abas[0] || [''])[0];
			caixa.innerHTML = '<header class="gemec-est-ficha-cab"><div><p class="gemec-est-sobre">' + esc(p.cat || 'Membro') + '</p><h2 id="gemec-est-ficha-t">' + esc(p.n) + '</h2>' +
				'<p class="gemec-est-ficha-meta">' + [p.ar, p.in].filter(Boolean).map(esc).join(' · ') + '</p>' +
				'<p class="gemec-est-ficha-meta">' + (p.bo ? etq('Bolsa CNPq: ' + p.bo) + ' ' : '') + (p.at ? 'Lattes atualizado em ' + esc(p.at) : '') + '</p></div>' +
				'<div class="gemec-est-ficha-acoes">' + (p.u ? '<a class="gemec-est-bt" href="' + esc(p.u) + '" data-perfil>Perfil no site</a>' : '') +
				'<a class="gemec-est-bt gemec-est-bt-claro" href="http://lattes.cnpq.br/' + esc(p.l) + '" target="_blank" rel="noopener" data-perfil>Currículo Lattes <span aria-hidden="true">&#8599;</span></a>' +
				'<button type="button" class="gemec-est-ficha-fechar" aria-label="Fechar">&times;</button></div></header>' +
				htmlNums(partes.nums) + htmlAbas(partes.abas, ativa) +
				'<div class="gemec-est-ficha-corpo">' + (partes.abas.length ? htmlPaineis(partes, ativa) : '<p class="gemec-est-vazio">Nenhum item no Lattes deste membro.</p>') + '</div>';
			caixa.scrollTop = 0;
		});
	}

	// Perfil do membro: Sobre (sempre visivel, fora das abas) e Publicacoes vem
	// do servidor; aqui entram, abaixo do Sobre, os numeros e as abas.
	// #publicacoes no endereco rola ate essa aba.
	if (proprio >= 0) {
		quandoProntos(function (d) {
			var sobre = raiz.querySelector(':scope > [data-painel="sobre"]');
			var servidor = [].slice.call(raiz.querySelectorAll(':scope > .gemec-est-ficha-painel:not([data-painel="sobre"])'));
			var pubs = raiz.querySelector('[data-painel="publicacoes"]');
			var partes = partesFicha(d, proprio, true, pubs ? +pubs.getAttribute('data-n') : 0);
			var abas = servidor.map(function (el) { return [el.getAttribute('data-painel'), el.getAttribute('data-rot'), el.hasAttribute('data-n') ? +el.getAttribute('data-n') : '']; }).concat(partes.abas);
			if (!abas.length) { return; }
			var ativa = abas[0][0];
			var corpo = document.createElement('div');
			corpo.className = 'gemec-est-ficha-corpo';
			servidor.forEach(function (el) { el.setAttribute('role', 'tabpanel'); corpo.appendChild(el); });
			corpo.insertAdjacentHTML('beforeend', htmlPaineis(partes, ativa));
			var topo = document.createElement('div');
			topo.className = 'gemec-perfil-abas-topo';
			var antigo = raiz.querySelector('h2#publicacoes'); // o ancora passa para o topo das abas
			if (antigo) { antigo.removeAttribute('id'); }
			topo.id = 'publicacoes';
			topo.innerHTML = htmlNums(partes.nums) + htmlAbas(abas, ativa);
			if (sobre) { sobre.classList.remove('gemec-est-ficha-painel'); sobre.classList.add('gemec-perfil-sobre'); }
			raiz.appendChild(topo);
			raiz.appendChild(corpo);
			raiz.classList.add('gemec-perfil-com-abas');
			mostrarAba(raiz, ativa);
			if (/^#publicacoes/.test(location.hash)) { topo.scrollIntoView({ block: 'start' }); }
		});
	}

	// Nomes de membros na pagina (tabela, listas, premios, graficos) abrem a ficha.
	raiz.addEventListener('click', function (ev) {
		var a = ev.target.closest('a[data-ficha], a[href]');
		if (!a || a.hasAttribute('data-perfil') || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button) { return; }
		var i = a.hasAttribute('data-ficha') ? +a.getAttribute('data-ficha') : porUrl[a.href.replace(/\/$/, '')];
		if (i === undefined || isNaN(i) || i === proprio) { return; }
		ev.preventDefault();
		abrirFicha(i);
	});

	// Botoes com filtro pronto (ex.: niveis das orientacoes).
	raiz.addEventListener('click', function (ev) {
		var b = ev.target.closest('[data-filtro]');
		if (!b) { return; }
		var f = JSON.parse(b.getAttribute('data-filtro'));
		var k = f.lista;
		delete f.lista;
		quandoProntos(function () { if (listas[k]) { listas[k](f); } });
	});

	/* ----------------------------------------------------- tabela de membros */
	raiz.querySelectorAll('[data-gemec-tabela]').forEach(function (caixa) {
		var tab = caixa.querySelector('table');
		var corpo = tab.tBodies[0];
		var VISOES = [['producao', 'Produção'], ['orientacoes', 'Orientações'], ['projetos', 'Projetos, prêmios e eventos'], ['perfil', 'Perfil']];
		var ferr = document.createElement('div');
		ferr.className = 'gemec-est-barra-ferr';
		ferr.innerHTML = '<label class="gemec-est-busca"><span class="screen-reader-text">Buscar membro</span><input type="search" placeholder="Buscar membro" autocomplete="off"></label>' +
			'<div class="gemec-est-seg" role="group" aria-label="Colunas">' + VISOES.map(function (v, i) {
				return '<button type="button" data-v="' + v[0] + '" aria-pressed="' + (i ? 'false' : 'true') + '">' + v[1] + '</button>';
			}).join('') + '</div>';
		caixa.insertBefore(ferr, caixa.firstChild);
		tab.setAttribute('data-vista', 'producao');
		ferr.querySelector('.gemec-est-seg').addEventListener('click', function (ev) {
			var bt = ev.target.closest('button');
			if (!bt) { return; }
			this.querySelectorAll('button').forEach(function (b) { b.setAttribute('aria-pressed', b === bt ? 'true' : 'false'); });
			tab.setAttribute('data-vista', bt.getAttribute('data-v'));
		});
		ferr.querySelector('input').addEventListener('input', function () {
			var q = normal(this.value.trim());
			[].forEach.call(corpo.rows, function (tr) { tr.hidden = q !== '' && normal(tr.cells[0].textContent).indexOf(q) < 0; });
		});
		var ths = [].slice.call(tab.tHead.rows[0].cells);
		ths.forEach(function (th, col) {
			if (!th.hasAttribute('data-ord')) { return; }
			var bt = document.createElement('button');
			bt.type = 'button';
			bt.className = 'gemec-est-ord';
			while (th.firstChild) { bt.appendChild(th.firstChild); }
			th.appendChild(bt);
			bt.addEventListener('click', function () {
				var num = th.getAttribute('data-ord') === 'n';
				var desc = th.getAttribute('aria-sort') ? th.getAttribute('aria-sort') === 'ascending' : num;
				ths.forEach(function (o) { o.removeAttribute('aria-sort'); });
				th.setAttribute('aria-sort', desc ? 'descending' : 'ascending');
				var linhas = [].slice.call(corpo.rows);
				function valor(tr) {
					var c = tr.cells[col];
					return num ? +(c.getAttribute('data-v') || c.textContent) : normal(c.textContent.trim());
				}
				linhas.sort(function (a, b) {
					var x = valor(a), y = valor(b);
					var r = num ? x - y : String(x).localeCompare(String(y), 'pt-BR');
					return desc ? -r : r;
				});
				linhas.forEach(function (tr) { corpo.appendChild(tr); });
			});
		});
	});

	/* ------------------------------------------- grafo de colaboracoes */
	raiz.querySelectorAll('[data-gemec-grafo]').forEach(function (caixa) {
		var d3 = window.d3;
		if (!d3) { return; }
		var g = JSON.parse(caixa.querySelector('script[type="application/json"]').textContent);
		var tela = caixa.querySelector('.gemec-est-grafo-tela');
		var painel = caixa.querySelector('.gemec-est-grafo-painel');
		var dicaInicial = painel.innerHTML;
		var viz = {};
		var nos = g.nos.map(function (n) { viz[n.i] = []; return { id: n.i, g: n.g, nome: membros[n.i] ? membros[n.i].n : '' }; });
		var arestas = g.arestas.map(function (e) { viz[e[0]].push([e[1], e[2]]); viz[e[1]].push([e[0], e[2]]); return { source: e[0], target: e[1], w: e[2] }; });
		var wmax = d3.max(arestas, function (e) { return e.w; }) || 1;
		var gmax = d3.max(nos, function (n) { return viz[n.id].length; }) || 1;
		var raio = function (n) { return 7 + 13 * Math.sqrt(viz[n.id].length / gmax); };

		// Barra: busca, rotulos e zoom.
		var ferr = document.createElement('div');
		ferr.className = 'gemec-est-barra-ferr gemec-est-grafo-ferr';
		ferr.innerHTML = '<label class="gemec-est-busca"><span class="screen-reader-text">Buscar membro no grafo</span><input type="search" list="gemec-est-grafo-nomes" placeholder="Buscar membro no grafo" autocomplete="off"></label>' +
			'<datalist id="gemec-est-grafo-nomes">' + nos.map(function (n) { return '<option value="' + esc(n.nome) + '">'; }).join('') + '</datalist>' +
			'<div class="gemec-est-seg"><button type="button" data-acao="rotulos" aria-pressed="true">Rótulos</button></div>' +
			'<div class="gemec-est-seg"><button type="button" data-acao="menos" aria-label="Diminuir zoom">&minus;</button><button type="button" data-acao="mais" aria-label="Aumentar zoom">+</button>' +
			'<button type="button" data-acao="centro">Centralizar</button></div>';
		caixa.insertBefore(ferr, caixa.firstChild);

		var W = tela.clientWidth || 800, H = W < 640 ? 440 : 600;
		var sim = d3.forceSimulation(nos)
			.force('link', d3.forceLink(arestas).id(function (n) { return n.id; }).distance(function (e) { return 90 + 160 / Math.sqrt(e.w); }).strength(function (e) { return 0.25 + 0.5 * e.w / wmax; }))
			.force('carga', d3.forceManyBody().strength(-480))
			.force('centro', d3.forceCenter(W / 2, H / 2))
			// quem nao tem coautoria no grupo fica perto do nucleo, sem espalhar o grafo
			.force('x', d3.forceX(W / 2).strength(function (n) { return viz[n.id].length ? 0.06 : 0.35; }))
			.force('y', d3.forceY(H / 2).strength(function (n) { return viz[n.id].length ? 0.08 : 0.45; }))
			.force('colisao', d3.forceCollide().radius(function (n) { return raio(n) + 6; }))
			.stop();
		for (var t = 0; t < 320; t++) { sim.tick(); }

		var svg = d3.select(tela).append('svg').attr('width', '100%').attr('height', H).attr('viewBox', '0 0 ' + W + ' ' + H).attr('class', 'gemec-est-grafo-svg');
		var mundo = svg.append('g');
		var linhas = mundo.append('g').selectAll('line').data(arestas).join('line')
			.attr('class', 'gemec-est-grafo-l').attr('stroke-width', function (e) { return (1 + 6 * Math.sqrt(e.w / wmax)).toFixed(2); });
		var marcas = mundo.append('g').selectAll('g').data(nos).join('g').attr('class', 'gemec-est-grafo-no').attr('tabindex', 0)
			.attr('role', 'button').attr('aria-label', function (n) { return n.nome + ': ' + viz[n.id].length + ' coautores no grupo'; });
		marcas.append('circle').attr('r', raio).attr('class', function (n) { return 'gemec-est-' + n.g; });
		marcas.append('text').attr('dy', function (n) { return raio(n) + 13; }).attr('text-anchor', 'middle').text(function (n) { return curto(n.nome); });

		function posicionar() {
			linhas.attr('x1', function (e) { return e.source.x; }).attr('y1', function (e) { return e.source.y; })
				.attr('x2', function (e) { return e.target.x; }).attr('y2', function (e) { return e.target.y; });
			marcas.attr('transform', function (n) { return 'translate(' + n.x + ',' + n.y + ')'; });
		}
		posicionar();
		sim.on('tick', posicionar);

		var zoom = d3.zoom().scaleExtent([0.3, 4])
			.filter(function (ev) { return ev.type === 'wheel' ? (ev.ctrlKey || ev.metaKey) : !ev.button; })
			.on('zoom', function (ev) { mundo.attr('transform', ev.transform); });
		svg.call(zoom).on('dblclick.zoom', null);
		svg.style('touch-action', 'pan-y');
		function enquadrar(animar) {
			var x0 = d3.min(nos, function (n) { return n.x - raio(n); }), x1 = d3.max(nos, function (n) { return n.x + raio(n); });
			var y0 = d3.min(nos, function (n) { return n.y - raio(n); }), y1 = d3.max(nos, function (n) { return n.y + raio(n) + 18; });
			var k = Math.min(2, 0.92 * Math.min(W / (x1 - x0), H / (y1 - y0)));
			var tr = d3.zoomIdentity.translate(W / 2, H / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
			(animar ? svg.transition().duration(450) : svg).call(zoom.transform, tr);
		}
		enquadrar(false);

		marcas.call(d3.drag()
			.on('start', function (ev, n) { if (!ev.active) { sim.alphaTarget(0.2).restart(); } n.fx = n.x; n.fy = n.y; })
			.on('drag', function (ev, n) { n.fx = ev.x; n.fy = ev.y; })
			.on('end', function (ev, n) { if (!ev.active) { sim.alphaTarget(0); } n.fx = null; n.fy = null; }));

		var atual = null;
		function selecionar(id, centrar) {
			atual = id;
			var lig = {};
			lig[id] = true;
			viz[id].forEach(function (v) { lig[v[0]] = true; });
			svg.classed('gemec-est-grafo-foco', true);
			marcas.classed('gemec-est-on', function (n) { return !!lig[n.id]; }).classed('gemec-est-sel', function (n) { return n.id === id; });
			linhas.classed('gemec-est-on', function (e) { return e.source.id === id || e.target.id === id; });
			var p = membros[id] || {};
			var par = viz[id].slice().sort(function (a, b) { return b[1] - a[1]; });
			painel.innerHTML = '<p class="gemec-est-sobre">' + esc(p.cat || '') + '</p><h4>' + esc(p.n) + '</h4>' +
				'<p class="gemec-est-grafo-meta">' + (p.ar ? esc(p.ar) + '<br>' : '') + (p.at ? 'Lattes atualizado em ' + esc(p.at) : '') + '</p>' +
				'<p class="gemec-est-grafo-n"><b>' + fmt(par.length) + '</b> ' + (par.length === 1 ? 'coautor' : 'coautores') + ' no grupo</p>' +
				(par.length ? '<ol class="gemec-est-grafo-viz">' + par.map(function (v) {
					return '<li><button type="button" data-sel="' + v[0] + '"><span>' + esc(membros[v[0]] ? membros[v[0]].n : '') + '</span><b>' + fmt(v[1]) + '</b></button></li>';
				}).join('') + '</ol>' : '<p class="gemec-est-grafo-meta">Sem coautoria registrada com outros membros.</p>') +
				'<div class="gemec-est-grafo-acoes"><button type="button" class="gemec-est-bt" data-abrir="' + id + '">Abrir ficha completa</button>' +
				(p.u ? '<a class="gemec-est-bt gemec-est-bt-claro" href="' + esc(p.u) + '" data-perfil>Perfil no site</a>' : '') + '</div>';
			if (centrar) {
				var n = nos.filter(function (x) { return x.id === id; })[0];
				var k = Math.max(d3.zoomTransform(svg.node()).k, 1.3);
				svg.transition().duration(450).call(zoom.transform, d3.zoomIdentity.translate(W / 2, H / 2).scale(k).translate(-n.x, -n.y));
			}
		}
		function limpar() {
			atual = null;
			svg.classed('gemec-est-grafo-foco', false);
			marcas.classed('gemec-est-on gemec-est-sel', false);
			linhas.classed('gemec-est-on', false);
			painel.innerHTML = dicaInicial;
		}
		marcas.on('click', function (ev, n) { ev.stopPropagation(); selecionar(n.id); })
			.on('keydown', function (ev, n) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); selecionar(n.id); } });
		svg.on('click', function () { if (atual !== null) { limpar(); } });
		painel.addEventListener('click', function (ev) {
			var b = ev.target.closest('[data-sel]');
			if (b) { selecionar(+b.getAttribute('data-sel'), true); return; }
			var f = ev.target.closest('[data-abrir]');
			if (f) { abrirFicha(+f.getAttribute('data-abrir'), 'colab'); }
		});
		var rotulos = true;
		ferr.addEventListener('click', function (ev) {
			var b = ev.target.closest('[data-acao]');
			if (!b) { return; }
			var a = b.getAttribute('data-acao');
			if (a === 'rotulos') {
				rotulos = !rotulos;
				b.setAttribute('aria-pressed', rotulos ? 'true' : 'false');
				svg.classed('gemec-est-grafo-sem-rotulos', !rotulos);
			} else if (a === 'mais' || a === 'menos') {
				svg.transition().duration(250).call(zoom.scaleBy, a === 'mais' ? 1.4 : 1 / 1.4);
			} else {
				enquadrar(true);
			}
		});
		var busca = ferr.querySelector('input');
		function buscar() {
			var q = normal(busca.value.trim());
			if (!q) { return; }
			var n = nos.filter(function (x) { return normal(x.nome) === q; })[0] || nos.filter(function (x) { return normal(x.nome).indexOf(q) >= 0; })[0];
			if (n) { selecionar(n.id, true); }
		}
		busca.addEventListener('change', buscar);
		busca.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { ev.preventDefault(); buscar(); } });
	});
})();
