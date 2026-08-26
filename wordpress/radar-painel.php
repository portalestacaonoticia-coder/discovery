<?php
/**
 * Plugin Name: Radar — Painel de acompanhamento
 * Description: Fila de pautas, cotações, artigos e execuções dos crons do radar, direto do Supabase, dentro do wp-admin.
 * Version: 1.0.0
 * Author: Radar de pautas
 *
 * Configuração: menu Radar -> seção "Configuração" (ou constantes RADAR_SUPABASE_URL,
 * RADAR_SUPABASE_CHAVE e RADAR_SITE no wp-config.php, que têm precedência).
 * O plugin só LÊ o Supabase; quem escreve são os crons do radar.
 */

if (!defined('ABSPATH')) { exit; }

class Radar_Painel {

    const OPCAO = 'radar_painel_config';
    const CACHE_TTL = 60; // segundos; o dado muda no ritmo dos crons, nao do F5

    public static function inicia() {
        add_action('admin_menu', array(__CLASS__, 'menu'));
    }

    public static function menu() {
        add_menu_page('Radar', 'Radar', 'manage_options', 'radar-painel',
            array(__CLASS__, 'pagina'), 'dashicons-chart-line', 3);
    }

    // -- configuracao -------------------------------------------------------

    private static function config() {
        $opcao = get_option(self::OPCAO, array());
        return array(
            'url'   => defined('RADAR_SUPABASE_URL') ? RADAR_SUPABASE_URL : (isset($opcao['url']) ? $opcao['url'] : ''),
            'chave' => defined('RADAR_SUPABASE_CHAVE') ? RADAR_SUPABASE_CHAVE : (isset($opcao['chave']) ? $opcao['chave'] : ''),
            'site'  => defined('RADAR_SITE') ? RADAR_SITE : (isset($opcao['site']) ? $opcao['site'] : 'doll'),
        );
    }

    private static function salva_config() {
        if (!isset($_POST['radar_painel_nonce'])) { return; }
        if (!wp_verify_nonce($_POST['radar_painel_nonce'], 'radar_painel_salvar')) { return; }
        if (!current_user_can('manage_options')) { return; }

        $atual = get_option(self::OPCAO, array());
        $novo = array(
            'url'   => esc_url_raw(trim(isset($_POST['radar_url']) ? $_POST['radar_url'] : '')),
            'site'  => sanitize_key(isset($_POST['radar_site']) ? $_POST['radar_site'] : 'doll'),
            'chave' => isset($atual['chave']) ? $atual['chave'] : '',
        );
        // Campo de chave vazio preserva a que ja esta salva (para nao reexibir segredo).
        $chave = trim(isset($_POST['radar_chave']) ? $_POST['radar_chave'] : '');
        if ($chave !== '') { $novo['chave'] = sanitize_text_field($chave); }

        update_option(self::OPCAO, $novo, false);
        delete_transient(self::cache_chave($novo['site']));
        echo '<div class="notice notice-success"><p>Configuração salva.</p></div>';
    }

    private static function cache_chave($site) {
        return 'radar_painel_' . $site;
    }

    // -- leituras do Supabase (PostgREST) -----------------------------------

    private static function consulta($cfg, $recurso, $query, $contar = false) {
        $url = rtrim($cfg['url'], '/') . '/rest/v1/' . $recurso . '?' . $query;
        $cabecalhos = array(
            'apikey'        => $cfg['chave'],
            'Authorization' => 'Bearer ' . $cfg['chave'],
        );
        if ($contar) { $cabecalhos['Prefer'] = 'count=exact'; }

        $resposta = wp_remote_get($url, array('headers' => $cabecalhos, 'timeout' => 15));
        if (is_wp_error($resposta)) {
            return array('dados' => null, 'total' => null, 'erro' => $resposta->get_error_message());
        }
        $codigo = wp_remote_retrieve_response_code($resposta);
        if ($codigo >= 400) {
            return array('dados' => null, 'total' => null, 'erro' => 'HTTP ' . $codigo);
        }
        $dados = json_decode(wp_remote_retrieve_body($resposta), true);
        $total = null;
        $faixa = wp_remote_retrieve_header($resposta, 'content-range');
        if ($faixa && strpos($faixa, '/') !== false) {
            $total = (int) substr($faixa, strpos($faixa, '/') + 1);
        }
        return array('dados' => is_array($dados) ? $dados : array(), 'total' => $total, 'erro' => null);
    }

