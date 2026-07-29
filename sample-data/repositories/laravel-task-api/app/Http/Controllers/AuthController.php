<?php

namespace App\Http\Controllers;

class AuthController
{
    public function login(array $credentials): array
    {
        if ($credentials['email'] !== 'demo@example.test') {
            return ['ok' => false, 'message' => 'Invalid credentials'];
        }

        return [
            'ok' => true,
            'token_type' => 'Bearer',
            'access_token' => 'sample-token-value',
        ];
    }
}

