import unittest
from decimal import Decimal

from services.calculator import (
    parse_numbers,
    calculate_profit,
    calculate_percentage,
    calculate_discount,
    calculate_expenses,
    format_money,
)


class TestNumberParsing(unittest.TestCase):

    def test_parse_valid_numbers(self):
        self.assertEqual(
            parse_numbers("100 250.50 300"),
            [Decimal("100"), Decimal("250.50"), Decimal("300")]
        )

    def test_reject_empty_input(self):
        with self.assertRaises(ValueError):
            parse_numbers("")

    def test_reject_invalid_number(self):
        with self.assertRaises(ValueError):
            parse_numbers("100 abc")

    def test_reject_non_finite_numbers(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_numbers(value)

    def test_reject_too_many_numbers(self):
        with self.assertRaises(ValueError):
            parse_numbers(" ".join(["1"] * 51))


class TestProfitCalculator(unittest.TestCase):

    def test_profit(self):
        result = calculate_profit(
            Decimal("100"), Decimal("150")
        )
        self.assertEqual(result["status"], "profit")
        self.assertEqual(result["difference"], Decimal("50"))

    def test_loss(self):
        result = calculate_profit(
            Decimal("150"), Decimal("100")
        )
        self.assertEqual(result["status"], "loss")
        self.assertEqual(result["difference"], Decimal("-50"))

    def test_break_even(self):
        result = calculate_profit(
            Decimal("100"), Decimal("100")
        )
        self.assertEqual(result["status"], "break_even")
        self.assertEqual(result["difference"], Decimal("0"))

    def test_zero_cost(self):
        result = calculate_profit(
            Decimal("0"), Decimal("100")
        )
        self.assertEqual(result["markup"], Decimal("0"))

    def test_negative_prices_rejected(self):
        with self.assertRaises(ValueError):
            calculate_profit(
                Decimal("-10"), Decimal("100")
            )


class TestPercentageCalculator(unittest.TestCase):

    def test_percentage_calculation(self):
        result = calculate_percentage(
            Decimal("1000"), Decimal("15")
        )
        self.assertEqual(result, Decimal("150"))

    def test_zero_percentage(self):
        result = calculate_percentage(
            Decimal("1000"), Decimal("0")
        )
        self.assertEqual(result, Decimal("0"))

    def test_negative_values_rejected(self):
        with self.assertRaises(ValueError):
            calculate_percentage(
                Decimal("100"), Decimal("-5")
            )


class TestDiscountCalculator(unittest.TestCase):

    def test_discount_calculation(self):
        result = calculate_discount(
            Decimal("2000"), Decimal("10")
        )
        self.assertEqual(result["savings"], Decimal("200"))
        self.assertEqual(result["final_price"], Decimal("1800"))

    def test_full_discount(self):
        result = calculate_discount(
            Decimal("500"), Decimal("100")
        )
        self.assertEqual(result["final_price"], Decimal("0"))

    def test_zero_discount(self):
        result = calculate_discount(
            Decimal("500"), Decimal("0")
        )
        self.assertEqual(result["savings"], Decimal("0"))
        self.assertEqual(result["final_price"], Decimal("500"))

    def test_discount_above_100_rejected(self):
        with self.assertRaises(ValueError):
            calculate_discount(
                Decimal("500"), Decimal("101")
            )


class TestExpenseCalculator(unittest.TestCase):

    def test_expense_summary(self):
        result = calculate_expenses([
            Decimal("100"),
            Decimal("250"),
            Decimal("300")
        ])
        self.assertEqual(result["total"], Decimal("650"))
        self.assertEqual(result["count"], 3)
        self.assertEqual(
            result["average"],
            Decimal("650") / Decimal("3")
        )

    def test_empty_expenses_rejected(self):
        with self.assertRaises(ValueError):
            calculate_expenses([])

    def test_negative_expenses_rejected(self):
        with self.assertRaises(ValueError):
            calculate_expenses([
                Decimal("100"), Decimal("-50")
            ])


class TestMoneyFormatting(unittest.TestCase):

    def test_format_money(self):
        self.assertEqual(
            format_money(Decimal("1250.5")),
            "1,250.50 ETB"
        )


if __name__ == "__main__":
    unittest.main()
