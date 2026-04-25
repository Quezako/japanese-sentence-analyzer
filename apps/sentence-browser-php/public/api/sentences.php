<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/src/bootstrap.php';
require_once dirname(__DIR__, 2) . '/src/Db.php';
require_once dirname(__DIR__, 2) . '/src/SentenceRepository.php';

try {
    $config = sb_load_config();
    $db = new Db($config);
    $repo = new SentenceRepository($db->pdo());

    $payload = $repo->search([
        'q'                  => trim((string)($_GET['q'] ?? '')),
        'english_q'          => trim((string)($_GET['english_q'] ?? '')),
        'grammar_details_q'  => trim((string)($_GET['grammar_details_q'] ?? '')),
        'jlpt_no_katakana'   => sb_input_array('jlpt_no_katakana'),
        'vocab_jlpt_pedagogical' => sb_input_array('vocab_jlpt_pedagogical'),
        'vocab_jlpt_strict'      => sb_input_array('vocab_jlpt_strict'),
        'grammar_jlpt'       => sb_input_array('grammar_jlpt'),
        'kanji_jlpt'         => sb_input_array('kanji_jlpt'),
        'JLPT_origin'        => sb_input_array('JLPT_origin'),
        'tags'               => sb_input_array('tags'),
        'char_len_min'       => $_GET['char_len_min'] ?? '',
        'char_len_max'       => $_GET['char_len_max'] ?? '',
        'sort_by'            => $_GET['sort_by'] ?? 'id',
        'sort_dir'           => $_GET['sort_dir'] ?? 'asc',
        'page'               => $_GET['page'] ?? 1,
        'page_size'          => $_GET['page_size'] ?? 50,
    ]);

    sb_json($payload);
} catch (Throwable $e) {
    sb_error('Server error: ' . $e->getMessage(), 500);
}
