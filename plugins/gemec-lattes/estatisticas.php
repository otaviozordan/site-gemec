<?php
/**
 * Secoes do Relatorio Lattes na pagina Estatisticas ([gemec_estatisticas]).
 *
 * scripts/lattes/relatorio_json.py gera, a partir do relatorio do scriptLattes:
 *   relatorio.json  contagens, membros com metricas, premios e grafo (lido aqui)
 *   listas.json     todos os itens, com os membros de cada um; o navegador o
 *                   baixa comprimido de ?gemec_lattes_listas=<versao> e
 *                   estatisticas.js monta as listas com busca e filtros
 * Os graficos usam as pecas de gemec-core/estatisticas.php.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

function gemec_lattes_relatorio() {
	static $d = null;
	if ( null === $d ) {
		$arq = __DIR__ . '/relatorio.json';
		$d   = is_readable( $arq ) ? json_decode( (string) file_get_contents( $arq ), true ) : array();
		$d   = is_array( $d ) && isset( $d['membros'] ) ? $d : array();
	}
	return $d;
}

/** ID Lattes => array( url do perfil, categoria, nome no site ), dos membros publicados. */
function gemec_lattes_perfis() {
	static $out = null;
	if ( null === $out ) {
		$out = array();
		foreach ( gemec_lattes_mapa_membros() as $lid => $id ) {
			$out[ $lid ] = array( get_permalink( $id ), function_exists( 'gemec_categoria_de' ) ? gemec_categoria_de( $id ) : '', get_the_title( $id ) );
		}
	}
	return $out;
}

/** Primeiro e ultimo nome (ex.: 'Guilherme Gomes'), para rotulos curtos. */
function gemec_lattes_curto( $nome ) {
	$p = preg_split( '/\s+/', trim( $nome ) );
	return count( $p ) > 1 ? $p[0] . ' ' . end( $p ) : $nome;
}

/** Lista montada pelo navegador (estatisticas.js) a partir de listas.json. */
function gemec_lattes_lista( $chave, $titulo, $sub = '' ) {
	return gemec_est_bloco(
		$titulo,
		$sub,
		'<div class="gemec-est-lista" data-lista="' . esc_attr( $chave ) . '"><p class="gemec-est-carrega">Carregando a lista&hellip;</p>'
			. '<noscript><p>A lista completa precisa de JavaScript.</p></noscript></div>',
		'gemec-est-bloco-lista'
	);
}

/** Series s1..s5 a partir de uma lista de tipos ([k, rot, n]); do quinto em diante vira "Outros tipos". */
function gemec_lattes_series_tipos( $tipos, &$mapa ) {
	usort( $tipos, function ( $a, $b ) {
		return $b['n'] - $a['n'];
	} );
	$series = array();
	$mapa   = array();
	foreach ( $tipos as $i => $t ) {
		$s               = 's' . min( $i + 1, 5 );
		$mapa[ $t['k'] ] = $s;
		$series[ $s ]    = $i < 4 || count( $tipos ) === 5 ? esc_html( $t['rot'] ) : 'Outros tipos';
	}
	return $series;
}

/** ano => [chave => n] com as chaves trocadas pelas series de $mapa. */
function gemec_lattes_remapear( $anos, $mapa ) {
	$out = array();
	foreach ( (array) $anos as $a => $c ) {
		foreach ( $c as $k => $n ) {
			$s                     = isset( $mapa[ $k ] ) ? $mapa[ $k ] : 's5';
			$out[ (int) $a ][ $s ] = ( isset( $out[ (int) $a ][ $s ] ) ? $out[ (int) $a ][ $s ] : 0 ) + $n;
		}
	}
	return $out;
}

/* ---------------------------------------------------------------- secoes */

