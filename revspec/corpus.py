"""
revspec.corpus
==============
A labelled corpus of classical integer sequences.

Every sequence is GENERATED from its definition (never transcribed), and is
labelled with its ground-truth position in the holonomic hierarchy:

    POLY  subset of  CFIN  subset of  PREC  subset of  (all sequences)

    POLY : polynomial closed form in n
    CFIN : C-finite (constant-coefficient linear recurrence) but not polynomial
    PREC : P-recursive / holonomic (polynomial-coefficient) but not C-finite
    NONH : provably not P-recursive

The NONH labels rest on standard results: the primes, the partition numbers,
the Bell numbers, the ordered Bell (Fubini) numbers and the classical
multiplicative functions (d, sigma, phi) are all known not to be holonomic.
The Hofstadter, Kolakoski and Recaman sequences are not given by any linear
recurrence with polynomial coefficients.

OEIS A-numbers are given for cross-reference; they are not needed to run the
experiments, since all values are computed here from first principles.
"""

from __future__ import annotations

from functools import lru_cache
from math import comb, factorial, gcd

from sympy import bell, divisor_count, divisor_sigma, npartitions, prime, totient

N_TERMS = 34  # default corpus length


# --------------------------------------------------------------------------- #
# generators
# --------------------------------------------------------------------------- #

def _linrec(init, coef, n):
    """a(k) = sum_i coef[i] * a(k-1-i), seeded with init."""
    s = list(init)
    while len(s) < n:
        s.append(sum(c * s[-1 - i] for i, c in enumerate(coef)))
    return s[:n]


def _kolakoski(n):
    s = [1, 2, 2]
    i = 2
    while len(s) < n:
        nxt = 1 if s[-1] == 2 else 2
        s.extend([nxt] * s[i])
        i += 1
    return s[:n]


def _recaman(n):
    s, seen, cur = [0], {0}, 0
    for k in range(1, n):
        back = cur - k
        cur = back if back > 0 and back not in seen else cur + k
        seen.add(cur)
        s.append(cur)
    return s[:n]


def _hofstadter_q(n):
    s = [1, 1]
    while len(s) < n:
        k = len(s)
        s.append(s[k - s[k - 1]] + s[k - s[k - 2]])
    return s[:n]


def _conway(n):
    s = [1, 1]
    while len(s) < n:
        k = len(s)
        s.append(s[s[k - 1] - 1] + s[k - s[k - 1]])
    return s[:n]


def _collatz_steps(k):
    c = 0
    while k != 1:
        k = k // 2 if k % 2 == 0 else 3 * k + 1
        c += 1
    return c


