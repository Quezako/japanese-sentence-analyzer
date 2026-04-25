<?php

declare(strict_types=1);

function sb_project_root(): string
{
    return dirname(__DIR__);
}

function sb_load_config(): array
{
    $env = getenv('APP_ENV') ?: 'local';
    $configPath = sb_project_root() . '/config/config.' . $env . '.php';
    if (!file_exists($configPath)) {
        $configPath = sb_project_root() . '/config/config.local.php';
    }
    if (!file_exists($configPath)) {
        $configPath = sb_project_root() . '/config/config.example.php';
    }
    $config = require $configPath;
    if (!is_array($config)) {
        throw new RuntimeException('Invalid config file: ' . $configPath);
    }
    return $config;
}

function sb_json(array $payload, int $status = 200): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function sb_error(string $message, int $status = 400): void
{
    sb_json(['error' => $message], $status);
}

function sb_input_array(string $key): array
{
    if (!isset($_GET[$key])) {
        return [];
    }
    $value = $_GET[$key];
    if (is_array($value)) {
        return array_values(array_filter(array_map('strval', $value), fn($v) => $v !== ''));
    }
    $raw = trim((string)$value);
    if ($raw === '') {
        return [];
    }
    return array_values(array_filter(array_map('trim', explode(',', $raw)), fn($v) => $v !== ''));
}
