# Shop pricing

Small Java library: `PriceCalculator` computes order totals for the shop's checkout service, which depends on it.

## Verifying your work
| Stack | Changed | Full |
| --- | --- | --- |
| Java (Maven) | `mvn -q test -Dtest=PriceCalculatorTest` | `mvn -q verify` |

## Conventions
- `PriceCalculator` is a published API: the checkout service calls `total(List<Line>)` and reads a `double`.
