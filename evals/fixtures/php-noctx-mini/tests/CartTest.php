<?php

declare(strict_types=1);

use App\Cart;
use PHPUnit\Framework\TestCase;

final class CartTest extends TestCase
{
    public function testCountsQuantities(): void
    {
        $cart = new Cart();
        $cart->add('a', 2);
        $cart->add('a', 1);
        self::assertSame(3, $cart->count());
    }
}
