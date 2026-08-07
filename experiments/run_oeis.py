"""
Scale-up runner: apply the revision-spectrum pipeline to the OEIS.

Frozen constants (asserted at startup; written into every output header):
    MAX_ORDER=6, MAX_DEGREE=4, SLACK=2, N_MIN=6
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import random
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from revspec.core import guess_prec, literal_cost, revision_spectrum

# FROZEN — do not change without invalidating all OEIS comparisons
SLACK, N_MIN = 2, 6
MAX_ORDER, MAX_DEGREE = 6, 4

# Per-process worker config set in initializer / main before map
_WORKER = {
    "strict_leading": False,
}


def parse_stripped(path, min_terms, max_terms, limit, shuffle_seed=None,
                   anums=None, no_truncate=False):
    """Load eligible (anum, terms) rows from the OEIS stripped file.

    max_terms is ignored when no_truncate is True (use every available term).
    If ``anums`` is a set/list, only those A-numbers are kept (order preserved
    by ``anums`` when it is a list).
    """
    opener = gzip.open if path.endswith(".gz") else open
    want = set(anums) if anums is not None else None
    by_anum = {}
    with opener(path, "rt", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            anum = parts[0].strip()
            if not anum.startswith("A"):
                continue
            if want is not None and anum not in want:
                continue
            vals = []
            for tok in parts[1:]:
                tok = tok.strip()
                if not tok:
                    continue
                try:
                    vals.append(int(tok))
                except ValueError:
                    break
            if len(vals) < min_terms:
                continue
            if no_truncate:
                by_anum[anum] = vals
            else:
                by_anum[anum] = vals[:max_terms]
            if want is None and shuffle_seed is None and limit and len(by_anum) >= limit:
                break
            if want is not None and len(by_anum) == len(want):
                break

    if anums is not None and not isinstance(anums, set):
        rows = [(a, by_anum[a]) for a in anums if a in by_anum]
    else:
        rows = list(by_anum.items())
        if shuffle_seed is not None:
            rng = random.Random(shuffle_seed)
            rng.shuffle(rows)
        if limit:
            rows = rows[:limit]
    return rows


def parse_names(path):
    if not path or not os.path.exists(path):
        return {}
    opener = gzip.open if path.endswith(".gz") else open
    out = {}
    with opener(path, "rt", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("A") and " " in line:
                a, nm = line.split(" ", 1)
                out[a] = nm.strip()
    return out


def _init_worker(strict_leading: bool):
    _WORKER["strict_leading"] = strict_leading


def process(job):
    anum, seq = job
    strict = _WORKER["strict_leading"]
    try:
        res = revision_spectrum(
            seq, anum=anum, n_min=N_MIN,
            max_order=MAX_ORDER, max_degree=MAX_DEGREE, slack=SLACK,
            strict_leading=strict,
        )
        n_d = res.discovery_point()
        lit = literal_cost(list(seq))
        hyp = guess_prec(
            seq, max_order=MAX_ORDER, max_degree=MAX_DEGREE,
            slack=SLACK, best_bits=lit, strict_leading=strict,
        )
        full_fit = (
            hyp is not None and hyp.description_length() < lit
        )
        if full_fit:
            r, d = hyp.order, hyp.degree
            n_id = (r + 1) * (d + 1) + SLACK + r
            L_H = hyp.description_length()
            n_singular = len(hyp.singular_terms)
        else:
            r = d = n_id = L_H = n_singular = None
        prefix_only = (n_d is not None) and (not full_fit)
        return {
            "anum": anum,
            "n_terms": len(seq),
            "n_d": n_d,
            "order": r,
            "degree": d,
            "n_id": n_id,
            "L_H": L_H,
            "n_singular": n_singular,
            "full_fit": bool(full_fit),
            "prefix_only": bool(prefix_only),
            "n_revisions": res.n_revisions(),
            "n_struct_rev": res.n_structural_revisions(),
            "final_lambda": res.L[-1] / res.L_lit[-1],
            "error": None,
        }
    except Exception as exc:
        return {
            "anum": anum,
            "n_terms": len(seq) if seq is not None else None,
            "error": repr(exc)[:200],
            "full_fit": False,
            "prefix_only": False,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stripped", required=True)
    ap.add_argument("--names", default=None)
    ap.add_argument("--terms", type=int, default=34)
    ap.add_argument("--min-terms", type=int, default=20)
    ap.add_argument("--limit", type=int, default=20000)
    ap.add_argument("--shuffle", type=int, default=None, metavar="SEED")
    ap.add_argument("--anums-file", default=None,
                    help="If set, process exactly these A-numbers (one per line).")
    ap.add_argument("--no-truncate", action="store_true",
                    help="Use every available term (ignore --terms cap).")
    ap.add_argument("--strict-leading", type=int, choices=[0, 1], default=0,
                    help="1 = legacy leading-coeff rejection; 0 = singular_terms.")
    ap.add_argument("--write-anums", default=None,
                    help="If set, write the sampled A-number list to this path.")
    ap.add_argument("--resume", action="store_true",
                    help="Skip A-numbers already present in --out and append.")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", default="results/oeis_results.csv")
    args = ap.parse_args()

    # Assert frozen constants
    assert MAX_ORDER == 6 and MAX_DEGREE == 4 and SLACK == 2 and N_MIN == 6, (
        f"FROZEN PARAM MISMATCH: MAX_ORDER={MAX_ORDER} MAX_DEGREE={MAX_DEGREE} "
        f"SLACK={SLACK} N_MIN={N_MIN}"
    )
    strict = bool(args.strict_leading)
    print("FROZEN PARAMS: MAX_ORDER=6 MAX_DEGREE=4 SLACK=2 N_MIN=6")
    print(f"strict_leading={int(strict)} no_truncate={int(args.no_truncate)} "
          f"min_terms={args.min_terms} terms={args.terms} "
          f"shuffle={args.shuffle} limit={args.limit}")

    anums = None
    if args.anums_file:
        with open(args.anums_file, encoding="utf-8") as fh:
            anums = [ln.strip() for ln in fh if ln.strip().startswith("A")]
        print(f"loaded {len(anums)} A-numbers from {args.anums_file}")

    jobs = parse_stripped(
        args.stripped, args.min_terms, args.terms, args.limit,
        shuffle_seed=args.shuffle, anums=anums, no_truncate=args.no_truncate,
    )
    print(f"parsed {len(jobs)} sequences with >= {args.min_terms} terms")

    if args.write_anums:
        os.makedirs(os.path.dirname(args.write_anums) or ".", exist_ok=True)
        with open(args.write_anums, "w", encoding="utf-8") as fh:
            for a, _ in jobs:
                fh.write(a + "\n")
        print(f"wrote {args.write_anums}")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    done = set()
    prior_rows = []
    fieldnames = [
        "anum", "n_terms", "n_d", "order", "degree", "n_id", "L_H",
        "n_singular", "full_fit", "prefix_only", "n_revisions",
        "n_struct_rev", "final_lambda", "error", "name",
    ]
    if args.resume and os.path.exists(args.out):
        prior = pd.read_csv(args.out)
        if "anum" in prior.columns and len(prior):
            done = set(prior["anum"].astype(str))
            prior_rows = prior.to_dict("records")
            print(f"resume: {len(done)} already in {args.out}")
    jobs = [(a, s) for a, s in jobs if a not in done]
    print(f"remaining to process: {len(jobs)}")

    _init_worker(strict)
    rows = list(prior_rows)
    write_header = not (args.resume and os.path.exists(args.out) and len(prior_rows))
    out_fh = open(args.out, "a" if (args.resume and not write_header) else "w",
                  newline="", encoding="utf-8")
    writer = csv.DictWriter(out_fh, fieldnames=fieldnames, extrasaction="ignore")
    if write_header:
        writer.writeheader()
        out_fh.flush()

    names = parse_names(args.names)
    completed = 0
    total_target = len(jobs) + len(done)
    try:
        with ProcessPoolExecutor(
            max_workers=args.jobs,
            initializer=_init_worker,
            initargs=(strict,),
        ) as ex:
            futs = {ex.submit(process, job): job[0] for job in jobs}
            for fut in as_completed(futs):
                row = fut.result()
                if names and row.get("anum"):
                    row["name"] = names.get(row["anum"])
                rows.append(row)
                writer.writerow({k: row.get(k) for k in fieldnames})
                completed += 1
                if completed % 50 == 0:
                    out_fh.flush()
                if completed % 500 == 0:
                    print(f"  {len(done)+completed}/{total_target}")
                    sys.stdout.flush()
    finally:
        out_fh.flush()
        out_fh.close()

    df = pd.DataFrame(rows)

    # Header comment block prepended via a sidecar summary; CSV itself is plain
    # but we also write a .meta.json next to it with frozen params.
    meta = {
        "MAX_ORDER": MAX_ORDER,
        "MAX_DEGREE": MAX_DEGREE,
        "SLACK": SLACK,
        "N_MIN": N_MIN,
        "strict_leading": int(strict),
        "no_truncate": int(args.no_truncate),
        "min_terms": args.min_terms,
        "terms": None if args.no_truncate else args.terms,
        "shuffle": args.shuffle,
        "limit": args.limit,
        "n_jobs_input": len(jobs),
        "out": args.out,
    }
    meta_path = args.out + ".meta.json"

    # Classify
    err = df["error"].notna() if "error" in df.columns else pd.Series([False] * len(df))
    # treat empty-string error as no error
    if "error" in df.columns:
        err = df["error"].notna() & (df["error"].astype(str) != "") & (df["error"].astype(str) != "None")
    holonomic = (~err) & (df.get("full_fit") == True)  # noqa: E712
    prefix_only = (~err) & (df.get("prefix_only") == True)  # noqa: E712
    no_fit = (~err) & (~holonomic) & (~prefix_only)
    n_err = int(err.sum())
    n_hol = int(holonomic.sum())
    n_pref = int(prefix_only.sum())
    n_none = int(no_fit.sum())
    total = n_hol + n_pref + n_none + n_err
    print("\n" + "=" * 62)
    print("OEIS RUN SUMMARY")
    print("=" * 62)
    print(json.dumps(meta, indent=2))
    print(f"holonomic (full-seq fit)   : {n_hol}")
    print(f"prefix-only fit            : {n_pref}")
    print(f"no fit                     : {n_none}")
    print(f"errored                    : {n_err}")
    print(f"conservation sum           : {total} (must equal {len(df)})")
    if total != len(df):
        print("STOP: conservation check FAILED")
        sys.exit(3)
    if n_err:
        msgs = df.loc[err, "error"].astype(str).head(10).tolist()
        print("first error messages:")
        for m in msgs:
            print("  ", m)

    ok = df.loc[holonomic]
    summary = {
        **meta,
        "n_processed": int(len(df)),
        "n_holonomic": n_hol,
        "n_prefix_only": n_pref,
        "n_no_fit": n_none,
        "n_errored": n_err,
        "conservation_sum": total,
    }
    if n_hol:
        revises = ok["n_struct_rev"] > 0
        exact = ok["n_d"] == ok["n_id"]
        w1 = (ok["n_d"] - ok["n_id"]).abs() <= 1
        mae = (ok["n_d"] - ok["n_id"]).abs().mean()
        n_sing = int((ok["n_singular"].fillna(0) > 0).sum())
        mean_sing = float(ok["n_singular"].fillna(0).mean())
        summary.update({
            "n_revise": int(revises.sum()),
            "pct_revise": 100 * float(revises.mean()),
            "exact": int(exact.sum()),
            "within1": int(w1.sum()),
            "exact_pct": 100 * float(exact.mean()),
            "within1_pct": 100 * float(w1.mean()),
            "mae": float(mae),
            "n_with_singular": n_sing,
            "mean_singular": mean_sing,
            "pct_holonomic": 100 * n_hol / len(df),
        })
        print(f"holonomic % of processed   : {n_hol}/{len(df)} "
              f"({100*n_hol/len(df):.4f}%)")
        print(f"revise among holonomic     : {int(revises.sum())}/{n_hol} "
              f"({100*revises.mean():.4f}%)")
        print(f"n_d==n_id exact            : {int(exact.sum())}/{n_hol} "
              f"({100*exact.mean():.4f}%)")
        print(f"n_d==n_id within1          : {int(w1.sum())}/{n_hol} "
              f"({100*w1.mean():.4f}%)")
        print(f"MAE                        : {mae}")
        print(f"n with singular_terms>0    : {n_sing}/{n_hol}")
        print(f"mean n_singular            : {mean_sing}")

    # Rewrite final CSV from assembled rows (canonical column order).
    df.to_csv(args.out, index=False)
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    # also write a text header companion
    hdr = args.out + ".header.txt"
    with open(hdr, "w", encoding="utf-8") as fh:
        fh.write("# FROZEN MAX_ORDER=6 MAX_DEGREE=4 SLACK=2 N_MIN=6\n")
        fh.write(f"# strict_leading={int(strict)} no_truncate={int(args.no_truncate)}\n")
        fh.write(json.dumps(summary, indent=2))
        fh.write("\n")
    print(f"\nwrote {args.out}")
    print(f"wrote {meta_path}")
    print(f"wrote {hdr}")


if __name__ == "__main__":
    main()
