<?php

declare(strict_types=1);

class Db
{
    private PDO $pdo;

    public function __construct(array $config)
    {
        $db = $config['db'] ?? [];
        $host = $db['host'] ?? '127.0.0.1';
        $port = (int)($db['port'] ?? 3306);
        $name = $db['name'] ?? '';
        $user = $db['user'] ?? '';
        $pass = $db['pass'] ?? '';
        $charset = $db['charset'] ?? 'utf8mb4';

        $dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=%s', $host, $port, $name, $charset);
        $this->pdo = new PDO($dsn, $user, $pass, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false,
        ]);
    }

    public function pdo(): PDO
    {
        return $this->pdo;
    }
}
