package shop;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;
import org.junit.jupiter.api.Test;

class PriceCalculatorTest {
    @Test
    void totalInEuros() {
        var lines = List.of(new PriceCalculator.Line(10.0, 2), new PriceCalculator.Line(2.5, 1));
        assertEquals(22.5, new PriceCalculator().total(lines), 1e-9);
    }
}
