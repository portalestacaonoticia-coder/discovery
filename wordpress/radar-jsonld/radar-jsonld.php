<?php
/**
 * Plugin Name: Radar — JSON-LD e meta de noticia
 * Description: Registra o campo usado pelo radar e imprime o JSON-LD no <head>.
 * Version: 1.0.0
 * Author: Radar
 *
 * Instalar por Plugins -> Adicionar novo -> Enviar plugin, e ativar.
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