function gemec_lattes_sec_orientacoes( $d ) {
	$o = $d['orientacoes'];
	if ( empty( $o['n'] ) ) {
		return null;
	}
	$niveis = array(
		'posdoc'         => 'P&oacute;s-doutorado',
		'doutorado'      => 'Doutorado',
		'mestrado'       => 'Mestrado',
		'especializacao' => 'Especializa&ccedil;&atilde;o',
		'tcc'            => 'TCC',
		'ic'             => 'Inicia&ccedil;&atilde;o cient&iacute;fica',
		'outra'          => 'Outra natureza',
	);
	$n = function ( $t, $s ) use ( $o ) {
		return isset( $o['conta'][ $t ][ $s ] ) ? (int) $o['conta'][ $t ][ $s ] : 0;
	};
	$tot = array( 'c' => 0, 'a' => 0 );
	foreach ( array_keys( $niveis ) as $k ) {
		$tot['c'] += $n( $k, 'c' );
		$tot['a'] += $n( $k, 'a' );
	}

	$h = gemec_est_numeros( array(
		array( $tot['c'], 'orienta&ccedil;&otilde;es conclu&iacute;das' ),
		array( $tot['a'], 'em andamento', (int) $n( 'doutorado', 'a' ) . ' doutorados e ' . (int) $n( 'mestrado', 'a' ) . ' mestrados' ),
		array( $n( 'doutorado', 'c' ), 'teses de doutorado' ),
		array( $n( 'mestrado', 'c' ), 'disserta&ccedil;&otilde;es de mestrado' ),
	) );

	$c = '<div class="gemec-est-niveis">';
	foreach ( $niveis as $k => $r ) {
		if ( $n( $k, 'c' ) || $n( $k, 'a' ) ) {
			$c .= '<button type="button" class="gemec-est-nivel" data-filtro="' . esc_attr( wp_json_encode( array( 'lista' => 'orientacoes', 't' => $k ) ) ) . '"><span class="gemec-est-nivel-r">' . $r . '</span><span class="gemec-est-nivel-n">' . (int) $n( $k, 'c' ) . '</span>'
				. '<span class="gemec-est-nivel-a">' . ( $n( $k, 'a' ) ? '+' . (int) $n( $k, 'a' ) . ' em andamento' : 'conclu&iacute;das' ) . '</span></button>';
		}
	}
	$c .= '</div>';

	$series = array( 's1' => 'Doutorado e p&oacute;s-doc', 's2' => 'Mestrado', 's3' => 'Inicia&ccedil;&atilde;o cient&iacute;fica', 's4' => 'TCC', 's5' => 'Especializa&ccedil;&atilde;o e outras' );
	$grupo  = array( 'posdoc' => 's1', 'doutorado' => 's1', 'mestrado' => 's2', 'ic' => 's3', 'tcc' => 's4', 'especializacao' => 's5', 'outra' => 's5' );
	$h     .= gemec_est_grade( array(
		gemec_est_bloco( 'Por n&iacute;vel', 'Clique em um n&iacute;vel para ver as orienta&ccedil;&otilde;es.', $c ),
		gemec_est_bloco( 'Conclu&iacute;das por ano', 'No ano de conclus&atilde;o, por n&iacute;vel. Clique em um ano para ver a lista.', gemec_est_colunas( 'ori-anos', $series, gemec_lattes_remapear( $o['anos'], $grupo ), 'Gráfico de colunas empilhadas: orientações concluídas por ano e nível.', true ) ),
	), '2-3' );
	$h .= gemec_lattes_lista( 'orientacoes', 'Todas as orienta&ccedil;&otilde;es', 'Filtre por situa&ccedil;&atilde;o, n&iacute;vel ou orientador, ou busque por aluno, t&iacute;tulo, curso e ag&ecirc;ncia.' );

	return array(
		'titulo' => 'Orienta&ccedil;&otilde;es',
		'sobre'  => 'Forma&ccedil;&atilde;o de pessoas',
		'lead'   => 'Supervis&otilde;es de p&oacute;s-doutorado, teses, disserta&ccedil;&otilde;es, TCCs e inicia&ccedil;&otilde;es cient&iacute;ficas orientadas ou coorientadas pelos membros.',
		'html'   => $h,
		'kpi'    => array( array( 'n' => $tot['c'], 'rot' => 'orienta&ccedil;&otilde;es conclu&iacute;das', 'nota' => '+' . (int) $tot['a'] . ' em andamento', 'serie' => gemec_est_totais( $o['anos'] ) ) ),
	);
}

function gemec_lattes_sec_projetos( $d ) {
	$p = $d['projetos'];
	if ( empty( $p['n'] ) ) {
		return null;
	}
	$h  = gemec_est_numeros( array(
		array( $p['n'], 'projetos de pesquisa' ),
		array( $p['andamento'], 'em andamento' ),
		array( $p['n'] - $p['andamento'], 'conclu&iacute;dos' ),
	) );
	$h .= gemec_est_bloco( 'Projetos iniciados por ano', 'Pelo ano de in&iacute;cio informado no Lattes.', gemec_est_colunas( 'pj-anos', array( 's1' => 'Projetos iniciados' ), $p['anos'], 'Gráfico de colunas: projetos de pesquisa iniciados por ano.', true ) );
	$h .= gemec_lattes_lista( 'projetos', 'Todos os projetos', 'Em andamento primeiro. Filtre por situa&ccedil;&atilde;o ou membro, ou busque por tema.' );
	return array(
		'titulo' => 'Projetos de pesquisa',
		'menu'   => 'Projetos',
		'sobre'  => 'Pesquisa',
		'lead'   => 'Projetos coordenados pelos membros ou de que participam, com equipe, per&iacute;odo e resumo.',
		'html'   => $h,
		'kpi'    => array( array( 'n' => $p['n'], 'rot' => 'projetos de pesquisa', 'serie' => gemec_est_totais( $p['anos'] ), 'nota' => (int) $p['andamento'] . ' em andamento' ) ),
	);
}

