<?php
/**
 * Plugin Name: Radar — JSON-LD e meta de noticia
 * Description: Registra o campo usado pelo radar e imprime o JSON-LD no <head>.
 *              Colocar em wp-content/mu-plugins/ (cria a pasta se nao existir).
 *              Em mu-plugins nao precisa ativar e nao some em atualizacao de tema.
 */

// Sem register_meta com show_in_rest, a REST API ignora o campo silenciosamente.
add_action('init', function () {
    register_meta('post', 'radar_jsonld', [
        'type'         => 'string',
        'single'       => true,
        'show_in_rest' => true,
        'auth_callback'=> function () { return current_user_can('edit_posts'); },
    ]);
});

add_action('wp_head', function () {
    if (!is_singular('post')) return;
    $jsonld = get_post_meta(get_the_ID(), 'radar_jsonld', true);
    if (!$jsonld) return;
    echo "\n<script type=\"application/ld+json\">" . $jsonld . "</script>\n";
}, 20);

// max-snippet:-1 libera trecho longo — e' o que os motores de IA extraem.
// max-image-preview:large e' pre-requisito pratico do Discover.
add_filter('wp_robots', function ($robots) {
    $robots['max-image-preview'] = 'large';
    $robots['max-snippet']       = '-1';
    $robots['max-video-preview'] = '-1';
    return $robots;
});

// og:image de reserva. Com Rank Math/Yoast no ar, eles ja' imprimem o og:image
// da imagem destacada e este bloco sai de cena (duas tags confundem o rastreador).
// Sem plugin de SEO, e' isto que entrega a imagem ao Discover.
add_action('wp_head', function () {
    if (!is_singular('post')) return;
    if (defined('RANK_MATH_VERSION') || defined('WPSEO_VERSION')) return;
    if (!has_post_thumbnail()) return;

    // 'full' de proposito: o Discover exige >= 1200px de largura, e os
    // tamanhos intermediarios do WP ficam abaixo disso.
    $img = wp_get_attachment_image_src(get_post_thumbnail_id(), 'full');
    if (!$img) return;

    printf(
        "\n<meta property=\"og:image\" content=\"%s\" />\n"
        . "<meta property=\"og:image:width\" content=\"%d\" />\n"
        . "<meta property=\"og:image:height\" content=\"%d\" />\n"
        . "<meta name=\"twitter:card\" content=\"summary_large_image\" />\n",
        esc_url($img[0]), (int) $img[1], (int) $img[2]
    );
}, 5);
