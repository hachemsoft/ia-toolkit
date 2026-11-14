<?php

declare(strict_types=1);

namespace Billing;

final class Invoice
{
    public function __construct(public readonly int $amountCents)
    {
    }
}