function gemec_lattes_sec_tecnica( $d ) {
	$t = $d['tecnica'];
	$a = $d['artistica'];
	if ( empty( $t['n'] ) && empty( $a['n'] ) ) {
		return null;
	}
	$nums  = array( array( $t['n'], 'produ&ccedil;&otilde;es t&eacute;cnicas' ) );
	$tipos = $t['tipos'];
	usort( $tipos, function ( $x, $y ) {
		return $y['n'] - $x['n'];
	} );
	foreach ( array_slice( $tipos, 0, 2 ) as $x ) {
		$nums[] = array( $x['n'], esc_html( mb_strtolower( $x['rot'] ) ) );
	}
	$nums[] = array( $a['n'], 'produ&ccedil;&otilde;es art&iacute;sticas' );
	$h      = gemec_est_numeros( $nums );

	$linhas = array();
	foreach ( $tipos as $x ) {
		$linhas[] = array( $x['rot'], $x['n'] );
	}
	$mapa = array();
	$ser  = gemec_lattes_series_tipos( $t['tipos'], $mapa );
	$h   .= gemec_est_grade( array(
		gemec_est_bloco( 'Por tipo', '', gemec_est_barras( 'pt-tipos', array( 'Tipo', 'Produ&ccedil;&otilde;es' ), $linhas, 'Gráfico de barras: produção técnica por tipo.', 's1', true ) ),
		gemec_est_bloco( 'Por ano', 'Por tipo.', gemec_est_colunas( 'pt-anos', $ser, gemec_lattes_remapear( $t['anos'], $mapa ), 'Gráfico de colunas empilhadas: produção técnica por ano e tipo.', true ) ),
	) );
	if ( $t['n'] ) {
		$h .= gemec_lattes_lista( 'tecnica', 'Toda a produ&ccedil;&atilde;o t&eacute;cnica', 'Programas de computador, produtos, trabalhos t&eacute;cnicos, entrevistas e outros.' );
	}
	if ( $a['n'] ) {
		$h .= gemec_lattes_lista( 'artistica', 'Produ&ccedil;&atilde;o art&iacute;stica', '' );
	} else {
		$h .= '<p class="gemec-est-nota">Nenhuma produ&ccedil;&atilde;o art&iacute;stica registrada nos curr&iacute;culos.</p>';
	}
	return array(
		'titulo' => 'Produ&ccedil;&atilde;o t&eacute;cnica e art&iacute;stica',
		'menu'   => 'Produ&ccedil;&atilde;o t&eacute;cnica',
		'sobre'  => 'Tecnologia e extens&atilde;o',
		'lead'   => 'Softwares, produtos tecnol&oacute;gicos, pareceres, relat&oacute;rios, cursos e participa&ccedil;&otilde;es na m&iacute;dia registrados no Lattes.',
		'html'   => $h,
		'kpi'    => array( array( 'n' => $t['n'], 'rot' => 'produ&ccedil;&otilde;es t&eacute;cnicas', 'serie' => gemec_est_totais( $t['anos'] ) ) ),
	);
}

