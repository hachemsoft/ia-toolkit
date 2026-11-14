<?php

declare(strict_types=1);

use App\TokenVerifier;
use PHPUnit\Framework\TestCase;

final class TokenVerifierTest extends TestCase
{
    public function testAcceptsTheRightToken(): void
    {
        $verifier = new TokenVerifier(['t1' => hash('sha256', 'secret')]);
        self::assertTrue($verifier->verify('t1', 'secret'));
    }
}
