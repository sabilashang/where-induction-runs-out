"""LLM confabulation eval via OpenRouter (3 models × 60 sequences).

Reads OPENROUTER_API_KEY from the environment or a local .env file (never
committed). Writes results/llm_eval.csv and results/llm_summary.json.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv as _dotenv_load
except ImportError:  # optional; load_dotenv() has a file parser fallback
    _dotenv_load = None

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MODELS_REQUESTED = [
    "anthropic/claude-sonnet-4.5",
    "openai/gpt-4o",
    "meta-llama/llama-3.3-70b-instruct",
]
PROMPT_N = 20
NEXT_K = 3
TEMPERATURE = 0
MAX_TOKENS = 400
SLEEP_S = 0.5
MAX_RETRIES = 3


def load_dotenv() -> None:
    """Load ROOT/.env into os.environ without overwriting existing vars.

    Prefer python-dotenv when installed; fall back to a tiny parser so the
    eval still runs in a minimal venv.
    """
    if _dotenv_load is not None:
        _dotenv_load(ROOT / ".env", override=False)
        return
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def pct(num: int, den: int) -> str:
    if den == 0:
        return f"{num}/{den} (n/a)"
    return f"{num}/{den} ({100.0 * num / den:.4f}%)"


def mean_or_none(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def load_prompt_template() -> str:
    return (ROOT / "results" / "llm_prompt.txt").read_text(encoding="utf-8")


def render_prompt(template: str, terms20: list[int]) -> str:
    terms_s = ", ".join(str(x) for x in terms20)
    return template.replace("<terms>", terms_s)


def load_sample() -> list[dict]:
    meta = json.loads((ROOT / "results" / "llm_sample.json").read_text(encoding="utf-8"))
    return meta["rows"]


def load_seqs(anums: list[str]) -> dict[str, list[int]]:
    want = set(anums)
    out: dict[str, list[int]] = {}
    with gzip.open(ROOT / "stripped.gz", "rt", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            anum = parts[0].strip()
            if anum not in want:
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
            out[anum] = vals
            if len(out) == len(want):
                break
    return out


def parse_model_json(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError(f"no JSON object in response: {text[:240]!r}")
    return json.loads(m.group(0))


def http_json(url: str, headers: dict, body: dict | None = None, method: str = "GET") -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_openrouter_models(api_key: str) -> list[str]:
    headers = {"Authorization": f"Bearer {api_key}"}
    data = http_json("https://openrouter.ai/api/v1/models", headers=headers)
    ids = [m["id"] for m in data.get("data", []) if "id" in m]
    return ids


def resolve_models(api_key: str) -> tuple[list[str], dict[str, str]]:
    """Return (models_used, mapping requested->used). On 404, pick nearest."""
    used = []
    mapping = {}
    available = None
    for mid in MODELS_REQUESTED:
        # probe with a tiny request? Better: list models once if needed.
        # We'll resolve against the catalog first.
        if available is None:
            try:
                available = list_openrouter_models(api_key)
            except Exception as exc:
                print(f"WARN: could not list models ({exc}); using requested ids as-is")
                available = []
        if not available or mid in available:
            used.append(mid)
            mapping[mid] = mid
            continue
        # nearest equivalent heuristics
        candidates = []
        if "claude" in mid:
            candidates = [x for x in available if "claude" in x and "sonnet" in x]
            prefer = [x for x in candidates if "4.5" in x or "4-5" in x or "sonnet-4" in x]
            pick = (prefer or candidates or [x for x in available if "claude" in x])[:1]
        elif "gpt-4o" in mid:
            candidates = [x for x in available if "gpt-4o" in x and "mini" not in x]
            pick = candidates[:1] or [x for x in available if x.endswith("/gpt-4o")][:1]
        elif "llama-3.3" in mid or "llama" in mid:
            candidates = [x for x in available if "llama-3.3-70b" in x or "llama-3.3" in x]
            pick = candidates[:1] or [x for x in available if "70b" in x and "llama" in x][:1]
        else:
            pick = []
        if not pick:
            print(f"STOP: requested model {mid} not found and no equivalent")
            print("sample available:", available[:30])
            sys.exit(3)
        alt = pick[0]
        print(f"MODEL FALLBACK: {mid} -> {alt}")
        used.append(alt)
        mapping[mid] = alt
    # dedupe while preserving order
    seen = set()
    unique = []
    for m in used:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique, mapping


def call_openrouter(api_key: str, model: str, prompt: str) -> tuple[str, dict]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/local/revspec",
        "X-Title": "revspec-llm-eval",
    }
    body = {
        "model": model,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "messages": [
            {"role": "system", "content": "Return only valid JSON. No markdown."},
            {"role": "user", "content": prompt},
        ],
    }
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            data = http_json(ENDPOINT, headers=headers, body=body, method="POST")
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            return str(content), data
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            last_err = f"HTTPError {exc.code}: {payload[:500]}"
            print(f"FAIL model={model} attempt={attempt+1}: {last_err}")
            if exc.code == 404:
                raise
            if exc.code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(last_err) from exc
        except Exception as exc:
            last_err = repr(exc)
            print(f"FAIL model={model} attempt={attempt+1}: {last_err}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(last_err or "unknown failure")


def score_one(
    anum: str,
    stratum: str,
    model: str,
    model_requested: str,
    seq: list[int],
    parsed: dict | None,
    raw: str | None,
    error: str | None,
) -> dict:
    truth = seq[PROMPT_N: PROMPT_N + NEXT_K]
    pred = None
    conf = None
    formula = None
    recognized = None
    name_rec = None
    n_correct = 0
    exact = False
    partial = False
    abstain = False
    confab = False
    if parsed is not None and error is None:
        try:
            pred = [int(x) for x in parsed.get("next_three")]
        except Exception:
            pred = None
        try:
            conf = int(parsed.get("confidence"))
        except Exception:
            conf = None
        formula = parsed.get("formula")
        recognized = parsed.get("recognized")
        if isinstance(recognized, str):
            recognized = recognized.strip().lower() in ("true", "1", "yes")
        name_rec = parsed.get("name_if_recognized")
        if pred is not None and len(pred) == NEXT_K and len(truth) == NEXT_K:
            n_correct = sum(int(a == b) for a, b in zip(pred, truth))
            exact = n_correct == NEXT_K
            partial = n_correct >= 1
        abstain = (str(formula).strip() == "NO_FORMULA_FOUND") if formula is not None else False
        confab = bool(conf is not None and conf >= 4 and (not exact) and pred is not None)
    return {
        "anum": anum,
        "stratum": stratum,
        "model": model,
        "model_requested": model_requested,
        "n_terms_available": len(seq),
        "prompt_terms": PROMPT_N,
        "truth_next_three": json.dumps(truth),
        "pred_next_three": json.dumps(pred) if pred is not None else None,
        "n_terms_correct": n_correct,
        "exact_correct": exact,
        "partial_correct": partial,
        "formula": formula,
        "confidence": conf,
        "recognized": recognized,
        "name_if_recognized": name_rec,
        "abstention": abstain,
        "confabulation": confab,
        "raw_response": (raw or "")[:4000],
        "error": error,
        "failed": error is not None,
    }


def aggregate(rows: list[dict], models_used: list[str]) -> dict:
    by_model = {}
    for model in models_used:
        mrows = [r for r in rows if r["model"] == model]
        strata = {}
        for s in ("clean", "revising", "wilderness"):
            sub = [r for r in mrows if r["stratum"] == s]
            ok = [r for r in sub if not r["failed"]]
            n = len(sub)
            n_ok = len(ok)
            n_fail = n - n_ok
            n_exact = sum(1 for r in ok if r["exact_correct"])
            n_partial = sum(1 for r in ok if r["partial_correct"])
            confs = [r["confidence"] for r in ok if r["confidence"] is not None]
            n_confab = sum(1 for r in ok if r["confabulation"])
            n_abstain = sum(1 for r in ok if r["abstention"])
            n_recog = sum(1 for r in ok if r["recognized"] is True)
            rec = [r for r in ok if r["recognized"] is True]
            nrec = [r for r in ok if r["recognized"] is False]
            unk = [r for r in ok if r["recognized"] not in (True, False)]
            strata[s] = {
                "n": n,
                "n_scored": n_ok,
                "n_failed": n_fail,
                "exact_accuracy": pct(n_exact, n_ok),
                "partial_accuracy": pct(n_partial, n_ok),
                "mean_confidence": mean_or_none(confs),
                "confabulation_rate": pct(n_confab, n_ok),
                "abstention_rate": pct(n_abstain, n_ok),
                "recognition_rate": pct(n_recog, n_ok),
                "exact_accuracy_recognized": pct(
                    sum(1 for r in rec if r["exact_correct"]), len(rec)
                ),
                "exact_accuracy_not_recognized": pct(
                    sum(1 for r in nrec if r["exact_correct"]), len(nrec)
                ),
                "n_recognized": len(rec),
                "n_not_recognized": len(nrec),
                "n_recognition_unknown": len(unk),
            }
            # hypothesis check
            wild = s == "wilderness"
            if wild and n_ok:
                mean_c = mean_or_none(confs)
                strata[s]["hypothesis_wilderness"] = {
                    "mean_confidence": mean_c,
                    "exact_accuracy": pct(n_exact, n_ok),
                    "holds_if": (
                        "mean confidence high (>=3.5) AND exact accuracy low (<0.25)"
                    ),
                    "holds": bool(
                        mean_c is not None and mean_c >= 3.5 and (n_exact / n_ok) < 0.25
                    ),
                    "hedges_if": "abstention high (>=0.5) OR mean confidence low (<3.0)",
                    "hedges": bool(
                        (n_abstain / n_ok) >= 0.5
                        or (mean_c is not None and mean_c < 3.0)
                    ),
                }
        # overall contamination note for clean
        clean_ok = [r for r in mrows if r["stratum"] == "clean" and not r["failed"]]
        clean_exact = [r for r in clean_ok if r["exact_correct"]]
        clean_exact_recog = [r for r in clean_exact if r["recognized"] is True]
        by_model[model] = {
            "by_stratum": strata,
            "contamination_clean": {
                "n_exact": len(clean_exact),
                "n_exact_recognized": len(clean_exact_recog),
                "frac_exact_from_recognition": pct(
                    len(clean_exact_recog), len(clean_exact)
                ),
                "note": (
                    "If most clean correctness is recognized=true, the benchmark "
                    "measures recall more than reasoning."
                ),
            },
        }

    # agreement across models per stratum: among sequences with 3 successful preds
    agreement = {}
    by_anum = defaultdict(list)
    for r in rows:
        if not r["failed"] and r["pred_next_three"]:
            by_anum[(r["anum"], r["stratum"])].append(r)
    for s in ("clean", "revising", "wilderness"):
        seqs = [k for k in by_anum if k[1] == s]
        triple = [k for k in seqs if len({r["model"] for r in by_anum[k]}) >= 3]
        # take one row per model
        n_all_agree = 0
        n_majority = 0
        n = 0
        for key in triple:
            preds = {}
            for r in by_anum[key]:
                preds[r["model"]] = r["pred_next_three"]
            if len(preds) < 3:
                continue
            n += 1
            vals = list(preds.values())
            if len(set(vals)) == 1:
                n_all_agree += 1
            # majority: at least 2 match
            c = Counter(vals)
            if c.most_common(1)[0][1] >= 2:
                n_majority += 1
        agreement[s] = {
            "n_with_3_models": n,
            "unanimous_next_three": pct(n_all_agree, n),
            "majority_next_three": pct(n_majority, n),
        }

    return {"by_model": by_model, "agreement_across_models": agreement}


def main():
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("STOP: OPENROUTER_API_KEY not set")
        sys.exit(2)

    if not (ROOT / "results" / "llm_sample.json").exists():
        print("Run experiments/build_llm_sample.py first")
        sys.exit(2)

    template = load_prompt_template()
    sample = load_sample()
    anums = [r["anum"] for r in sample]
    seqs = load_seqs(anums)
    missing = [a for a in anums if a not in seqs or len(seqs[a]) < PROMPT_N + NEXT_K]
    if missing:
        print("STOP: insufficient terms", missing[:10], len(missing))
        sys.exit(3)

    models_used, mapping = resolve_models(api_key)
    print("models_requested", MODELS_REQUESTED)
    print("models_used", models_used)
    print("mapping", mapping)

    # reverse map used -> requested (first requested that maps to it)
    used_to_req = {}
    for req, used in mapping.items():
        used_to_req.setdefault(used, req)

    out_rows: list[dict] = []
    failures_log: list[dict] = []
    total = len(sample) * len(models_used)
    i = 0
    for model in models_used:
        for meta in sample:
            i += 1
            anum = meta["anum"]
            stratum = meta["stratum"]
            seq = seqs[anum]
            prompt = render_prompt(template, seq[:PROMPT_N])
            raw = None
            parsed = None
            err = None
            try:
                raw, _meta = call_openrouter(api_key, model, prompt)
                parsed = parse_model_json(raw)
            except Exception as exc:
                err = repr(exc)[:500]
                failures_log.append({
                    "anum": anum, "stratum": stratum, "model": model, "error": err
                })
                print(f"LOGGED_FAILURE {i}/{total} {anum} {model}: {err}")
            row = score_one(
                anum, stratum, model, used_to_req.get(model, model),
                seq, parsed, raw, err,
            )
            out_rows.append(row)
            print(
                f"  {i}/{total} {anum} {stratum} {model} "
                f"exact={row['exact_correct']} conf={row['confidence']} "
                f"recog={row['recognized']} fail={row['failed']}"
            )
            time.sleep(SLEEP_S)

    fieldnames = [
        "anum", "stratum", "model", "model_requested", "n_terms_available",
        "prompt_terms", "truth_next_three", "pred_next_three", "n_terms_correct",
        "exact_correct", "partial_correct", "formula", "confidence", "recognized",
        "name_if_recognized", "abstention", "confabulation", "raw_response",
        "error", "failed",
    ]
    csv_path = ROOT / "results" / "llm_eval.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    agg = aggregate(out_rows, models_used)
    # hypothesis per model
    hyp = {}
    for model, block in agg["by_model"].items():
        w = block["by_stratum"]["wilderness"]
        h = w.get("hypothesis_wilderness", {})
        hyp[model] = h

    summary = {
        "status": "COMPLETE",
        "endpoint": ENDPOINT,
        "models_requested": MODELS_REQUESTED,
        "models_used": models_used,
        "model_id_mapping": mapping,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "n_sequences": len(sample),
        "n_models": len(models_used),
        "n_rows": len(out_rows),
        "n_failed_calls": sum(1 for r in out_rows if r["failed"]),
        "failures": failures_log,
        "prompt_file": "results/llm_prompt.txt",
        "sample_file": "results/llm_sample.txt",
        "aggregates": agg,
        "hypothesis_per_model": hyp,
        "hypothesis_text": (
            "Confidence stays high in wilderness while accuracy collapses "
            "(model does not know it has no theory; MDL does)."
        ),
    }
    sum_path = ROOT / "results" / "llm_summary.json"
    with open(sum_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    # print contradictions / negatives first
    print("\n=== NEGATIVE / CONTAMINATION CHECKS ===")
    for model, block in agg["by_model"].items():
        c = block["contamination_clean"]
        print(f"{model}: clean exact from recognition: {c['frac_exact_from_recognition']}")
        h = hyp.get(model, {})
        print(
            f"{model}: wilderness hypothesis holds={h.get('holds')} "
            f"hedges={h.get('hedges')} mean_conf={h.get('mean_confidence')} "
            f"exact={h.get('exact_accuracy')}"
        )
    print("\n=== WROTE ===")
    print(csv_path)
    print(sum_path)
    print(json.dumps({"models_used": models_used, "n_failed": summary["n_failed_calls"]}, indent=2))


if __name__ == "__main__":
    main()
