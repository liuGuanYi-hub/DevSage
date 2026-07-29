<?php

namespace App\Http\Middleware;

class Authenticate
{
    public function handle(array $headers): bool
    {
        $authorization = $headers['Authorization'] ?? '';

        return str_starts_with($authorization, 'Bearer ')
            && trim(substr($authorization, 7)) !== '';
    }
}