    private static function dados($cfg) {
        $chave_cache = self::cache_chave($cfg['site']);
        if (isset($_GET['radar_atualizar']) && check_admin_referer('radar_atualizar')) {
            delete_transient($chave_cache);
        }
        $pronto = get_transient($chave_cache);
        if ($pronto !== false) { return $pronto; }

        $s = 'site=eq.' . rawurlencode($cfg['site']);
        $d = array();
        $d['execucoes'] = self::consulta($cfg, 'execucoes', $s . '&order=fim.desc&limit=10');
        $d['cotacoes']  = self::consulta($cfg, 'cotacoes', $s . '&moeda=eq.USD&order=data.desc&limit=30');
        $d['pautas']    = self::consulta($cfg, 'pautas', $s . '&order=criado_em.desc&limit=20&select=*,itens(titulo,url,veiculo)');
        $d['artigos']   = self::consulta($cfg, 'artigos', $s . '&order=criado_em.desc&limit=10&select=id,titulo,tipo,status,motivo_portao,url_publicada,criado_em');
        $d['contagens'] = array();
        foreach (array('nova', 'aprovada', 'rascunho', 'publicada', 'descartada') as $st) {
            $r = self::consulta($cfg, 'pautas', $s . '&status=eq.' . $st . '&select=id&limit=1', true);
            if (!empty($r['total'])) { $d['contagens'][$st] = $r['total']; }
        }
        set_transient($chave_cache, $d, self::CACHE_TTL);
        return $d;
    }

    // -- formatacao ---------------------------------------------------------

    private static function moeda($v) {
        return 'R$ ' . number_format((float) $v, 4, ',', '.');
    }

    private static function pct($v) {
        return str_replace('.', ',', sprintf('%+.2f%%', (float) $v));
    }

    private static function quando($iso) {
        if (!$iso) { return '—'; }
        return wp_date('d/m H:i', strtotime($iso));
    }

    private static function duracao($inicio, $fim) {
        if (!$inicio || !$fim) { return '—'; }
        $seg = max(0, strtotime($fim) - strtotime($inicio));
        if ($seg < 60) { return $seg . ' s'; }
        return floor($seg / 60) . ' min ' . ($seg % 60) . ' s';
    }

    private static function selo($status) {
        $mapa = array(
            'ok'          => array('bom',     '✓ ok'),
            'publicada'   => array('bom',     '✓ publicada'),
            'aprovada'    => array('bom',     '✓ aprovada'),
            'rascunho'    => array('alerta',  '◐ rascunho'),
            'erro'        => array('critico', '✕ erro'),
            'sem_cotacao' => array('neutro',  '— sem cotação'),
            'nova'        => array('info',    '● nova'),
            'descartada'  => array('neutro',  'descartada'),
        );
        $v = isset($mapa[$status]) ? $mapa[$status] : array('neutro', $status);
        return '<span class="radar-selo radar-selo-' . esc_attr($v[0]) . '">' . esc_html($v[1]) . '</span>';
    }

    // -- grafico SVG da serie PTAX ------------------------------------------

