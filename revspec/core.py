"""
revspec.core
============
Core machinery for revision spectra of symbolic hypotheses over integer sequences.

Contents
--------
1. Universal codes for integers / rationals  (Elias-gamma based, prefix-free)
2. Description length of a P-recursive (holonomic) hypothesis
3. Exact guessing of P-recursive recurrences (mod-p screening + exact Q nullspace)
4. The MDL curve L(n) and the revision spectrum R(n)

All description lengths are in BITS and every code used is prefix-free, so the
two-part MDL sum L(H) + L(D|H) is a genuine codelength (Kraft inequality holds).

Author: Sabilashan Ganeshan
License: MIT
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from math import gcd, isqrt, log2
from typing import Iterable, Sequence

# --------------------------------------------------------------------------- #
# 1. Universal prefix-free codes for integers
# --------------------------------------------------------------------------- #

def elias_gamma_len(k: int) -> int:
    """Length in bits of the Elias-gamma codeword for k >= 1.

    gamma(k) = 2*floor(log2 k) + 1 bits.  Prefix-free.
    """
    if k < 1:
        raise ValueError("Elias gamma is defined for k >= 1")
    return 2 * k.bit_length() - 1


def code_nat(k: int) -> int:
    """Prefix-free codelength for a natural number k >= 0."""
    return elias_gamma_len(k + 1)


def code_int(m: int) -> int:
    """Prefix-free codelength for a signed integer m (sign bit + magnitude)."""
    return 1 + code_nat(abs(m))


def code_rational(q: Fraction) -> int:
    """Prefix-free codelength for a rational p/q in lowest terms."""
    return code_int(q.numerator) + code_nat(q.denominator)


def literal_cost(seq: Sequence[int]) -> int:
    """Codelength of the trivial 'store the terms verbatim' hypothesis.

    This is the fallback model H_lit.  It is what makes L(n) finite for every
    sequence, including sequences with no recurrence in the hypothesis class.
    """
    return code_nat(len(seq)) + sum(code_int(int(x)) for x in seq)


# --------------------------------------------------------------------------- #
# 2. Hypotheses
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class PRecHypothesis:
    """A P-recursive (holonomic) hypothesis.

    Encodes the operator   sum_{i=0}^{r} p_i(n) * s(n+i) = 0,
    with p_i(n) = sum_{j=0}^{d} c[i][j] * n^j,  together with the r initial
    terms needed to run the recurrence forward.

    When the leading polynomial p_r vanishes at some indices in range, those
    positions do not determine s(n+r) from prior terms; the corresponding
    sequence values are stored in ``singular_terms`` and charged in L(H).

    d == 0 recovers the C-finite (constant-coefficient) case.
    """
    order: int                       # r
    degree: int                      # d
    coeffs: tuple                    # ((c_00..c_0d), ..., (c_r0..c_rd)) ints
    initial: tuple                   # r initial terms
    singular_terms: tuple = ()       # extra values at zeros of p_r

    @property
    def is_cfinite(self) -> bool:
        return self.degree == 0

    def description_length(self) -> int:
        """L(H): bits to write down the operator plus the initial conditions."""
        bits = code_nat(self.order) + code_nat(self.degree)
        for row in self.coeffs:
            for c in row:
                bits += code_int(int(c))
        for x in self.initial:
            bits += code_int(int(x))
        for x in self.singular_terms:
            bits += code_int(int(x))
        return bits

    def label(self) -> str:
        return f"P-rec(r={self.order},d={self.degree})"


@dataclass(frozen=True)
class LiteralHypothesis:
    """The verbatim fallback model."""
    length: int
    bits: int

    def description_length(self) -> int:
        return self.bits

    def label(self) -> str:
        return "literal"


# --------------------------------------------------------------------------- #
# 3. Guessing a P-recursive recurrence
# --------------------------------------------------------------------------- #

_P = (1 << 61) - 1  # Mersenne prime, big enough that accidental rank drops are
                    # vanishingly rare (< 2^-55 per screened system).


def _rref_mod_p(
    rows: list[list[int]], ncols: int, p: int = _P
) -> tuple[list[list[int]], list[int], int]:
    """Gauss-Jordan over GF(p). Returns (rref_matrix, pivot_cols, rank)."""
    mat = [r[:] for r in rows]
    nrows = len(mat)
    pivots: list[int] = []
    rank = 0
    col = 0
    while col < ncols and rank < nrows:
        piv = None
        for i in range(rank, nrows):
            if mat[i][col] % p:
                piv = i
                break
        if piv is None:
            col += 1
            continue
        mat[rank], mat[piv] = mat[piv], mat[rank]
        inv = pow(mat[rank][col], p - 2, p)
        mat[rank] = [(v * inv) % p for v in mat[rank]]
        for i in range(nrows):
            if i != rank and mat[i][col] % p:
                f = mat[i][col]
                mat[i] = [(a - f * b) % p for a, b in zip(mat[i], mat[rank])]
        pivots.append(col)
        rank += 1
        col += 1
    return mat, pivots, rank


def _nullity_mod_p(rows: list[list[int]], ncols: int, p: int = _P) -> int:
    """Rank-deficiency of a matrix over GF(p). Cheap screening step."""
    _, _, rank = _rref_mod_p(rows, ncols, p)
    return ncols - rank


def _nullspace_basis_mod_p(
    rows: list[list[int]], ncols: int, p: int = _P
) -> list[list[int]]:
    """Nullspace basis over GF(p) from RREF (entries in 0..p-1)."""
    mat, pivots, rank = _rref_mod_p(rows, ncols, p)
    pivot_set = set(pivots)
    free = [c for c in range(ncols) if c not in pivot_set]
    basis = []
    for fc in free:
        vec = [0] * ncols
        vec[fc] = 1
        for r_i, pc in enumerate(pivots):
            vec[pc] = (-mat[r_i][fc]) % p
        basis.append(vec)
    return basis


def _center_lift_mod_p(vec: list[int], p: int = _P) -> list[int]:
    """Lift GF(p) entries to signed ints in (-p/2, p/2]."""
    half = p // 2
    out = []
    for v in vec:
        v %= p
        out.append(v - p if v > half else v)
    return out


def _rational_reconstruction(a: int, m: int) -> Fraction | None:
    """Recover n/d ≡ a (mod m) with |n|, d <= sqrt(m/2) (Wang)."""
    a %= m
    if a == 0:
        return Fraction(0)
    r0, r1 = m, a
    s0, s1 = 0, 1
    bound = isqrt(m // 2)
    while r1 > bound:
        q = r0 // r1
        r0, r1 = r1, r0 - q * r1
        s0, s1 = s1, s0 - q * s1
    if s1 < 0:
        r1, s1 = -r1, -s1
    if s1 == 0 or abs(r1) > bound:
        return None
    g = gcd(abs(r1), s1)
    return Fraction(r1 // g, s1 // g)


def _nullspace_exact(rows: list[list[Fraction]], ncols: int) -> list[list[Fraction]]:
    """Exact nullspace basis over Q by Gauss-Jordan elimination.

    Prefer ``_candidate_integer_nullvectors`` (mod-p + rational reconstruction);
    this is the fallback when reconstruction fails.
    """
    mat = [r[:] for r in rows]
    nrows = len(mat)
    pivots: list[int] = []
    rank = 0
    for col in range(ncols):
        piv = None
        for i in range(rank, nrows):
            if mat[i][col] != 0:
                piv = i
                break
        if piv is None:
            continue
        mat[rank], mat[piv] = mat[piv], mat[rank]
        pv = mat[rank][col]
        mat[rank] = [v / pv for v in mat[rank]]
        for i in range(nrows):
            if i != rank and mat[i][col] != 0:
                f = mat[i][col]
                mat[i] = [a - f * b for a, b in zip(mat[i], mat[rank])]
        pivots.append(col)
        rank += 1
        if rank == nrows:
            break
    free = [c for c in range(ncols) if c not in pivots]
    basis = []
    for fc in free:
        vec = [Fraction(0)] * ncols
        vec[fc] = Fraction(1)
        for r_i, pc in enumerate(pivots):
            vec[pc] = -mat[r_i][fc]
        basis.append(vec)
    return basis


def _candidate_integer_nullvectors(
    rows_int: list[list[int]], ncols: int, p: int = _P
) -> tuple[list[list[int]], int]:
    """GF(p) nullspace → integer vectors via rational reconstruction.

    Returns (integer_nullvectors, mod_p_dimension).  Avoids Fraction
    Gauss-Jordan on the original (possibly huge) matrix entries.  When
    reconstruction fails for a basis vector it is omitted; callers may
    fall back to ``_nullspace_exact`` if dimension > 0 but nothing verifies.
    """
    basis_p = _nullspace_basis_mod_p(
        [[v % p for v in row] for row in rows_int], ncols, p
    )
    out: list[list[int]] = []
    for vec_p in basis_p:
        fracs: list[Fraction] = []
        ok = True
        for a in vec_p:
            rq = _rational_reconstruction(a, p)
            if rq is None:
                ok = False
                break
            fracs.append(rq)
        if ok:
            out.append(_primitive_integer_vector(fracs))
    return out, len(basis_p)


def _primitive_integer_vector(vec: list[Fraction]) -> list[int]:
    """Clear denominators and divide out the gcd -> primitive integer vector."""
    den = 1
    for v in vec:
        den = den * v.denominator // gcd(den, v.denominator)
    ints = [int(v * den) for v in vec]
    g = 0
    for v in ints:
        g = gcd(g, abs(v))
    if g > 1:
        ints = [v // g for v in ints]
    # canonical sign: first nonzero entry positive
    for v in ints:
        if v != 0:
            if v < 0:
                ints = [-x for x in ints]
            break
    return ints


def _build_rows(seq: Sequence[int], r: int, d: int) -> tuple[list[list[int]], int]:
    """Linear system rows for the ansatz sum_i sum_j c_ij n^j s(n+i) = 0.

    Index convention: n runs 0..len(seq)-1-r so that s(n+i) is always defined.
    Unknown ordering: (i, j) -> i*(d+1) + j.
    """
    ncols = (r + 1) * (d + 1)
    rows = []
    for n in range(len(seq) - r):
        row = [0] * ncols
        for i in range(r + 1):
            s = int(seq[n + i])
            npow = 1
            for j in range(d + 1):
                row[i * (d + 1) + j] = npow * s
                npow *= n
        rows.append(row)
    return rows, ncols


def _leading_poly_value(coeffs: tuple, r: int, d: int, n: int) -> int:
    npow = 1
    lead = 0
    for j in range(d + 1):
        lead += coeffs[r][j] * npow
        npow *= n
    return lead


def _annihilates(seq: Sequence[int], r: int, d: int, coeffs: tuple) -> bool:
    """True iff the operator annihilates every available consecutive window."""
    for n in range(len(seq) - r):
        tot = 0
        for i in range(r + 1):
            npow = 1
            acc = 0
            for j in range(d + 1):
                acc += coeffs[i][j] * npow
                npow *= n
            tot += acc * int(seq[n + i])
        if tot != 0:
            return False
    return True


def _singular_terms(seq: Sequence[int], r: int, d: int, coeffs: tuple) -> tuple:
    """Sequence values at indices where p_r(n)=0 (recurrence does not determine them)."""
    out = []
    for n in range(len(seq) - r):
        if _leading_poly_value(coeffs, r, d, n) == 0:
            out.append(int(seq[n + r]))
    return tuple(out)


def _verifies(
    seq: Sequence[int],
    r: int,
    d: int,
    coeffs: tuple,
    strict_leading: bool = False,
) -> bool:
    """Check the operator annihilates every available term.

    If ``strict_leading`` is True (legacy behaviour), also reject any operator
    whose leading polynomial p_r(n) vanishes anywhere in range.  The default
    accepts singular operators; callers must charge the singular terms in L(H).
    """
    if not _annihilates(seq, r, d, coeffs):
        return False
    if strict_leading:
        for n in range(len(seq) - r):
            if _leading_poly_value(coeffs, r, d, n) == 0:
                return False
    return True


def guess_prec(
    seq: Sequence[int],
    max_order: int = 6,
    max_degree: int = 4,
    slack: int = 2,
    best_bits: int | None = None,
    strict_leading: bool = False,
) -> PRecHypothesis | None:
    """Return the minimum-description-length P-recursive hypothesis fitting `seq`.

    Enumerates (r, d) in increasing number of unknowns.  A candidate is only
    considered when the linear system is over-determined by at least `slack`
    equations, which is the standard guard against a recurrence that merely
    interpolates the data it was fitted on.

    Branch-and-bound: a candidate whose parameter count alone must cost more
    than the incumbent is skipped, since every coefficient costs >= 3 bits.

    By default, operators with vanishing leading coefficient at some indices
    are accepted and the corresponding sequence values are charged as
    ``singular_terms`` in L(H).  Pass ``strict_leading=True`` to restore the
    legacy blanket rejection of any such operator.
    """
    m = len(seq)
    best: PRecHypothesis | None = None
    best_L = best_bits if best_bits is not None else float("inf")

    pairs = sorted(
        ((r, d) for r in range(1, max_order + 1) for d in range(0, max_degree + 1)),
        key=lambda rd: ((rd[0] + 1) * (rd[1] + 1), rd[0], rd[1]),
    )

    for r, d in pairs:
        ncols = (r + 1) * (d + 1)
        neqs = m - r
        if neqs < ncols + slack:
            continue
        # lower bound on cost: ncols coefficients (>=3 bits) + r initial terms
        if 3 * ncols > best_L:
            continue
        rows_int, _ = _build_rows(seq, r, d)
        # (a) GF(p) pivot structure / dimension + rational reconstruction.
        # Exact Q only if mod-p nullity > 0 but no reconstructed vector verifies
        # (this (r,d) is then a live candidate that still needs a Q solve).
        lifted, dim_p = _candidate_integer_nullvectors(rows_int, ncols)
        if dim_p == 0:
            continue

        def _consume(int_vecs: list[list[int]]) -> bool:
            nonlocal best_L, best
            any_ok = False
            for ints in int_vecs:
                coeffs = tuple(
                    tuple(ints[i * (d + 1) + j] for j in range(d + 1))
                    for i in range(r + 1)
                )
                if all(c == 0 for c in coeffs[r]):
                    continue
                if not _verifies(seq, r, d, coeffs, strict_leading=strict_leading):
                    continue
                any_ok = True
                sing = () if strict_leading else _singular_terms(seq, r, d, coeffs)
                hyp = PRecHypothesis(
                    r, d, coeffs, tuple(int(x) for x in seq[:r]), singular_terms=sing
                )
                L = hyp.description_length()
                if L < best_L:
                    best_L, best = L, hyp
            return any_ok

        if _consume(lifted):
            continue
        rows_q = [[Fraction(v) for v in row] for row in rows_int]
        basis = _nullspace_exact(rows_q, ncols)
        _consume([_primitive_integer_vector(vec) for vec in basis])
    return best


# --------------------------------------------------------------------------- #
# 4. MDL curve and revision spectrum
# --------------------------------------------------------------------------- #

@dataclass
class SpectrumResult:
    """Full record of one sequence's induction trajectory."""
    name: str
    anum: str
    true_class: str
    n_values: list = field(default_factory=list)
    L: list = field(default_factory=list)          # MDL codelength L(n)
    L_lit: list = field(default_factory=list)      # literal codelength
    dL_lit: list = field(default_factory=list)     # cost of the n-th new term
    R: list = field(default_factory=list)          # raw revision  R(n)=L(n+1)-L(n)
    rho: list = field(default_factory=list)        # normalised revision R/dL_lit
    sig: list = field(default_factory=list)        # exact hypothesis signature
    labels: list = field(default_factory=list)     # short hypothesis label

    # ---- exact structural landmarks ---------------------------------------
    @property
    def N(self) -> int:
        return self.n_values[-1] if self.n_values else 0

    def discovery_point(self):
        """First prefix length at which structure beats verbatim storage."""
        for n, lab in zip(self.n_values, self.labels):
            if lab != "literal":
                return n
        return None

    def stabilisation_point(self):
        """Smallest n after which the hypothesis never changes again."""
        if not self.sig:
            return None
        last = self.sig[-1]
        n_star = self.n_values[0]
        for n, sg in zip(self.n_values, self.sig):
            if sg != last:
                n_star = None
        # stabilisation = earliest n after which the selected hypothesis is fixed
        idx = len(self.sig) - 1
        while idx > 0 and self.sig[idx - 1] == last:
            idx -= 1
        return self.n_values[idx]

    def n_revisions(self) -> int:
        """Number of steps at which the selected hypothesis actually changed."""
        return sum(1 for a, b in zip(self.sig, self.sig[1:]) if a != b)

    def n_structural_revisions(self) -> int:
        """Hypothesis changes occurring after structure was first found.

        These are the genuine 'the formula was wrong and had to be revised'
        events -- the phenomenon the revision spectrum is designed to expose.
        """
        d = self.discovery_point()
        if d is None:
            return 0
        i0 = self.n_values.index(d)
        return sum(1 for a, b in zip(self.sig[i0:], self.sig[i0 + 1:]) if a != b)

    def features(self) -> dict:
        N = self.N
        d = self.discovery_point()
        st = self.stabilisation_point()
        rho_post = []
        if d is not None:
            i0 = self.n_values.index(d)
            rho_post = self.rho[i0:]
        return {
            "final_lambda": self.L[-1] / self.L_lit[-1] if self.L else 1.0,
            "discovery_frac": (d / N) if d else 1.0,
            "stabilisation_frac": (st / N) if st else 1.0,
            "provisional_span": ((st - d) / N) if (d and st) else 0.0,
            "n_revisions": self.n_revisions(),
            "n_structural_revisions": self.n_structural_revisions(),
            "total_variation": sum(abs(r) for r in self.rho),
            "post_disc_variation": sum(abs(r) for r in rho_post),
            "max_abs_rho": max((abs(r) for r in self.rho), default=0.0),
            "min_rho": min(self.rho) if self.rho else 0.0,
            "frac_zero_rho": (
                sum(1 for r in self.rho if abs(r) < 1e-12) / len(self.rho)
                if self.rho else 0.0
            ),
            "found_structure": 0 if d is None else 1,
        }


