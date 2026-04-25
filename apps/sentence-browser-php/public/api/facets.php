<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/src/bootstrap.php';
require_once dirname(__DIR__, 2) . '/src/Db.php';
require_once dirname(__DIR__, 2) . '/src/SentenceRepository.php';

try {
    $config = sb_load_config();
    $db = new Db($config);
    $repo = new SentenceRepository($db->pdo());
    sb_json($repo->getFacets());
} catch (Throwable $e) {
    sb_error('Server error: ' . $e->getMessage(), 500);
}