function gemec_lattes_sec_eventos( $d ) {
	$e = $d['eventos'];
	if ( empty( $e['part'] ) && empty( $e['org'] ) ) {
		return null;
	}
	$tipos = (array) $e['tipos'];
	arsort( $tipos );
	$h      = gemec_est_numeros( array(
		array( $e['part'], 'participa&ccedil;&otilde;es em eventos' ),
		array( isset( $tipos['Congresso'] ) ? $tipos['Congresso'] : 0, 'em congressos' ),
		array( $e['org'], 'eventos organizados' ),
	) );
	$linhas = array();
	foreach ( $tipos as $k => $v ) {
		$linhas[] = array( $k, $v );
	}
	$h .= gemec_est_grade( array(
		gemec_est_bloco( 'Por ano', 'Participa&ccedil;&otilde;es e organiza&ccedil;&otilde;es.', gemec_est_colunas( 'ev-anos', array( 's1' => 'Participa&ccedil;&atilde;o', 's2' => 'Organiza&ccedil;&atilde;o' ), $e['anos'], 'Gráfico de colunas empilhadas: participação e organização de eventos por ano.', true ) ),
		gemec_est_bloco( 'Participa&ccedil;&otilde;es por tipo de evento', '', gemec_est_barras( 'ev-tipos', array( 'Tipo de evento', 'Participa&ccedil;&otilde;es' ), $linhas, 'Gráfico de barras: participações por tipo de evento.', 's1', true ) ),
	), '3-2' );
	$h .= gemec_lattes_lista( 'eventos', 'Todos os eventos', 'Congressos, simp&oacute;sios, semin&aacute;rios e outros, com o trabalho apresentado.' );
	return array(
		'titulo' => 'Eventos',
		'sobre'  => 'Divulga&ccedil;&atilde;o',
		'lead'   => 'Participa&ccedil;&atilde;o dos membros em congressos e outros eventos, e os eventos que organizaram.',
		'html'   => $h,
		'kpi'    => array( array( 'n' => $e['part'] + $e['org'], 'rot' => 'participa&ccedil;&otilde;es e organiza&ccedil;&otilde;es de eventos', 'serie' => gemec_est_totais( $e['anos'] ) ) ),
	);
}

function gemec_lattes_sec_premios( $d ) {
	if ( empty( $d['premios'] ) ) {
		return null;
	}
	$perfis = gemec_lattes_perfis();
	$pos    = array_flip( wp_list_pluck( $d['membros'], 'lattes' ) );
	$h      = '<ol class="gemec-est-premios">';
	foreach ( $d['premios'] as $p ) {
		$quem = array();
		foreach ( $p['lattes'] as $lid ) {
			if ( isset( $perfis[ $lid ] ) ) {
				$quem[] = '<a href="' . esc_url( $perfis[ $lid ][0] ) . '"' . ( isset( $pos[ $lid ] ) ? ' data-ficha="' . (int) $pos[ $lid ] . '"' : '' ) . '>' . esc_html( $perfis[ $lid ][2] ) . '</a>';
			}
		}
		$h .= '<li class="gemec-est-premio"><span class="gemec-est-premio-ano">' . ( $p['ano'] ? (int) $p['ano'] : '&ndash;' ) . '</span><div><p class="gemec-est-item-t">' . esc_html( $p['desc'] ) . '</p>'
			. ( $quem ? '<p class="gemec-est-item-m">' . implode( ', ', $quem ) . '</p>' : '' ) . '</div></li>';
	}
	$h .= '</ol>';
	return array(
		'titulo' => 'Pr&ecirc;mios e t&iacute;tulos',
		'menu'   => 'Pr&ecirc;mios',
		'sobre'  => 'Reconhecimento',
		'lead'   => count( $d['premios'] ) . ' pr&ecirc;mios e t&iacute;tulos recebidos pelos membros, do mais recente para o mais antigo.',
		'html'   => $h,
		'kpi'    => array( array( 'n' => count( $d['premios'] ), 'rot' => 'pr&ecirc;mios e t&iacute;tulos' ) ),
	);
}

