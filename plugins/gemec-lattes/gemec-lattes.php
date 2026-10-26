<?php
/**
 * Plugin Name: GEMEC - Relatorio Lattes
 * Description: Relatorio de producao do grupo gerado pelo scriptLattes (Mena-Chalco &amp; Cesar-Jr., 2009) a partir dos curriculos Lattes dos membros. O relatorio e estatico, fica em relatorio/ e e gerado fora do site por scripts/lattes/lattes.py; o shortcode [gemec_lattes] o mostra dentro da pagina. Leva tambem as secoes do relatorio (relatorio.json) a pagina Estatisticas.
 * Version:     1.9.0
 * Author:      GEMEC - UNIFEI
 * Requires PHP: 7.4
 * Text Domain: gemec
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

require_once __DIR__ . '/estatisticas.php';

/**
 * Data de geracao e numero de curriculos, gravados por lattes.py em relatorio.txt.
 */
function gemec_lattes_info() {
	$arq = __DIR__ . '/relatorio.txt';
	if ( ! is_readable( $arq ) ) {
		return array( '', 0 );
	}
	$linhas = array_map( 'trim', file( $arq ) );
	return array( isset( $linhas[0] ) ? $linhas[0] : '', isset( $linhas[1] ) ? (int) $linhas[1] : 0 );
}

function gemec_lattes_shortcode() {
	$index = __DIR__ . '/relatorio/index.html';
	if ( ! is_readable( $index ) ) {
		return '<p class="gemec-lattes-vazio">O relat&oacute;rio do Lattes ainda n&atilde;o foi gerado.</p>';
	}
	list( $data, $n ) = gemec_lattes_info();
	$src = add_query_arg( 'v', (string) filemtime( $index ), plugins_url( 'relatorio/index.html', __FILE__ ) );

	$nota = 'Gerado pelo <a href="https://github.com/jpmenachalco/scriptLattes" target="_blank" rel="noopener">scriptLattes</a> a partir dos curr&iacute;culos Lattes';
	if ( $n ) {
		$nota .= ' de ' . (int) $n . ' membros';
	}
	if ( $data ) {
		$nota .= ', em ' . esc_html( $data );
	}
	$nota .= '. Para a lista sempre atualizada de artigos, veja <a href="' . esc_url( home_url( '/publicacoes/' ) ) . '">Publica&ccedil;&otilde;es</a>.';

	ob_start();
	?>
	<div class="gemec-lattes">
		<p class="gemec-lattes-nota"><?php echo $nota; // phpcs:ignore WordPress.Security.EscapeOutput ?></p>
		<iframe id="gemec-lattes-quadro" class="gemec-lattes-quadro" src="<?php echo esc_url( $src ); ?>" title="Relat&oacute;rio Lattes do GEMEC" loading="lazy"></iframe>
	</div>
	<?php
	return ob_get_clean();
}
add_shortcode( 'gemec_lattes', 'gemec_lattes_shortcode' );

/* -------------------------------------------------------------------------
 * Importacao (REST), chamada por lattes.py enviar. A cada sincronizacao as
 * publicacoes do Lattes sao refeitas do zero, sem deixar o site vazio:
 *   POST /gemec/v1/lattes/membros      resumo do CV de cada membro (quem nao
 *                                      veio perde o resumo)
 *   POST /gemec/v1/lattes/limpar       apaga lotes incompletos de envios que
 *                                      falharam
 *   POST /gemec/v1/lattes/publicacoes  cria as publicacoes do lote novo como
 *                                      rascunho (gemec_lote)
 *   POST /gemec/v1/lattes/concluir     publica o lote novo e apaga de vez tudo
 *                                      o mais que veio do Lattes; grava o log
 * limpar e concluir trabalham em partes e devolvem 'faltam' (o script repete).
 * Fica a marca Ocultar (reaplicada pela chave do trabalho).
 * ---------------------------------------------------------------------- */

define( 'GEMEC_LATTES_PARTE', 30 ); // registros por chamada em limpar/concluir (o servidor corta pedidos longos com 503)

/**
 * ID Lattes (16 digitos) => ID do membro no site, de todos os membros cadastrados (os ocultos, post Privado, inclusive).
 * Tambem 'orcid:<ORCID>' => ID: as publicacoes dos membros sem Lattes (estrangeiros) vem do OpenAlex pelo ORCID.
 */