    private static function grafico($serie) {
        $n = count($serie);
        if ($n < 2) { return ''; }

        $larg = 720; $alt = 240;
        $m = array('esq' => 56, 'dir' => 16, 'topo' => 14, 'base' => 26);
        $vendas = array();
        foreach ($serie as $c) { $vendas[] = (float) $c['ptax_venda']; }
        $min = min($vendas); $max = max($vendas);
        if ($min === $max) { $min -= 0.05; $max += 0.05; }
        $folga = ($max - $min) * 0.1; $min -= $folga; $max += $folga;

        $x = function ($i) use ($larg, $m, $n) { return $m['esq'] + $i * ($larg - $m['esq'] - $m['dir']) / ($n - 1); };
        $y = function ($v) use ($alt, $m, $min, $max) { return $m['topo'] + ($alt - $m['topo'] - $m['base']) * (1 - ($v - $min) / ($max - $min)); };

        // passo "redondo" para ~4 linhas de grade
        $bruto = ($max - $min) / 4;
        $exp = pow(10, floor(log10($bruto)));
        $normal = $bruto / $exp;
        $passo = ($normal > 5 ? 10 : ($normal > 2 ? 5 : ($normal > 1 ? 2 : 1))) * $exp;

        $svg = '<div class="radar-grafico-envelope">';
        $svg .= '<svg id="radar-grafico" viewBox="0 0 ' . $larg . ' ' . $alt . '" role="img" ';
        $pontos_js = array();
        foreach ($serie as $i => $c) {
            $pontos_js[] = array(
                'x' => round($x($i), 1), 'y' => round($y($vendas[$i]), 1),
                'data' => substr($c['data'], 8, 2) . '/' . substr($c['data'], 5, 2) . '/' . substr($c['data'], 0, 4),
                'venda' => self::moeda($c['ptax_venda']), 'compra' => self::moeda($c['ptax_compra']),
            );
        }
        $svg .= "data-pontos='" . esc_attr(wp_json_encode($pontos_js)) . "' ";
        $svg .= 'aria-label="Série da PTAX de venda com ' . $n . ' pregões">';

        for ($v = ceil($min / $passo) * $passo; $v <= $max; $v += $passo) {
            $yy = $y($v);
            $svg .= '<line x1="' . $m['esq'] . '" x2="' . ($larg - $m['dir']) . '" y1="' . $yy . '" y2="' . $yy . '" stroke="#e1e0d9" stroke-width="1"/>';
            $svg .= '<text x="' . ($m['esq'] - 6) . '" y="' . ($yy + 3.5) . '" text-anchor="end" font-size="11" fill="#898781">' . str_replace('.', ',', sprintf('%.2f', $v)) . '</text>';
        }
        $svg .= '<line x1="' . $m['esq'] . '" x2="' . ($larg - $m['dir']) . '" y1="' . ($alt - $m['base']) . '" y2="' . ($alt - $m['base']) . '" stroke="#c3c2b7" stroke-width="1"/>';

        $cada_n = max(1, (int) ceil($n / 5));
        foreach ($serie as $i => $c) {
            if ($i % $cada_n === 0) {
                $svg .= '<text x="' . $x($i) . '" y="' . ($alt - $m['base'] + 16) . '" text-anchor="middle" font-size="11" fill="#898781">'
                    . esc_html(substr($c['data'], 8, 2) . '/' . substr($c['data'], 5, 2)) . '</text>';
            }
        }

        $caminho = '';
        foreach ($vendas as $i => $v) {
            $caminho .= ($i ? 'L' : 'M') . round($x($i), 1) . ',' . round($y($v), 1) . ' ';
        }
        $svg .= '<path d="' . trim($caminho) . '" fill="none" stroke="#2a78d6" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>';

        // rotulo direto so no ultimo ponto — nunca numero em todo ponto
        $ux = $x($n - 1); $uy = $y($vendas[$n - 1]);
        $svg .= '<circle cx="' . $ux . '" cy="' . $uy . '" r="4" fill="#2a78d6" stroke="#ffffff" stroke-width="2"/>';
        $svg .= '<text x="' . ($ux - 8) . '" y="' . ($uy - 10) . '" text-anchor="end" font-size="12" font-weight="600" fill="#52514e">'
            . str_replace('.', ',', sprintf('%.4f', $vendas[$n - 1])) . '</text>';

        $svg .= '<line id="radar-mira" y1="' . $m['topo'] . '" y2="' . ($alt - $m['base']) . '" stroke="#c3c2b7" stroke-width="1" stroke-dasharray="3 3" style="display:none"/>';
        $svg .= '<circle id="radar-ponto" r="4" fill="#2a78d6" stroke="#ffffff" stroke-width="2" style="display:none"/>';
        $svg .= '</svg>';
        $svg .= '<div id="radar-dica" class="radar-dica" style="display:none"></div>';
        $svg .= '</div>';
        return $svg;
    }

    // -- pagina -------------------------------------------------------------

