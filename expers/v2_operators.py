"""Очевидные Python-операторы строят новые узлы Deferred-графа."""

from dataclasses import dataclass

import evalcache


@dataclass(frozen=True)
class Matrix:
    value: int

    def __evalcache_key__(self) -> bytes:
        return str(self.value).encode("ascii")

    def __matmul__(self, other):
        if not isinstance(other, Matrix):
            return NotImplemented
        return Matrix(self.value * other.value)


def main() -> None:
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
    )

    @evaluator
    def load_numbers() -> tuple[int, ...]:
        print("Загружается набор чисел")
        return (6, -4, 3)

    @evaluator
    def make_matrix(value: int) -> Matrix:
        return Matrix(value)

    numbers = load_numbers()

    # [], reflected +, *, - и abs создают узлы, не раскрывая load_numbers.
    arithmetic = 10 + numbers[0] * 2 - abs(numbers[1])
    bit_mask = (numbers[2] | 0b1000) & 0b1110
    matrix_product = make_matrix(6) @ make_matrix(7)

    assert isinstance(arithmetic, evalcache.Deferred)
    assert arithmetic.compute() == 18
    assert bit_mask.compute() == 10
    assert matrix_product.compute() == Matrix(42)

    print("Арифметика:", arithmetic.compute())
    print("Битовая маска:", bit_mask.compute())
    print("Матричное умножение:", matrix_product.compute())


if __name__ == "__main__":
    main()
