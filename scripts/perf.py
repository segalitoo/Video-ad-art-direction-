#!/usr/bin/env python3
"""Read what the platform says, decide kill / hold / scale, and feed the winners back.

    python scripts/perf.py read export.csv --rules perf.yml --matrix matrix.csv -o report.md
    python scripts/perf.py read export.csv --rules perf.yml --prev last-week.csv     # adds fatigue
    python scripts/perf.py taste export.csv --rules perf.yml --files creatives.yml   # winners into the taste library

`export.csv` is an ad-level export (Meta Ads Manager: Ad name, Amount spent, Impressions, Link
clicks or CTR, Results, Cost per result, Frequency; add a Days column, or pass --day). Name ads
with the matrix's variant_id (e.g. fernly-reviews-15s_tiktok_H1C1) and --matrix joins each row to
its hook, CTA and platform, so the report can say which hook and which CTA win.

The rules file (templates/perf.yml) holds this account's thresholds per checkpoint (day 1, 3, 7).
Under `min_spend` an ad gets WAIT. Kill wins over scale; everything else is HOLD.

The report ends with a plan for every SCALE ad: ten variations to make before any new concept
(3 headline or hook swaps, 2 background or treatment swaps, 2 format translations, 1 proof swap,
1 CTA swap, 1 awareness reframe). Data proposes; a person decides.

`taste` files every SCALE ad as an exemplar in the taste library with its numbers, so the library
learns what performs, not only what looks right. `creatives.yml` maps ad names (or name prefixes)
to their creative file: {fernly-reviews-15s_tiktok_H1: exports/H1.mp4}.
"""

import argparse
import ast
import csv
from datetime import date
import math
from pathlib import Path

from common import fail, load_yaml

# Column names seen in exports, lowercased; the first match wins.
COLUMNS = {
    "ad": ["ad name", "ad", "name", "variant_id"],
    "spend": ["amount spent (usd)", "amount spent", "spend", "cost"],
    "impressions": ["impressions"],
    "clicks": ["link clicks", "clicks (all)", "clicks"],
    "ctr": ["ctr (link click-through rate)", "link ctr", "ctr"],
    "results": ["results", "conversions", "purchases", "leads"],
    "cpa": ["cost per result", "cost per results", "cpa", "cpl", "cost per purchase"],
    "frequency": ["frequency"],
    "roas": ["purchase roas (return on ad spend)", "roas"],
    "days": ["days", "age", "days running"],
}
OPS = {ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b,
       ast.GtE: lambda a, b: a >= b, ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b}
BIN = {ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b, ast.Add: lambda a, b: a + b,
       ast.Sub: lambda a, b: a - b}


def num(v):
    v = str(v or "").strip().replace(",", "").replace("$", "").replace("%", "").replace("€", "").replace("£", "")
    try:
        return float(v)
    except ValueError:
        return None


def read_export(path, day=None):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        fail(f"{path} has no rows")
    heads = {h.lower().strip(): h for h in rows[0]}
    pick = {k: next((heads[c] for c in names if c in heads), None) for k, names in COLUMNS.items()}
    if not pick["ad"]:
        fail(f"{path}: no ad name column (looked for {', '.join(COLUMNS['ad'])})")
    ads = []
    for r in rows:
        m = {k: (None if not c else r[c].strip() if k == "ad" else num(r[c])) for k, c in pick.items()}
        if not m["ad"]:
            continue
        spend, imp, clicks, res = m["spend"] or 0, m["impressions"] or 0, m["clicks"], m["results"] or 0
        if m["ctr"] is None and clicks is not None and imp:
            m["ctr"] = 100 * clicks / imp
        if m["cpa"] is None:
            m["cpa"] = spend / res if res else math.inf
        m["cpm"] = 1000 * spend / imp if imp else 0
        m["days"] = m["days"] if m["days"] is not None else day
        for k in ("ctr", "frequency", "roas", "clicks"):
            m[k] = m[k] if m[k] is not None else 0
        m["spend"], m["impressions"], m["results"] = spend, imp, res
        ads.append(m)
    return ads