    public static function pagina() {
        if (!current_user_can('manage_options')) { return; }
        self::salva_config();
        $cfg = self::config();
        $configurado = $cfg['url'] && $cfg['chave'];

        echo '<div class="wrap radar-painel">';
        self::estilos();
        echo '<h1>Radar — ' . esc_html($cfg['site']) . '</h1>';

        if ($configurado) {
            $link = wp_nonce_url(add_query_arg('radar_atualizar', 1), 'radar_atualizar');
            echo '<p class="radar-mudo">Dados do Supabase, cache de ' . self::CACHE_TTL . 's. <a href="' . esc_url($link) . '">Atualizar agora</a></p>';
            $d = self::dados($cfg);
            self::secao_execucoes($d['execucoes']);
            self::secao_cotacoes($d['cotacoes']);
            self::secao_pautas($d['pautas'], $d['contagens']);
            self::secao_artigos($d['artigos']);
            self::script_grafico();
        } else {
            echo '<div class="notice notice-warning"><p>Preencha a configuração abaixo para o painel ler o Supabase.</p></div>';
        }

        self::secao_config($cfg, $configurado);
        echo '</div>';
    }

    private static function secao_execucoes($r) {
        echo '<div class="radar-cartao"><h2>Execuções dos crons</h2>';
        if ($r['erro']) {
            echo '<p class="radar-mudo">Não consegui ler a tabela <code>execucoes</code> (' . esc_html($r['erro']) . ').</p>';
        } elseif (empty($r['dados'])) {
            echo '<p class="radar-mudo">Nenhuma execução registrada ainda — a próxima rodada dos crons aparece aqui.</p>';
        } else {
            echo '<table class="widefat striped"><thead><tr><th>Fluxo</th><th>Status</th><th>Resumo</th><th>Quando</th><th>Duração</th></tr></thead><tbody>';
            foreach ($r['dados'] as $l) {
                echo '<tr><td>' . esc_html($l['fluxo']) . '</td>'
                    . '<td>' . self::selo($l['status']) . '</td>'
                    . '<td class="radar-mudo">' . esc_html(isset($l['resumo']) ? $l['resumo'] : '—') . '</td>'
                    . '<td>' . esc_html(self::quando($l['fim'])) . '</td>'
                    . '<td>' . esc_html(self::duracao($l['inicio'], $l['fim'])) . '</td></tr>';
            }
            echo '</tbody></table>';
        }
        echo '</div>';
    }

    private static function secao_cotacoes($r) {
        if ($r['erro'] || empty($r['dados'])) { return; } // site sem base de cotacoes
        $serie = array_reverse($r['dados']); // ordem crescente de data
        $n = count($serie);
        $atual = $serie[$n - 1];
        echo '<div class="radar-cartao"><h2>PTAX de venda — últimos ' . $n . ' pregões</h2>';
        echo '<p class="radar-heroi">' . esc_html(self::moeda($atual['ptax_venda']));
        if ($n > 1) {
            $anterior = (float) $serie[$n - 2]['ptax_venda'];
            $delta = ((float) $atual['ptax_venda'] / $anterior - 1) * 100;
            // delta em tom neutro de proposito: dolar subir nao e' "bom" nem "ruim"
            echo ' <span class="radar-delta">' . ($delta >= 0 ? '▲' : '▼') . ' ' . esc_html(self::pct($delta)) . ' ante o pregão anterior</span>';
        }
        // fatia a string 'AAAA-MM-DD' direto: strtotime + fuso empurraria o dia para tras
        $data_atual = substr($atual['data'], 8, 2) . '/' . substr($atual['data'], 5, 2) . '/' . substr($atual['data'], 0, 4);
        echo '<br><span class="radar-mudo">cotação de ' . esc_html($data_atual) . '</span></p>';
        echo self::grafico($serie);

        echo '<table class="widefat striped radar-tabela-num"><thead><tr><th>Data</th><th>Compra</th><th>Venda</th><th>Variação</th></tr></thead><tbody>';
        $recentes = array_slice(array_reverse($serie), 0, 10);
        foreach ($recentes as $i => $c) {
            $var = '—';
            if (isset($recentes[$i + 1])) {
                $var = self::pct(((float) $c['ptax_venda'] / (float) $recentes[$i + 1]['ptax_venda'] - 1) * 100);
            }
            echo '<tr><td>' . esc_html(substr($c['data'], 8, 2) . '/' . substr($c['data'], 5, 2)) . '</td>'
                . '<td>' . esc_html(self::moeda($c['ptax_compra'])) . '</td>'
                . '<td>' . esc_html(self::moeda($c['ptax_venda'])) . '</td>'
                . '<td class="radar-mudo">' . esc_html($var) . '</td></tr>';
        }
        echo '</tbody></table></div>';
    }

