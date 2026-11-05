package shop;

import java.util.List;

public final class PriceCalculator {
    public record Line(double price, int qty) {}

    public double total(List<Line> lines) {
        return lines.stream().mapToDouble(l -> l.price() * l.qty()).sum();
    }
}