function gemec_lattes_mapa_membros() {
	$mapa = array();
	if ( ! defined( 'GEMEC_MEMBRO' ) ) {
		return $mapa;
	}
	foreach ( get_posts( array( 'post_type' => GEMEC_MEMBRO, 'posts_per_page' => -1, 'post_status' => array( 'publish', 'private' ), 'fields' => 'ids' ) ) as $id ) {
		if ( preg_match( '/(\d{16})/', (string) get_post_meta( $id, 'gemec_lattes', true ), $m ) ) {
			$mapa[ $m[1] ] = $id;
		}
		if ( preg_match( '/(\d{4}-\d{4}-\d{4}-\d{3}[\dX])/', strtoupper( (string) get_post_meta( $id, 'gemec_orcid', true ) ), $m ) ) {
			$mapa[ 'orcid:' . $m[1] ] = $id;
		}
	}
	return $mapa;
}

/** Chaves das publicacoes do Lattes que alguem marcou como ocultas (sobrevivem a reconstrucao). */
function gemec_lattes_chaves_ocultas() {
	$out = array();
	$ids = get_posts( array( 'post_type' => GEMEC_PUB, 'posts_per_page' => -1, 'post_status' => 'publish', 'fields' => 'ids', 'meta_query' => array( array( 'key' => 'gemec_fonte', 'value' => 'lattes' ), array( 'key' => 'gemec_oculta', 'value' => '1' ) ) ) );
	foreach ( $ids as $id ) {
		$out[ (string) get_post_meta( $id, 'gemec_lattes_chave', true ) ] = true;
	}
	return $out;
}

/** Lista vinda do script, limpa: itens com os campos dados ou textos (campos vazio). */
function gemec_lattes_limpar_lista( $itens, $campos = array() ) {
	$out = array();
	foreach ( array_slice( (array) $itens, 0, 40 ) as $it ) {
		if ( $campos && is_array( $it ) ) {
			$l = array();
			foreach ( $campos as $c ) {
				$l[ $c ] = isset( $it[ $c ] ) ? sanitize_text_field( (string) $it[ $c ] ) : '';
			}
			$out[] = $l;
		} elseif ( ! $campos && is_string( $it ) && '' !== trim( $it ) ) {
			$out[] = sanitize_text_field( $it );
		}
	}
	return $out;
}

function gemec_lattes_rest_membros( WP_REST_Request $req ) {
	$mapa  = gemec_lattes_mapa_membros();
	$n     = 0;
	$sem   = array();
	$veio  = array();
	$dados = (array) $req->get_param( 'membros' );
	foreach ( $dados as $lid => $m ) {
		$lid = (string) $lid;
		if ( ! isset( $mapa[ $lid ] ) ) {
			$sem[] = isset( $m['nome'] ) ? sanitize_text_field( $m['nome'] ) : $lid;
			continue;
		}
		$id          = $mapa[ $lid ];
		$veio[ $id ] = true;
		update_post_meta( $id, 'gemec_resumo_lattes', sanitize_textarea_field( isset( $m['resumo'] ) ? $m['resumo'] : '' ) );
		update_post_meta( $id, 'gemec_lattes_atualizado', sanitize_text_field( isset( $m['atualizado'] ) ? $m['atualizado'] : '' ) );
		update_post_meta( $id, 'gemec_lattes_salvo', sanitize_text_field( isset( $m['salvo'] ) ? $m['salvo'] : '' ) );
		// Formacao academica e areas de atuacao do CV, mostradas no perfil (gemec-core).
		update_post_meta( $id, 'gemec_formacao_lattes', gemec_lattes_limpar_lista( isset( $m['formacao'] ) ? $m['formacao'] : array(), array( 'anos', 'curso', 'inst', 'titulo', 'orientador', 'coorientador' ) ) );
		update_post_meta( $id, 'gemec_areas_lattes', gemec_lattes_limpar_lista( isset( $m['areas'] ) ? $m['areas'] : array() ) );
		$n++;
	}
	// Do zero tambem aqui: quem nao veio nesta sincronizacao fica sem resumo do Lattes.
	$limpos = 0;
	if ( $dados && defined( 'GEMEC_MEMBRO' ) ) {
		foreach ( get_posts( array( 'post_type' => GEMEC_MEMBRO, 'posts_per_page' => -1, 'post_status' => 'any', 'fields' => 'ids', 'meta_key' => 'gemec_resumo_lattes', 'meta_compare' => 'EXISTS' ) ) as $id ) {
			if ( empty( $veio[ $id ] ) ) {
				foreach ( array( 'gemec_resumo_lattes', 'gemec_lattes_atualizado', 'gemec_lattes_salvo', 'gemec_formacao_lattes', 'gemec_areas_lattes' ) as $k ) {
					delete_post_meta( $id, $k );
				}
				$limpos++;
			}
		}
	}
	return array( 'atualizados' => $n, 'sem_cadastro' => $sem, 'sem_resumo' => $limpos );
}

