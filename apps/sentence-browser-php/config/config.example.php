<?php

return [
    'app' => [
        'name' => 'Sentence Browser',
        'env' => 'local',
        'base_path' => '/apps/sentence-browser-php/public',
        'admin_token' => 'change-me',
    ],
    'db' => [
        'host' => '127.0.0.1',
        'port' => 3306,
        'name' => 'sentence_browser',
        'user' => 'root',
        'pass' => '',
        'charset' => 'utf8mb4',
    ],
    'audio' => [
        // Base URL used for local-audio field (`sounds`) playback/download in the UI.
        // Keep relative path in local dev, set a full CDN/object-storage URL in production.
        'local_base_url' => 'audio/',
    ],
];