def safe_eval(expr, env):
    """Comparisons, and/or, + - * / on numbers and metric names. Nothing else."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.BoolOp):
            vals = [ev(v) for v in n.values]
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        if isinstance(n, ast.Compare):
            left = ev(n.left)
            for op, right in zip(n.ops, n.comparators):
                r = ev(right)
                if not OPS[type(op)](left, r):
                    return False
                left = r
            return True
        if isinstance(n, ast.BinOp) and type(n.op) in BIN:
            return BIN[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        if isinstance(n, ast.Name):
            if n.id not in env:
                raise ValueError(f"unknown metric '{n.id}'")
            return env[n.id]
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        raise ValueError(f"not allowed in a rule: {ast.dump(n)[:40]}")
    try:
        return ev(ast.parse(expr, mode="eval"))
    except (ValueError, KeyError, SyntaxError) as e:
        fail(f'rule "{expr}": {e}')


def decide(ad, rules):
    if ad["spend"] < rules.get("min_spend", 0):
        return "WAIT", f"spend {ad['spend']:.0f} under {rules['min_spend']}"
    if ad["days"] is None:
        fail(f"{ad['ad']}: no age. Add a Days column to the export, or pass --day")
    cps = sorted(rules.get("checkpoints") or [], key=lambda c: c["day"])
    cp = None
    for c in cps:
        if ad["days"] >= c["day"]:
            cp = c
    if not cp:
        return "WAIT", f"younger than day {cps[0]['day']}" if cps else "no checkpoints"
    env = dict(ad, target_cpa=rules.get("target_cpa", math.inf), target_roas=rules.get("target_roas", 0))
    for rule in cp.get("kill") or []:
        if safe_eval(rule, env):
            return "KILL", f"day {cp['day']}: {rule}"
    for rule in cp.get("scale") or []:
        if safe_eval(rule, env):
            return "SCALE", f"day {cp['day']}: {rule}"
    return "HOLD", f"day {cp['day']}: no rule hit"


def fatigue(ads, prev_path, rules):
    f = rules.get("fatigue") or {}
    prev = {a["ad"]: a for a in read_export(prev_path)}
    for a in ads:
        p = prev.get(a["ad"])
        if p and p["ctr"] and a["ctr"] < p["ctr"] * (1 - f.get("ctr_drop_pct", 20) / 100) \
                and a["frequency"] > f.get("frequency", 2.5):
            a["fatigue"] = f"CTR {p['ctr']:.2f}% → {a['ctr']:.2f}%, frequency {a['frequency']:.1f}"


def load_matrix(path):
    with open(path, encoding="utf-8", newline="") as f:
        return {r["variant_id"]: r for r in csv.DictReader(f)}


def join(ad, matrix):
    if not matrix:
        return {}
    if ad["ad"] in matrix:
        return matrix[ad["ad"]]
    hits = [v for k, v in matrix.items() if k in ad["ad"]]
    return hits[0] if hits else {}


def fmt_money(v):
    return "–" if v in (None, math.inf) else f"{v:,.2f}"


def multiplication_plan(ad, info):
    what = info.get("hook") or ad["ad"]
    return [
        f"3 hook or headline swaps: same visual, new first line (other mechanics than '{what[:40]}')",
        "2 treatment swaps: same copy, dark background and a lifestyle or UGC-frame version",
        "2 format translations: same angle in another format (static ↔ motion loop, stat → testimonial)",
        "1 proof swap: lead with a different proof from the lock",
        "1 CTA swap: the second CTA in the lock's verbal.cta",
        "1 awareness reframe: rewrite for one step colder (problem-aware → cold)",
    ]


def report(ads, matrix, rules, src):
    lines = [f"# Performance read · {Path(src).name} · {date.today().isoformat()}", "",
             f"Rules: target CPA {rules.get('target_cpa')}, min spend {rules.get('min_spend')}. "
             "Data proposes; a person decides.", "",
             "| Ad | Days | Spend | CTR % | CPA | Freq | Verdict | Why |", "|---|---|---|---|---|---|---|---|"]
    for a in sorted(ads, key=lambda a: ("SCALE", "HOLD", "WAIT", "KILL").index(a["verdict"])):
        why = a["why"] + (f"; fatigue: {a['fatigue']}" if a.get("fatigue") else "")
        lines.append(f"| {a['ad']} | {a['days'] if a['days'] is not None else '–'} | {a['spend']:,.0f} | {a['ctr']:.2f} | "
                     f"{fmt_money(a['cpa'])} | {a['frequency']:.1f} | **{a['verdict']}** | {why} |")
    counts = {v: sum(1 for a in ads if a["verdict"] == v) for v in ("SCALE", "HOLD", "WAIT", "KILL")}
    lines += ["", "**Count:** " + ", ".join(f"{k} {v}" for k, v in counts.items())]
    if matrix:
        for key, label in (("hook_id", "hook"), ("cta_id", "CTA"), ("platform", "platform")):
            groups = {}
            for a in ads:
                k = join(a, matrix).get(key)
                if k:
                    groups.setdefault(k, []).append(a)
            if len(groups) > 1:
                lines += ["", f"## By {label}", "", f"| {label} | Ads | Spend | CTR % (spend-weighted) | Scale | Kill |",
                          "|---|---|---|---|---|---|"]
                for k, g in sorted(groups.items(), key=lambda kv: -sum(a["ctr"] * a["spend"] for a in kv[1]) / max(1, sum(a["spend"] for a in kv[1]))):
                    sp = sum(a["spend"] for a in g)
                    ctr = sum(a["ctr"] * a["spend"] for a in g) / sp if sp else 0
                    name = join(g[0], matrix).get({"hook_id": "hook", "cta_id": "cta"}.get(key, ""), "")
                    lines.append(f"| {k} {name[:40]} | {len(g)} | {sp:,.0f} | {ctr:.2f} | "
                                 f"{sum(a['verdict'] == 'SCALE' for a in g)} | {sum(a['verdict'] == 'KILL' for a in g)} |")
    winners = [a for a in ads if a["verdict"] == "SCALE"]
    if winners:
        lines += ["", "## Multiply the winners before writing anything new", ""]
        for a in winners:
            lines += [f"**{a['ad']}**", ""] + [f"- [ ] {s}" for s in multiplication_plan(a, join(a, matrix))] + [""]
    killed = [a for a in ads if a["verdict"] == "KILL"]
    if killed:
        lines += ["## Killed: write down why, so the next batch does not repeat it", ""]
        lines += [f"- {a['ad']}: {a['why']}" for a in killed]
    return "\n".join(lines) + "\n"


def run(args):
    rules = load_yaml(args.rules)
    ads = read_export(args.export, args.day)
    for a in ads:
        a["verdict"], a["why"] = decide(a, rules)
    if getattr(args, "prev", None):
        fatigue(ads, args.prev, rules)
    return ads, rules


def cmd_read(args):
    ads, rules = run(args)
    matrix = load_matrix(args.matrix) if args.matrix else {}
    text = report(ads, matrix, rules, args.export)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    for a in ads:
        print(f"{a['verdict']:5}  {a['ad']}  ({a['why']})" + ("  FATIGUE" if a.get("fatigue") else ""))


def cmd_taste(args):
    import taste
    ads, _ = run(args)
    files = load_yaml(args.files) or {}
    base = Path(args.files).parent
    added = 0
    for a in ads:
        if a["verdict"] not in ("SCALE",) + (("KILL",) if args.with_kills else ()):
            continue
        src = next((files[k] for k in sorted(files, key=len, reverse=True) if a["ad"].startswith(k) or k == a["ad"]), None)
        if not src:
            print(f"skip {a['ad']}: no creative file in {args.files}")
            continue
        path = base / src
        medium = "clip" if path.suffix.lower() in taste.CLIP_EXT else "static"
        why = (f"Performance: {a['verdict']} at day {a['days']:g}, CTR {a['ctr']:.2f}%, CPA {fmt_money(a['cpa'])}, "
               f"spend {a['spend']:,.0f}. {a['why']}.")
        tags = ["performer" if a["verdict"] == "SCALE" else "killed-in-test"]
        taste.add_entry(path, "exemplar" if a["verdict"] == "SCALE" else "anti", medium, tags, why,
                        f"{Path(args.export).name}, ad {a['ad']}", "perf.py (data; art director to confirm)")
        added += 1
    print(f"filed {added} ad(s) in the taste library")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("read", "taste"):
        p = sub.add_parser(name)
        p.add_argument("export")
        p.add_argument("--rules", required=True)
        p.add_argument("--day", type=float, help="the age of every ad, when the export has no Days column")
        p.add_argument("--prev", help="an earlier export of the same ads, for fatigue")
        if name == "read":
            p.add_argument("--matrix", help="matrix.csv, to join ads to hooks, CTAs and platforms")
            p.add_argument("-o", "--out", help="write the report (markdown)")
        else:
            p.add_argument("--files", required=True, help="yml: ad name or prefix -> creative file")
            p.add_argument("--with-kills", action="store_true", help="also file killed ads, as anti-examples")
    a = ap.parse_args()
    {"read": cmd_read, "taste": cmd_taste}[a.cmd](a)


if __name__ == "__main__":
    main()