/**
 * Ate GEMEC_LATTES_PARTE publicacoes da consulta que passam no filtro,
 * percorrendo as paginas (consultas simples; o filtro fino e feito aqui).
 */
function gemec_lattes_juntar( $args, $filtro ) {
	$out    = array();
	$pagina = 1;
	while ( count( $out ) < GEMEC_LATTES_PARTE ) {
		$ids = get_posts( array_merge( $args, array( 'post_type' => GEMEC_PUB, 'posts_per_page' => 200, 'paged' => $pagina, 'fields' => 'ids', 'orderby' => 'ID', 'order' => 'ASC' ) ) );
		if ( ! $ids ) {
			break;
		}
		update_meta_cache( 'post', $ids ); // uma consulta para a pagina toda, nao uma por post
		foreach ( $ids as $id ) {
			if ( count( $out ) < GEMEC_LATTES_PARTE && $filtro( $id ) ) {
				$out[] = $id;
			}
		}
		$pagina++;
	}
	return $out;
}

/** Valida o identificador do lote mandado pelo script (ex.: 20261007-1530). */
function gemec_lattes_lote( WP_REST_Request $req ) {
	$lote = (string) $req->get_param( 'lote' );
	return preg_match( '/^[0-9A-Za-z_-]{6,40}$/', $lote ) ? $lote : '';
}

function gemec_lattes_rest_limpar( WP_REST_Request $req ) {
	$lote = gemec_lattes_lote( $req );
	if ( ! $lote ) {
		return new WP_Error( 'gemec_lote', 'Lote invalido.', array( 'status' => 400 ) );
	}
	// Rascunhos do Lattes de outro lote (envio que caiu no meio).
	$ids = get_posts( array( 'post_type' => GEMEC_PUB, 'posts_per_page' => GEMEC_LATTES_PARTE, 'post_status' => 'draft', 'fields' => 'ids', 'meta_key' => 'gemec_lote_aberto', 'meta_value' => '1' ) );
	$ids = array_values( array_filter( $ids, function ( $id ) use ( $lote ) {
		return get_post_meta( $id, 'gemec_lote', true ) !== $lote;
	} ) );
	foreach ( $ids as $id ) {
		wp_delete_post( $id, true );
	}
	return array( 'apagadas' => count( $ids ), 'faltam' => count( $ids ) >= GEMEC_LATTES_PARTE ? 1 : 0 );
}

function gemec_lattes_rest_publicacoes( WP_REST_Request $req ) {
	if ( function_exists( 'set_time_limit' ) ) {
		@set_time_limit( 300 ); // phpcs:ignore
	}
	$lote = gemec_lattes_lote( $req );
	if ( ! $lote ) {
		return new WP_Error( 'gemec_lote', 'Lote invalido.', array( 'status' => 400 ) );
	}
	$tipos   = array( 'periodico', 'congresso', 'livro' );
	$mapa    = gemec_lattes_mapa_membros();
	$ocultas = gemec_lattes_chaves_ocultas();
	$tot     = array( 'criadas' => 0 );

	foreach ( (array) $req->get_param( 'itens' ) as $it ) {
		$chave  = isset( $it['chave'] ) ? substr( (string) $it['chave'], 0, 250 ) : '';
		$titulo = isset( $it['titulo'] ) ? sanitize_text_field( $it['titulo'] ) : '';
		if ( '' === $chave || '' === $titulo ) {
			continue;
		}
		$membros = array();
		foreach ( (array) ( isset( $it['lattes'] ) ? $it['lattes'] : array() ) as $lid ) {
			if ( isset( $mapa[ (string) $lid ] ) ) {
				$membros[] = $mapa[ (string) $lid ];
			}
		}
		$autores = array();
		foreach ( (array) ( isset( $it['autores'] ) ? $it['autores'] : array() ) as $a ) {
			$nome = esc_html( sanitize_text_field( isset( $a['nome'] ) ? $a['nome'] : '' ) );
			if ( '' !== $nome ) {
				$autores[] = empty( $a['membro'] ) ? $nome : '<strong>' . $nome . '</strong>';
			}
		}
		$ano  = isset( $it['ano'] ) && preg_match( '/^\d{4}$/', (string) $it['ano'] ) ? (string) $it['ano'] : '';
		$tipo = isset( $it['tipo'] ) && in_array( $it['tipo'], $tipos, true ) ? $it['tipo'] : 'periodico';
		$doi  = isset( $it['doi'] ) ? sanitize_text_field( $it['doi'] ) : '';
		$meta = array(
			'tipo'          => $tipo,
			'data'          => $ano,
			'autores'       => implode( '; ', $autores ), // nomes de citacao do Lattes ja tem virgula
			'veiculo'       => isset( $it['veiculo'] ) ? sanitize_text_field( $it['veiculo'] ) : '',
			'doi'           => $doi,
			'fonte'         => 'lattes',
			'lattes_chave'  => $chave,
			'lote'          => $lote,
			'lote_aberto'   => '1', // vira '' quando o lote e publicado em concluir
			'oculta'        => isset( $ocultas[ $chave ] ) ? '1' : '',
		);

		$id = wp_insert_post( array( 'post_type' => GEMEC_PUB, 'post_title' => $titulo, 'post_status' => 'draft' ), true );
		if ( is_wp_error( $id ) ) {
			continue;
		}
		foreach ( $meta as $c => $v ) {
			update_post_meta( $id, 'gemec_' . $c, $v );
		}
		update_post_meta( $id, 'gemec_membros', array_values( array_unique( $membros ) ) );
		$tot['criadas']++;
	}
	return $tot;
}

