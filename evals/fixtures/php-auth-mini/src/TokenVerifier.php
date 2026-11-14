<?php

declare(strict_types=1);

namespace App;

final class TokenVerifier
{
    /** @param array<string, string> $storedHashes token id => sha256 of the token */
    public function __construct(private array $storedHashes)
    {
    }

    public function verify(string $tokenId, string $token): bool
    {
        $stored = $this->storedHashes[$tokenId] ?? null;
        if ($stored === null) {
            return false;
        }

        return hash_equals($stored, hash('sha256', $token));
    }
}