function gemec_lattes_sec_membros( $d ) {
	$ms = $d['membros'];
	if ( ! $ms ) {
		return null;
	}
	$perfis = gemec_lattes_perfis();
	$hoje   = new DateTime( 'now', wp_timezone() );
	$bolsas = 0;
	$recent = 0;
	$areas  = array();
	foreach ( $ms as $m ) {
		$bolsas += '' !== $m['bolsa'];
		$dt      = DateTime::createFromFormat( 'd/m/Y', $m['atualizacao'] );
		$recent += $dt && $dt->diff( $hoje )->days <= 365;
		if ( $m['area'] ) {
			$areas[ $m['area'] ] = true;
		}
	}
	$h = gemec_est_numeros( array(
		array( count( $ms ), 'curr&iacute;culos Lattes' ),
		array( $bolsas, 'bolsistas de produtividade do CNPq' ),
		array( $recent, 'atualizados nos &uacute;ltimos 12 meses' ),
		array( count( $areas ), '&aacute;reas do conhecimento' ),
	) );

	// Colunas de metricas: [rotulo, grupo, campo de met].
	$cols = array(
		array( 'Peri&oacute;dicos', 'producao', 'periodicos' ),
		array( 'Livros', 'producao', 'livros' ),
		array( 'Cap&iacute;tulos', 'producao', 'capitulos' ),
		array( 'Congressos', 'producao', 'congressos' ),
		array( 'Resumos', 'producao', 'resumos' ),
		array( 'Aceitos', 'producao', 'aceitos' ),
		array( 'Total bibliogr&aacute;fico', 'producao', 'pb' ),
		array( 'T&eacute;cnica', 'producao', 'tec' ),
		array( 'P&oacute;s-doc', 'orientacoes', 'oc_posdoc' ),
		array( 'Doutorado', 'orientacoes', 'oc_dout' ),
		array( 'Mestrado', 'orientacoes', 'oc_mest' ),
		array( 'Especializa&ccedil;&atilde;o', 'orientacoes', 'oc_espec' ),
		array( 'TCC', 'orientacoes', 'oc_tcc' ),
		array( 'IC', 'orientacoes', 'oc_ic' ),
		array( 'Total conclu&iacute;das', 'orientacoes', 'oc' ),
		array( 'Em andamento', 'orientacoes', 'oa' ),
		array( 'Projetos', 'projetos', 'projetos' ),
		array( 'Pr&ecirc;mios', 'projetos', 'premios' ),
		array( 'Participa&ccedil;&otilde;es em eventos', 'projetos', 'ev_part' ),
		array( 'Eventos organizados', 'projetos', 'ev_org' ),
	);
	$t  = '<div class="gemec-est-tabela" data-gemec-tabela><div class="gemec-est-rolagem"><table class="gemec-est-mt"><thead><tr>';
	$t .= '<th scope="col" data-ord="t">Membro</th><th scope="col" data-g="perfil" data-ord="t">Grupo no relat&oacute;rio</th><th scope="col" data-g="perfil" data-ord="t">&Aacute;rea</th>'
		. '<th scope="col" data-g="perfil" data-ord="t">Bolsa CNPq</th><th scope="col" data-g="perfil" data-ord="n">Lattes atualizado em</th>';
	foreach ( $cols as $c ) {
		$t .= '<th scope="col" data-g="' . $c[1] . '" data-ord="n">' . $c[0] . '</th>';
	}
	$t .= '</tr></thead><tbody>';
	foreach ( $ms as $i => $m ) {
		$p     = isset( $perfis[ $m['lattes'] ] ) ? $perfis[ $m['lattes'] ] : null;
		$nome  = '<a href="' . esc_url( $p ? $p[0] : 'http://lattes.cnpq.br/' . $m['lattes'] ) . '" data-ficha="' . (int) $i . '">' . esc_html( $p ? $p[2] : $m['nome'] ) . '</a>';
		$dt    = DateTime::createFromFormat( 'd/m/Y', $m['atualizacao'] );
		$velho = $dt && $dt->diff( $hoje )->days > 365;
		$t    .= '<tr><th scope="row"><span class="gemec-est-mt-nome">' . $nome . '</span> <a class="gemec-est-mt-lattes" href="' . esc_url( 'http://lattes.cnpq.br/' . $m['lattes'] ) . '" target="_blank" rel="noopener" title="Curr&iacute;culo Lattes">Lattes</a></th>'
			. '<td data-g="perfil">' . esc_html( $m['rotulo'] ) . '</td><td data-g="perfil">' . esc_html( $m['area'] ) . '</td><td data-g="perfil">' . esc_html( $m['bolsa'] ) . '</td>'
			. '<td data-g="perfil" data-v="' . ( $dt ? esc_attr( $dt->format( 'Ymd' ) ) : '0' ) . '">' . esc_html( $m['atualizacao'] ) . ( $velho ? ' <span class="gemec-est-etq gemec-est-etq-and">h&aacute; mais de 1 ano</span>' : '' ) . '</td>';
		foreach ( $cols as $c ) {
			$v  = isset( $m['met'][ $c[2] ] ) ? (int) $m['met'][ $c[2] ] : 0;
			$t .= '<td data-g="' . $c[1] . '"' . ( $v ? '' : ' class="gemec-est-zero"' ) . '>' . $v . '</td>';
		}
		$t .= '</tr>';
	}
	$t .= '</tbody></table></div></div>';
	$h .= gemec_est_bloco( 'M&eacute;tricas por membro', 'Clique em um nome para abrir a ficha do membro, com toda a produ&ccedil;&atilde;o e as colabora&ccedil;&otilde;es, ou no cabe&ccedil;alho de uma coluna para ordenar.', $t, 'gemec-est-bloco-tabela' );

	return array(
		'titulo' => 'Membros',
		'sobre'  => 'Equipe',
		'lead'   => 'Os curr&iacute;culos do relat&oacute;rio, com &aacute;rea, bolsa de produtividade, data da &uacute;ltima atualiza&ccedil;&atilde;o e a produ&ccedil;&atilde;o de cada um.',
		'html'   => $h,
		'kpi'    => array( array( 'n' => count( $ms ), 'rot' => 'curr&iacute;culos Lattes no relat&oacute;rio', 'nota' => $bolsas . ' bolsistas de produtividade' ) ),
	);
}