    private static function secao_pautas($r, $contagens) {
        echo '<div class="radar-cartao"><h2>Fila de pautas</h2>';
        if (!empty($contagens)) {
            echo '<p>';
            foreach ($contagens as $st => $total) {
                echo '<span class="radar-chip">' . esc_html($st) . ' <b>' . esc_html($total) . '</b></span> ';
            }
            echo '</p>';
        }
        if ($r['erro']) {
            echo '<p class="radar-mudo">Não consegui ler as pautas (' . esc_html($r['erro']) . ').</p>';
        } elseif (empty($r['dados'])) {
            echo '<p class="radar-mudo">Nenhuma pauta ainda — elas surgem quando o radar coleta algo relevante.</p>';
        } else {
            echo '<table class="widefat striped"><thead><tr><th>Pauta sugerida</th><th>Ângulo</th><th>Hub</th><th>Status</th><th>Quando</th></tr></thead><tbody>';
            foreach ($r['dados'] as $p) {
                $item = isset($p['itens']) && is_array($p['itens']) ? $p['itens'] : array();
                $titulo = !empty($p['titulo_sug']) ? $p['titulo_sug'] : (isset($item['titulo']) ? $item['titulo'] : '—');
                echo '<tr><td>' . esc_html($titulo);
                if (!empty($p['dado_proprio'])) {
                    echo '<br><span class="radar-mudo">dado próprio: ' . esc_html($p['dado_proprio']) . '</span>';
                }
                if (!empty($item['url'])) {
                    echo '<br><span class="radar-mudo">origem: <a href="' . esc_url($item['url']) . '" target="_blank" rel="noreferrer">'
                        . esc_html(!empty($item['veiculo']) ? $item['veiculo'] : 'link') . '</a></span>';
                }
                echo '</td><td class="radar-mudo">' . esc_html($p['angulo']) . '</td>'
                    . '<td class="radar-mudo">' . esc_html(!empty($p['hub']) ? $p['hub'] : '—') . '</td>'
                    . '<td>' . self::selo($p['status']) . '</td>'
                    . '<td class="radar-mudo">' . esc_html(self::quando($p['criado_em'])) . '</td></tr>';
            }
            echo '</tbody></table>';
        }
        echo '</div>';
    }

    private static function secao_artigos($r) {
        if ($r['erro'] || empty($r['dados'])) { return; }
        echo '<div class="radar-cartao"><h2>Artigos gerados</h2>';
        echo '<table class="widefat striped"><thead><tr><th>Título</th><th>Tipo</th><th>Status</th><th>Portão</th><th>Quando</th></tr></thead><tbody>';
        foreach ($r['dados'] as $a) {
            echo '<tr><td>';
            if (!empty($a['url_publicada'])) {
                echo '<a href="' . esc_url($a['url_publicada']) . '" target="_blank" rel="noreferrer">' . esc_html($a['titulo']) . '</a>';
            } else {
                echo esc_html($a['titulo']);
            }
            echo '</td><td class="radar-mudo">' . esc_html($a['tipo']) . '</td>'
                . '<td>' . self::selo($a['status']) . '</td>'
                . '<td class="radar-mudo">' . esc_html(!empty($a['motivo_portao']) ? $a['motivo_portao'] : '—') . '</td>'
                . '<td class="radar-mudo">' . esc_html(self::quando($a['criado_em'])) . '</td></tr>';
        }
        echo '</tbody></table></div>';
    }

    private static function secao_config($cfg, $configurado) {
        $constantes = defined('RADAR_SUPABASE_URL') || defined('RADAR_SUPABASE_CHAVE');
        echo '<details class="radar-cartao"' . ($configurado ? '' : ' open') . '><summary><b>Configuração</b></summary>';
        if ($constantes) {
            echo '<p class="radar-mudo">Definida por constantes no wp-config.php — os campos abaixo são ignorados.</p>';
        }
        echo '<form method="post">';
        wp_nonce_field('radar_painel_salvar', 'radar_painel_nonce');
        echo '<table class="form-table">';
        echo '<tr><th><label for="radar_url">URL do Supabase</label></th><td><input type="url" id="radar_url" name="radar_url" class="regular-text" value="' . esc_attr($cfg['url']) . '" placeholder="https://xxxx.supabase.co"></td></tr>';
        echo '<tr><th><label for="radar_chave">Service key</label></th><td><input type="password" id="radar_chave" name="radar_chave" class="regular-text" value="" placeholder="' . ($cfg['chave'] ? 'definida — deixe vazio para manter' : 'cole a service_role key') . '"><p class="description">Fica só no servidor; o navegador nunca a recebe.</p></td></tr>';
        echo '<tr><th><label for="radar_site">Site (id no sites.yaml)</label></th><td><input type="text" id="radar_site" name="radar_site" class="regular-text" value="' . esc_attr($cfg['site']) . '"></td></tr>';
        echo '</table>';
        submit_button('Salvar');
        echo '</form></details>';
    }

