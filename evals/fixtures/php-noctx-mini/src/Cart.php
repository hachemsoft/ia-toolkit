<?php

declare(strict_types=1);

namespace App;

final class Cart
{
    /** @var array<string, int> sku => quantity */
    private array $lines = [];

    public function add(string $sku, int $quantity): void
    {
        $this->lines[$sku] = ($this->lines[$sku] ?? 0) + $quantity;
    }

    public function count(): int
    {
        return array_sum($this->lines);
    }
}