def revision_spectrum(
    seq,
    name: str = "",
    anum: str = "",
    true_class: str = "",
    n_min: int = 6,
    max_order: int = 6,
    max_degree: int = 4,
    slack: int = 2,
    strict_leading: bool = False,
) -> SpectrumResult:
    """Compute the MDL curve L(n) and the revision spectrum of a sequence.

    For each prefix length n,

        L(n) = min( min_{H in P-rec, H |= s_1..s_n} L(H),  L_lit(s_1..s_n) )

    The raw revision is  R(n) = L(n+1) - L(n).  Because the codelength of a
    P-recursive hypothesis does not depend on n, R(n) = 0 EXACTLY whenever the
    selected hypothesis is unchanged; every nonzero R(n) is a genuine revision
    or a literal-regime absorption.

    The normalised revision divides by the cost of the newly arrived term,

        rho(n) = R(n) / [L_lit(n+1) - L_lit(n)],

    which is scale-free and admits a direct reading:
        rho = 1  the term was absorbed at full verbatim cost (nothing learned)
        rho = 0  the term was free (the standing hypothesis already implied it)
        rho < 0  the term triggered a simplification (a discovery)
        rho > 1  the term forced a costly restructuring
    """
    res = SpectrumResult(name=name, anum=anum, true_class=true_class)
    for n in range(n_min, len(seq) + 1):
        prefix = list(seq[:n])
        lit = literal_cost(prefix)
        hyp = guess_prec(prefix, max_order=max_order, max_degree=max_degree,
                         slack=slack, best_bits=lit,
                         strict_leading=strict_leading)
        if hyp is not None and hyp.description_length() < lit:
            L, label = hyp.description_length(), hyp.label()
            sig = f"{hyp.order}|{hyp.degree}|{hyp.coeffs}"
        else:
            L, label, sig = lit, "literal", "literal"
        res.n_values.append(n)
        res.L.append(L)
        res.L_lit.append(lit)
        res.labels.append(label)
        res.sig.append(sig)

    res.dL_lit = [res.L_lit[i + 1] - res.L_lit[i] for i in range(len(res.L_lit) - 1)]
    res.R = [res.L[i + 1] - res.L[i] for i in range(len(res.L) - 1)]
    res.rho = [
        (r / d if d else 0.0) for r, d in zip(res.R, res.dL_lit)
    ]
    return res


# --------------------------------------------------------------------------- #
# 5. Linear complexity profile baseline (Berlekamp-Massey over GF(2))
# --------------------------------------------------------------------------- #

def linear_complexity_profile(bits: Sequence[int]) -> list[int]:
    """Berlekamp-Massey over GF(2): returns L(s, N) for N = 1..len(bits).

    This is the classical cryptographic profile of Rueppel / Niederreiter.
    We use the sequence reduced mod 2 as the LCP baseline.
    """
    n = len(bits)
    c = [0] * n
    b = [0] * n
    c[0] = b[0] = 1
    L, m = 0, -1
    profile = []
    for N in range(n):
        d = bits[N]
        for i in range(1, L + 1):
            d ^= c[i] & bits[N - i]
        if d == 1:
            t = c[:]
            for i in range(0, n - (N - m)):
                c[i + N - m] ^= b[i]
            if L <= N // 2:
                L = N + 1 - L
                m = N
                b = t
        profile.append(L)
    return profile