    private static function estilos() {
        echo '<style>
        .radar-painel .radar-cartao { background: #fff; border: 1px solid #dcdcde; border-radius: 8px; padding: 16px 20px; margin: 16px 0; max-width: 960px; }
        .radar-painel h2 { margin-top: 0; }
        .radar-painel .radar-mudo { color: #646970; }
        .radar-painel .radar-heroi { font-size: 28px; font-weight: 700; margin: 4px 0 12px; }
        .radar-painel .radar-delta { font-size: 14px; font-weight: 400; color: #50575e; }
        .radar-painel .radar-selo { display: inline-block; padding: 0 8px; border-radius: 999px; font-size: 12px; font-weight: 600; border: 1px solid #dcdcde; white-space: nowrap; }
        .radar-painel .radar-selo-bom { color: #006300; border-color: #9ed99e; }
        .radar-painel .radar-selo-alerta { background: #fdf0d5; border-color: #f0c33c; }
        .radar-painel .radar-selo-critico { color: #d03b3b; border-color: #ebb1b1; }
        .radar-painel .radar-selo-info { color: #2a78d6; border-color: #a9c9ef; }
        .radar-painel .radar-selo-neutro { color: #646970; }
        .radar-painel .radar-chip { display: inline-block; padding: 1px 10px; border: 1px solid #dcdcde; border-radius: 999px; font-size: 13px; color: #50575e; margin-right: 6px; }
        .radar-painel .radar-tabela-num td:nth-child(n+2) { font-variant-numeric: tabular-nums; }
        .radar-painel .radar-grafico-envelope { position: relative; max-width: 760px; margin-bottom: 16px; }
        .radar-painel .radar-grafico-envelope svg { display: block; width: 100%; height: auto; }
        .radar-painel .radar-dica { position: absolute; transform: translate(-50%, -100%); background: #fff; border: 1px solid #dcdcde; border-radius: 6px; padding: 6px 10px; font-size: 13px; pointer-events: none; white-space: nowrap; box-shadow: 0 4px 14px rgba(0,0,0,.12); }
        </style>';
    }

    private static function script_grafico() {
        // Crosshair + dica no hover, mapeando o mouse para o ponto mais proximo.
        echo '<script>
        (function () {
            var svg = document.getElementById("radar-grafico");
            if (!svg) { return; }
            var pontos = JSON.parse(svg.dataset.pontos);
            var caixaViva = svg.viewBox.baseVal;
            var mira = document.getElementById("radar-mira");
            var ponto = document.getElementById("radar-ponto");
            var dica = document.getElementById("radar-dica");
            svg.addEventListener("mousemove", function (e) {
                var caixa = svg.getBoundingClientRect();
                var xVista = (e.clientX - caixa.left) / caixa.width * caixaViva.width;
                var perto = 0, dist = Infinity;
                pontos.forEach(function (p, i) {
                    var d = Math.abs(p.x - xVista);
                    if (d < dist) { dist = d; perto = i; }
                });
                var p = pontos[perto];
                mira.setAttribute("x1", p.x); mira.setAttribute("x2", p.x); mira.style.display = "";
                ponto.setAttribute("cx", p.x); ponto.setAttribute("cy", p.y); ponto.style.display = "";
                dica.style.display = "";
                dica.style.left = (p.x / caixaViva.width * 100) + "%";
                dica.style.top = (p.y / caixaViva.height * 100 - 6) + "%";
                dica.innerHTML = "<span style=\"color:#646970;font-size:12px\">" + p.data + "</span><br>venda " + p.venda + "<br>compra " + p.compra;
            });
            svg.addEventListener("mouseleave", function () {
                mira.style.display = "none"; ponto.style.display = "none"; dica.style.display = "none";
            });
        })();
        </script>';
    }
}

Radar_Painel::inicia();