function gemec_lattes_sec_colaboracao( $d ) {
	$g = $d['grafo'];
	if ( empty( $g['arestas'] ) ) {
		return null;
	}
	$perfis = gemec_lattes_perfis();
	$grupo  = array( 'professor' => 's1', 'visitante' => 's1', 'posdoc' => 's2', 'doutorado' => 's2', 'mestrado' => 's2', 'graduacao' => 's3', 'egresso' => 's4' );
	$series = array( 's1' => 'Professores e visitantes', 's2' => 'P&oacute;s-gradua&ccedil;&atilde;o', 's3' => 'Gradua&ccedil;&atilde;o', 's4' => 'Egressos' );
	$grau   = array();
	$soma   = 0;
	foreach ( $g['arestas'] as $e ) {
		$grau[ $e[0] ] = ( isset( $grau[ $e[0] ] ) ? $grau[ $e[0] ] : 0 ) + 1;
		$grau[ $e[1] ] = ( isset( $grau[ $e[1] ] ) ? $grau[ $e[1] ] : 0 ) + 1;
		$soma         += $e[2];
	}
	$nos = array();
	foreach ( $g['nos'] as $n ) {
		$p     = isset( $perfis[ $n['lattes'] ] ) ? $perfis[ $n['lattes'] ] : null;
		$nos[] = array( 'n' => $p ? $p[2] : $n['nome'], 'u' => $p ? $p[0] : '', 'g' => $p && isset( $grupo[ $p[1] ] ) ? $grupo[ $p[1] ] : 's4' );
	}

	$h = gemec_est_numeros( array(
		array( count( $grau ), 'membros com coautoria no grupo' ),
		array( count( $g['arestas'] ), 'pares de coautores' ),
		array( $soma, 'produ&ccedil;&otilde;es em coautoria', 'somadas par a par' ),
	) );

	// Grafo de forcas (estatisticas.js, com o d3 do proprio relatorio): nos pelo indice do membro em listas.json.
	$pos = array_flip( wp_list_pluck( $d['membros'], 'lattes' ) );
	$gnos = array();
	foreach ( $g['nos'] as $k => $n ) {
		if ( isset( $pos[ $n['lattes'] ] ) ) {
			$gnos[ $k ] = array( 'i' => $pos[ $n['lattes'] ], 'g' => $nos[ $k ]['g'] );
		}
	}
	$garestas = array();
	foreach ( $g['arestas'] as $e ) {
		if ( isset( $gnos[ $e[0] ], $gnos[ $e[1] ] ) ) {
			$garestas[] = array( $gnos[ $e[0] ]['i'], $gnos[ $e[1] ]['i'], $e[2] );
		}
	}
	$dados = wp_json_encode( array( 'nos' => array_values( $gnos ), 'arestas' => $garestas ) );
	$c     = gemec_est_legenda( $series );
	$c    .= '<div class="gemec-est-grafo" data-gemec-grafo><script type="application/json">' . str_replace( '</', '<\/', $dados ) . '</script>'
		. '<div class="gemec-est-grafo-corpo"><div class="gemec-est-grafo-tela" role="img" aria-label="' . esc_attr( 'Grafo de colaborações: cada círculo é um membro e cada linha liga dois membros que produziram juntos; a espessura cresce com o número de produções em comum. Os pares estão nas tabelas abaixo.' ) . '"></div>'
		. '<aside class="gemec-est-grafo-painel" aria-live="polite"><p class="gemec-est-grafo-dica">Clique em um membro (ou use a busca) para ver os coautores dele no grupo.</p></aside></div></div>';
	$h    .= gemec_est_bloco( 'Grafo de colabora&ccedil;&otilde;es', 'Arraste para mover; para o zoom, use os bot&otilde;es ou Ctrl + roda do mouse. O tamanho do c&iacute;rculo cresce com o n&uacute;mero de coautores; a espessura da linha, com as produ&ccedil;&otilde;es em comum.', $c, 'gemec-est-bloco-rede' );

	$pares = array();
	foreach ( $g['arestas'] as $e ) {
		$pares[] = array( gemec_lattes_curto( $nos[ $e[0] ]['n'] ) . ' e ' . gemec_lattes_curto( $nos[ $e[1] ]['n'] ), $e[2] );
	}
	arsort( $grau );
	$coaut = array();
	foreach ( $grau as $i => $v ) {
		$coaut[] = array( $nos[ $i ]['n'], $v, $nos[ $i ]['u'] );
	}
	$h .= gemec_est_grade( array(
		gemec_est_bloco( 'Parcerias mais frequentes', 'Produ&ccedil;&otilde;es em comum por par.', gemec_est_barras( 'rede-pares', array( 'Par de membros', 'Produ&ccedil;&otilde;es' ), $pares, 'Gráfico de barras: os pares com mais produções em comum.', 's1', false, 12 ) ),
		gemec_est_bloco( 'Membros mais conectados', 'N&uacute;mero de coautores dentro do grupo.', gemec_est_barras( 'rede-coautores', array( 'Membro', 'Coautores no grupo' ), $coaut, 'Gráfico de barras: membros com mais coautores no grupo.', 's2', false, 12 ) ),
	) );

	return array(
		'titulo' => 'Colabora&ccedil;&atilde;o entre membros',
		'menu'   => 'Colabora&ccedil;&atilde;o',
		'sobre'  => 'Rede',
		'lead'   => 'Quem publica com quem dentro do grupo, a partir das produ&ccedil;&otilde;es em coautoria registradas nos curr&iacute;culos.',
		'html'   => $h,
		'kpi'    => array( array( 'n' => count( $g['arestas'] ), 'rot' => 'pares de membros coautores', 'nota' => count( $grau ) . ' membros conectados' ) ),
	);
}

