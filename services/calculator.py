
from decimal import Decimal, InvalidOperation


def parse_numbers(text, minimum=1, maximum=50):
    """Parse space-separated decimal numbers safely."""

    parts = text.strip().split()

    if not minimum <= len(parts) <= maximum:
        raise ValueError(
            f"Enter between {minimum} and {maximum} numbers."
        )

    numbers = []

    try:
        for part in parts:
            number = Decimal(part)

            if not number.is_finite():
                raise ValueError("Enter valid finite numbers.")

            numbers.append(number)

    except InvalidOperation:
        raise ValueError(
            "Invalid number. Use digits and decimal points."
        )

    return numbers


def format_money(value):
    """Format a Decimal value to two decimal places."""

    return f"{value:,.2f} ETB"


def calculate_profit(cost, selling_price):
    """Calculate profit, loss, margin and markup."""

    if cost < 0 or selling_price < 0:
        raise ValueError("Prices cannot be negative.")

    difference = selling_price - cost

    if difference > 0:
        status = "profit"
    elif difference < 0:
        status = "loss"
    else:
        status = "break_even"

    margin = (
        (difference / selling_price) * 100
        if selling_price != 0
        else Decimal("0")
    )

    markup = (
        (difference / cost) * 100
        if cost != 0
        else Decimal("0")
    )

    return {
        "status": status,
        "difference": difference,
        "margin": margin,
        "markup": markup
    }


def calculate_percentage(amount, percentage):
    """Calculate a percentage of an amount."""

    if amount < 0 or percentage < 0:
        raise ValueError("Values cannot be negative.")

    return amount * percentage / Decimal("100")


def calculate_discount(original_price, discount_percentage):
    """Calculate discount savings and final price."""

    if original_price < 0:
        raise ValueError("Price cannot be negative.")

    if not Decimal("0") <= discount_percentage <= Decimal("100"):
        raise ValueError("Discount must be between 0 and 100.")

    savings = (
        original_price * discount_percentage / Decimal("100")
    )

    final_price = original_price - savings

    return {
        "savings": savings,
        "final_price": final_price
    }


def calculate_expenses(expenses):
    """Calculate expense total, average and count."""

    if not expenses:
        raise ValueError("Enter at least one expense.")

    if any(expense < 0 for expense in expenses):
        raise ValueError("Expenses cannot be negative.")

    total = sum(expenses, Decimal("0"))

    average = total / Decimal(len(expenses))

    return {
        "total": total,
        "average": average,
        "count": len(expenses)
    }
