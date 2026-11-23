"""Errors raised while evaluating expressions and variables."""


class ExpressionError(ValueError):
    """The text could not be evaluated. The message says what is wrong and how to fix it."""


class CircularReferenceError(ExpressionError):
    """Variables refer to each other in a loop."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        path = " -> ".join([*cycle, cycle[0]])
        super().__init__(f"Circular reference: {path}. Change one of these variables.")