add_filter( 'gemec_estatisticas_secoes', function ( $secoes ) {
	$d = gemec_lattes_relatorio();
	if ( ! $d || ! function_exists( 'gemec_est_bloco' ) ) {
		return $secoes;
	}

	// Publicacoes: toda a producao bibliografica do Lattes, de todos os tipos.
	if ( isset( $secoes['publicacoes'] ) && ! empty( $d['biblio']['n'] ) ) {
		$b     = $d['biblio'];
		$tipos = $b['tipos'];
		usort( $tipos, function ( $x, $y ) {
			return $y['n'] - $x['n'];
		} );
		$linhas = array();
		foreach ( $tipos as $x ) {
			$linhas[] = array( $x['rot'], $x['n'] );
		}
		$secoes['publicacoes']['html'] .= '<h3 class="gemec-est-subtitulo">Toda a produ&ccedil;&atilde;o bibliogr&aacute;fica no Lattes</h3>'
			. '<p class="gemec-est-nota">' . esc_html( number_format_i18n( (int) $b['n'] ) ) . ' itens de todos os tipos: artigos, trabalhos em congressos, livros e cap&iacute;tulos, e tamb&eacute;m resumos, apresenta&ccedil;&otilde;es de trabalho e artigos aceitos.</p>'
			. gemec_est_bloco( 'Por tipo', 'Clique em um tipo para ver os itens.', gemec_est_barras( 'pb-tipos', array( 'Tipo', 'Itens' ), $linhas, 'Gráfico de barras: produção bibliográfica por tipo.', 'periodico', true ) )
			. gemec_lattes_lista( 'biblio', 'Lista completa', 'Filtre por tipo ou membro, ou busque por t&iacute;tulo, autor, ve&iacute;culo e ano.' );
		$secoes['publicacoes']['kpi'][] = array( 'n' => $b['n'], 's' => 'Produ&ccedil;&atilde;o no Lattes', 'rot' => 'itens bibliogr&aacute;ficos de todos os tipos', 'serie' => gemec_est_totais( $b['anos'] ) );
	}

	foreach ( array( 'orientacoes', 'projetos', 'tecnica', 'eventos', 'premios', 'membros', 'colaboracao' ) as $id ) {
		$s = call_user_func( 'gemec_lattes_sec_' . $id, $d );
		if ( $s ) {
			$secoes[ $id ] = $s;
		}
	}
	return $secoes;
} );

/* ------------------------------------------------------- listas e scripts */

/** Endereco versionado de listas.json (muda quando o arquivo muda). */
function gemec_lattes_listas_url() {
	$arq = __DIR__ . '/listas.json';
	return is_readable( $arq ) ? add_query_arg( 'gemec_lattes_listas', (string) filemtime( $arq ), home_url( '/' ) ) : '';
}