def _motzkin(n):
    s = [1, 1]
    for k in range(2, n):
        s.append(((2 * k + 1) * s[k - 1] + (3 * k - 3) * s[k - 2]) // (k + 2))
    return s[:n]


def _riordan(n):
    s = [1, 0]
    for k in range(2, n):
        s.append((k - 1) * (2 * s[k - 1] + 3 * s[k - 2]) // (k + 1))
    return s[:n]


def _derangements(n):
    s = [1, 0]
    for k in range(2, n):
        s.append((k - 1) * (s[k - 1] + s[k - 2]))
    return s[:n]


def _involutions(n):
    s = [1, 1]
    for k in range(2, n):
        s.append(s[k - 1] + (k - 1) * s[k - 2])
    return s[:n]


def _a000255(n):
    s = [1, 1]
    for k in range(2, n):
        s.append(k * s[k - 1] + (k - 1) * s[k - 2])
    return s[:n]


def _a002720(n):
    s = [1, 2]
    for k in range(2, n):
        s.append(2 * k * s[k - 1] - (k - 1) ** 2 * s[k - 2])
    return s[:n]


# --------------------------------------------------------------------------- #
# the corpus
# --------------------------------------------------------------------------- #

def build_corpus(n: int = N_TERMS) -> list[dict]:
    """Return the labelled corpus as a list of dicts."""
    R = range(n)
    C: list[dict] = []

    def add(anum, name, cls, vals):
        C.append({"anum": anum, "name": name, "true_class": cls,
                  "seq": [int(v) for v in vals[:n]]})

    # ---------------- POLY : polynomial closed form ------------------------ #
    add("A000027", "naturals",            "POLY", [k + 1 for k in R])
    add("A005843", "even numbers",        "POLY", [2 * k for k in R])
    add("A005408", "odd numbers",         "POLY", [2 * k + 1 for k in R])
    add("A000217", "triangular",          "POLY", [k * (k + 1) // 2 for k in R])
    add("A000290", "squares",             "POLY", [k * k for k in R])
    add("A002378", "oblong",              "POLY", [k * (k + 1) for k in R])
    add("A000578", "cubes",               "POLY", [k ** 3 for k in R])
    add("A000292", "tetrahedral",         "POLY", [k * (k + 1) * (k + 2) // 6 for k in R])
    add("A000326", "pentagonal",          "POLY", [k * (3 * k - 1) // 2 for k in R])
    add("A000384", "hexagonal",           "POLY", [k * (2 * k - 1) for k in R])
    add("A002061", "central polygonal",   "POLY", [k * k - k + 1 for k in R])
    add("A000583", "fourth powers",       "POLY", [k ** 4 for k in R])
    add("A005563", "n(n+2)",              "POLY", [k * (k + 2) for k in R])
    add("A001105", "2n^2",                "POLY", [2 * k * k for k in R])
    add("A000330", "square pyramidal",    "POLY", [k * (k + 1) * (2 * k + 1) // 6 for k in R])

    # ---------------- CFIN : C-finite, not polynomial ---------------------- #
    add("A000045", "Fibonacci",           "CFIN", _linrec([0, 1], [1, 1], n))
    add("A000032", "Lucas",               "CFIN", _linrec([2, 1], [1, 1], n))
    add("A000129", "Pell",                "CFIN", _linrec([0, 1], [2, 1], n))
    add("A001333", "NSW / Pell-Lucas",    "CFIN", _linrec([1, 1], [2, 1], n))
    add("A001045", "Jacobsthal",          "CFIN", _linrec([0, 1], [1, 2], n))
    add("A000073", "Tribonacci",          "CFIN", _linrec([0, 0, 1], [1, 1, 1], n))
    add("A000931", "Padovan",             "CFIN", _linrec([1, 0, 0], [0, 1, 1], n))
    add("A001608", "Perrin",              "CFIN", _linrec([3, 0, 2], [0, 1, 1], n))
    add("A000079", "powers of 2",         "CFIN", [2 ** k for k in R])
    add("A000244", "powers of 3",         "CFIN", [3 ** k for k in R])
    add("A000302", "powers of 4",         "CFIN", [4 ** k for k in R])
    add("A000225", "Mersenne 2^n-1",      "CFIN", [2 ** k - 1 for k in R])
    add("A002605", "a=2a+2a",             "CFIN", _linrec([0, 1], [2, 2], n))
    add("A006190", "a=3a+a",              "CFIN", _linrec([0, 1], [3, 1], n))
    add("A001519", "odd-index Fibonacci", "CFIN", _linrec([1, 1], [3, -1], n))
    add("A000225b", "3^n - 2^n",          "CFIN", [3 ** k - 2 ** k for k in R])

    # ---------------- PREC : holonomic, not C-finite ----------------------- #
    add("A000142", "factorial",           "PREC", [factorial(k) for k in R])
    add("A000108", "Catalan",             "PREC", [comb(2 * k, k) // (k + 1) for k in R])
    add("A000984", "central binomial",    "PREC", [comb(2 * k, k) for k in R])
    add("A000166", "derangements",        "PREC", _derangements(n))
    add("A001006", "Motzkin",             "PREC", _motzkin(n))
    add("A005043", "Riordan",             "PREC", _riordan(n))
    add("A000085", "involutions",         "PREC", _involutions(n))
    add("A001147", "double factorial !!", "PREC", [factorial(2 * k) // (2 ** k * factorial(k)) for k in R])
    add("A000255", "permutations A000255","PREC", _a000255(n))
    add("A002720", "A002720",             "PREC", _a002720(n))
    add("A000165", "2^n n!",              "PREC", [2 ** k * factorial(k) for k in R])
    add("A001813", "(2n)!/n!",            "PREC", [factorial(2 * k) // factorial(k) for k in R])
    add("A001764", "binom(3n,n)/(2n+1)",  "PREC", [comb(3 * k, k) // (2 * k + 1) for k in R])
    add("A000407", "(2n+1)!/n!",          "PREC", [factorial(2 * k + 1) // factorial(k) for k in R])
    add("A006882", "n!!",                 "PREC", [__import__("math").prod(range(k, 0, -2)) or 1 for k in R])

    # ---------------- NONH : not P-recursive ------------------------------- #
    add("A000040", "primes",              "NONH", [int(prime(k + 1)) for k in R])
    add("A000041", "partitions p(n)",     "NONH", [int(npartitions(k)) for k in R])
    add("A000009", "distinct partitions", "NONH", _distinct_partitions(n))
    add("A000110", "Bell",                "NONH", [int(bell(k)) for k in R])
    add("A000670", "Fubini / ordered Bell","NONH", _fubini(n))
    add("A000005", "number of divisors",  "NONH", [int(divisor_count(k + 1)) for k in R])
    add("A000010", "Euler phi",           "NONH", [int(totient(k + 1)) for k in R])
    add("A000203", "sigma",               "NONH", [int(divisor_sigma(k + 1)) for k in R])
    add("A002110", "primorial",           "NONH", _primorial(n))
    add("A000720", "pi(n)",               "NONH", _prime_counting(n))
    add("A005132", "Recaman",             "NONH", _recaman(n))
    add("A000002", "Kolakoski",           "NONH", _kolakoski(n))
    add("A006577", "Collatz steps",       "NONH", [_collatz_steps(k + 1) for k in R])
    add("A005185", "Hofstadter Q",        "NONH", _hofstadter_q(n))
    add("A004001", "Hofstadter-Conway",   "NONH", _conway(n))

    return C


def _distinct_partitions(n):
    q = [1] + [0] * (n + 5)
    for part in range(1, n + 5):
        for tot in range(n + 4, part - 1, -1):
            q[tot] += q[tot - part]
    return q[:n]


def _fubini(n):
    """Ordered Bell numbers: a(0)=1, a(k) = sum_{j=1..k} C(k,j) a(k-j)."""
    out = [1]
    for k in range(1, n):
        out.append(sum(comb(k, j) * out[k - j] for j in range(1, k + 1)))
    return out[:n]


def _primorial(n):
    out, p = [], 1
    for k in range(n):
        if k == 0:
            out.append(1)
        else:
            p *= int(prime(k))
            out.append(p)
    return out


def _prime_counting(n):
    from sympy import primepi
    return [int(primepi(k + 1)) for k in range(n)]


CLASS_ORDER = ["POLY", "CFIN", "PREC", "NONH"]