function gemec_lattes_rest_concluir( WP_REST_Request $req ) {
	if ( function_exists( 'set_time_limit' ) ) {
		@set_time_limit( 300 ); // phpcs:ignore
	}
	$lote = gemec_lattes_lote( $req );
	if ( ! $lote ) {
		return new WP_Error( 'gemec_lote', 'Lote invalido.', array( 'status' => 400 ) );
	}
	// Sem nenhuma publicacao no lote novo, nada e apagado: um envio vazio por engano nao esvazia o site.
	$novas = get_posts( array( 'post_type' => GEMEC_PUB, 'posts_per_page' => 1, 'post_status' => array( 'draft', 'publish' ), 'fields' => 'ids', 'meta_key' => 'gemec_lote', 'meta_value' => $lote ) );
	if ( ! $novas ) {
		return new WP_Error( 'gemec_lote_vazio', 'O lote novo esta vazio; nada foi apagado.', array( 'status' => 400 ) );
	}
	// 1. Publica o lote novo.
	$pub = get_posts( array( 'post_type' => GEMEC_PUB, 'posts_per_page' => GEMEC_LATTES_PARTE, 'post_status' => 'draft', 'fields' => 'ids', 'meta_query' => array( array( 'key' => 'gemec_lote', 'value' => $lote ), array( 'key' => 'gemec_lote_aberto', 'value' => '1' ) ) ) );
	foreach ( $pub as $id ) {
		update_post_meta( $id, 'gemec_lote_aberto', '' );
		wp_update_post( array( 'ID' => $id, 'post_status' => 'publish' ) );
	}
	if ( count( $pub ) >= GEMEC_LATTES_PARTE ) {
		return array( 'publicadas' => count( $pub ), 'apagadas' => 0, 'faltam' => 1 );
	}
	// 2. Apaga de vez tudo o mais que veio do Lattes (lotes antigos e importacoes de antes dos lotes).
	$velhas = gemec_lattes_juntar(
		array( 'post_status' => 'any', 'meta_key' => 'gemec_fonte', 'meta_value' => 'lattes' ),
		function ( $id ) use ( $lote ) {
			return get_post_meta( $id, 'gemec_lote', true ) !== $lote;
		}
	);
	foreach ( $velhas as $id ) {
		wp_delete_post( $id, true );
	}
	if ( count( $velhas ) >= GEMEC_LATTES_PARTE ) {
		return array( 'publicadas' => count( $pub ), 'apagadas' => count( $velhas ), 'faltam' => 1 );
	}
	$total = (int) ( new WP_Query( array( 'post_type' => GEMEC_PUB, 'post_status' => 'publish', 'posts_per_page' => 1, 'fields' => 'ids', 'meta_key' => 'gemec_lote', 'meta_value' => $lote ) ) )->found_posts;
	update_option( 'gemec_lattes_log', array( 'fim' => time(), 'cvs' => (int) $req->get_param( 'cvs' ), 'publicacoes' => $total, 'lote' => $lote ), false );
	return array( 'publicadas' => count( $pub ), 'apagadas' => count( $velhas ), 'faltam' => 0, 'total' => $total );
}