// O servidor nao comprime arquivos estaticos: listas.json sai daqui com gzip e cache longo.
add_action( 'init', function () {
	if ( ! isset( $_GET['gemec_lattes_listas'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification
		return;
	}
	$arq = __DIR__ . '/listas.json';
	if ( ! is_readable( $arq ) ) {
		status_header( 404 );
		exit;
	}
	$json = (string) file_get_contents( $arq );
	header( 'Content-Type: application/json; charset=utf-8' );
	header( 'Cache-Control: public, max-age=31536000, immutable' );
	header( 'Vary: Accept-Encoding' );
	$aceita = isset( $_SERVER['HTTP_ACCEPT_ENCODING'] ) ? (string) $_SERVER['HTTP_ACCEPT_ENCODING'] : ''; // phpcs:ignore
	if ( function_exists( 'gzencode' ) && false !== strpos( $aceita, 'gzip' ) && ! ini_get( 'zlib.output_compression' ) ) {
		$json = gzencode( $json, 6 );
		header( 'Content-Encoding: gzip' );
	}
	header( 'Content-Length: ' . strlen( $json ) );
	echo $json; // phpcs:ignore WordPress.Security.EscapeOutput
	exit;
} );

/**
 * Scripts das listas, fichas e grafo, com os membros na ordem de listas.json.
 * $grafo: carrega tambem o d3 do proprio relatorio (so a pagina Estatisticas).
 */
function gemec_lattes_scripts( $grafo = false ) {
	static $feito = false;
	if ( $feito || ! gemec_lattes_relatorio() ) {
		return;
	}
	$feito = true;
	$js    = __DIR__ . '/estatisticas.js';
	$dep   = array();
	$d3    = __DIR__ . '/relatorio/js/d3.min.js';
	if ( $grafo && is_readable( $d3 ) ) {
		wp_enqueue_script( 'gemec-d3', plugins_url( 'relatorio/js/d3.min.js', __FILE__ ), array(), (string) filemtime( $d3 ), true );
		$dep[] = 'gemec-d3';
	}
	wp_enqueue_script( 'gemec-lattes-est', plugins_url( 'estatisticas.js', __FILE__ ), $dep, (string) filemtime( $js ), true );
	$perfis  = gemec_lattes_perfis();
	$ids     = gemec_lattes_mapa_membros();
	$cats    = function_exists( 'gemec_categorias' ) ? gemec_categorias() : array();
	$membros = array();
	foreach ( gemec_lattes_relatorio()['membros'] as $m ) {
		$p         = isset( $perfis[ $m['lattes'] ] ) ? $perfis[ $m['lattes'] ] : null;
		$membros[] = array(
			'n'   => $p ? $p[2] : $m['nome'],
			'u'   => $p ? $p[0] : '',
			'l'   => $m['lattes'],
			'cat' => $p && isset( $cats[ $p[1] ] ) ? html_entity_decode( wp_strip_all_tags( $cats[ $p[1] ]['titulo'] ), ENT_QUOTES, 'UTF-8' ) : $m['rotulo'],
			'ar'  => $m['area'],
			'in'  => $m['instituicao'],
			'bo'  => $m['bolsa'],
			'at'  => $m['atualizacao'],
			'f'   => isset( $ids[ $m['lattes'] ] ) ? (string) get_the_post_thumbnail_url( $ids[ $m['lattes'] ], 'thumbnail' ) : '',
		);
	}
	wp_add_inline_script( 'gemec-lattes-est', 'window.GEMEC_LATTES=' . wp_json_encode( array( 'url' => gemec_lattes_listas_url(), 'membros' => $membros ) ) . ';', 'before' );
}

add_action( 'wp_enqueue_scripts', function () {
	if ( is_singular() && has_shortcode( (string) get_post_field( 'post_content', get_queried_object_id() ), 'gemec_estatisticas' ) ) {
		gemec_lattes_scripts( true );
	}
} );

/**
 * Perfil do membro (gemec-core): dados do Lattes para o cabecalho e o indice
 * do membro em listas.json, para as abas montadas por estatisticas.js. Null
 * quando o membro nao esta no relatorio.
 */
add_filter( 'gemec_perfil_lattes', function ( $atual, $id ) {
	$d = gemec_lattes_relatorio();
	if ( ! $d || ! preg_match( '/(\d{16})/', (string) get_post_meta( $id, 'gemec_lattes', true ), $mm ) ) {
		return $atual;
	}
	foreach ( $d['membros'] as $i => $m ) {
		if ( $m['lattes'] === $mm[1] ) {
			gemec_lattes_scripts();
			return array( 'i' => $i, 'area' => $m['area'], 'instituicao' => $m['instituicao'], 'bolsa' => $m['bolsa'], 'atualizacao' => $m['atualizacao'] );
		}
	}
	return $atual;
}, 10, 2 );