add_action( 'rest_api_init', function () {
	$pode = function () {
		return current_user_can( 'edit_posts' );
	};
	foreach ( array( 'membros', 'limpar', 'publicacoes', 'concluir' ) as $rota ) {
		register_rest_route(
			'gemec/v1',
			'/lattes/' . $rota,
			array(
				'methods'             => 'POST',
				'callback'            => 'gemec_lattes_rest_' . $rota,
				'permission_callback' => $pode,
			)
		);
	}
} );

/* Tela Publicacoes -> Importacao do Lattes: situacao da ultima importacao. */
add_action( 'admin_menu', function () {
	if ( defined( 'GEMEC_PUB' ) ) {
		add_submenu_page( 'edit.php?post_type=' . GEMEC_PUB, 'Importação do Lattes', 'Importação do Lattes', 'edit_posts', 'gemec-lattes', 'gemec_lattes_tela' );
	}
} );

function gemec_lattes_tela() {
	$log = get_option( 'gemec_lattes_log' );
	list( $data, $n ) = gemec_lattes_info();
	?>
	<div class="wrap" style="max-width:860px">
		<h1>Importa&ccedil;&atilde;o do Curr&iacute;culo Lattes</h1>
		<p>As publica&ccedil;&otilde;es do site e o resumo de cada pesquisador v&ecirc;m dos Curr&iacute;culos Lattes dos membros. Toda semana o <a href="https://github.com/jpmenachalco/scriptLattes" target="_blank" rel="noopener">scriptLattes</a> baixa os curr&iacute;culos de todos os membros que t&ecirc;m o link do Lattes no cadastro, gera o relat&oacute;rio do grupo e envia tudo para c&aacute; (<code>scripts/lattes/lattes.py semanal</code>).</p>
		<table class="widefat striped" style="margin:18px 0"><tbody>
		<?php if ( is_array( $log ) ) : ?>
			<tr><td>&Uacute;ltima importa&ccedil;&atilde;o</td><td><?php echo esc_html( wp_date( 'd/m/Y H:i', $log['fim'] ) ); ?></td></tr>
			<tr><td>Curr&iacute;culos lidos</td><td><?php echo (int) $log['cvs']; ?></td></tr>
			<tr><td>Publica&ccedil;&otilde;es do Lattes no site</td><td><?php echo (int) $log['publicacoes']; ?> (refeitas do zero a cada sincroniza&ccedil;&atilde;o; as marcadas como Ocultar continuam ocultas)</td></tr>
		<?php else : ?>
			<tr><td colspan="2">Ainda n&atilde;o houve importa&ccedil;&atilde;o.</td></tr>
		<?php endif; ?>
			<tr><td>Relat&oacute;rio Lattes</td><td><?php echo $data ? 'gerado em ' . esc_html( $data ) . ' com ' . (int) $n . ' curr&iacute;culos &mdash; <a href="' . esc_url( home_url( '/relatorio-lattes/' ) ) . '">ver</a>' : 'ainda n&atilde;o gerado'; ?></td></tr>
		</tbody></table>
		<h2>Quando algo vier errado</h2>
		<ul style="list-style:disc;margin-left:20px">
			<li><strong>Trabalho errado ou repetido:</strong> abra a publica&ccedil;&atilde;o e marque <em>Ocultar do site</em>. A importa&ccedil;&atilde;o respeita a marca.</li>
			<li><strong>Falta um trabalho:</strong> ele precisa estar no Curr&iacute;culo Lattes de algum membro; entra na importa&ccedil;&atilde;o seguinte.</li>
			<li><strong>Membro sem publica&ccedil;&otilde;es ou sem resumo:</strong> confira o link do Lattes no cadastro do membro.</li>
		</ul>
	</div>
	<?php
}

add_action( 'wp_enqueue_scripts', function () {
	if ( ! is_singular() || ! has_shortcode( (string) get_post_field( 'post_content', get_queried_object_id() ), 'gemec_lattes' ) ) {
		return;
	}
	$css = __DIR__ . '/gemec-lattes.css';
	$js  = __DIR__ . '/gemec-lattes.js';
	wp_enqueue_style( 'gemec-lattes', plugins_url( 'gemec-lattes.css', __FILE__ ), array(), (string) filemtime( $css ) );
	wp_enqueue_script( 'gemec-lattes', plugins_url( 'gemec-lattes.js', __FILE__ ), array(), (string) filemtime( $js ), true );
} );
