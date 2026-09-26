#!/usr/bin/env python3
"""Higgsfield API client: estimate, submit, wait, download, cancel, upload.

    python scripts/hf_api.py estimate bytedance/seedance-2.5/image-to-video -i body.json
    python scripts/hf_api.py run bytedance/seedance-2.5/image-to-video -i body.json --yes --out clips/
    python scripts/hf_api.py wait <request_id> --out clips/
    python scripts/hf_api.py cancel <request_id>
    python scripts/hf_api.py upload keyframes/S01.png          # prints a public_url to use as image_url

Inputs come from a JSON file (-i) and/or key=value pairs (-p duration=4 -p resolution=480p).

Rules this client keeps (from docs.higgsfield.ai, checked 2026-09-26):
- Every paid run is estimated first (POST /estimate/<model>) and only submitted with --yes,
  or when the estimate is under --max-usd. Nothing is spent by accident.
- A generation POST is never retried after an ambiguous timeout: submissions have no
  idempotency key, so a retry could pay twice. Status polling is retried with backoff.
- Every accepted request is appended to runs.jsonl (model, input, estimate, request_id,
  correlation id) before polling, so nothing paid for is ever lost.
- Outputs live on Higgsfield for about seven days; `--out` downloads them.

Authentication: `Authorization: Key <id:secret>`. When this runs in a Claude environment
with the Higgsfield credential connected, the environment adds the header itself and the
key never touches this script. Elsewhere, set HF_KEY to the copied key.
"""

import argparse
import json
import math
import os
import re
from pathlib import Path
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = os.environ.get("HF_API_BASE_URL", "https://api.higgsfield.ai")
TERMINAL = {"completed", "failed", "nsfw", "canceled"}
# The API's firewall rejects Python's default user agent with a 403, so name the client honestly.
USER_AGENT = "video-ad-art-direction/1.0 (+https://github.com/segalitoo/video-ad-art-direction-)"
LOG = Path(os.environ.get("HF_RUNS_LOG", "runs.jsonl"))


class ApiError(Exception):
    def __init__(self, status, detail, correlation=None):
        super().__init__(f"{status}: {detail}")
        self.status, self.detail, self.correlation = status, detail, correlation


HINTS = {
    401: "credentials missing or wrong. Connect the Higgsfield API key in the environment settings "
         "(header Authorization, prefix Key, the copied key as the value), or set HF_KEY.",
    403: "not enough credits on the API balance. Top up at open.higgsfield.ai.",
    404: "model or request not found for this account.",
    422: "the input does not match the model's schema. Check the model's API reference.",
    423: "the model is temporarily blocked. Try later.",
    503: "the model is disabled or not ready. Try later.",
}


def request(method, url, body=None, auth=True, timeout=60):
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    key = os.environ.get("HF_KEY")
    if auth and key:
        headers["Authorization"] = f"Key {key}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return (json.loads(raw) if raw else {}), resp.headers.get("X-Correlation-ID")
    except urllib.error.HTTPError as err:
        raw = err.read().decode(errors="replace")
        try:
            detail = json.loads(raw).get("detail", raw)
        except (ValueError, AttributeError):
            detail = raw
        raise ApiError(err.code, detail, err.headers.get("X-Correlation-ID")) from None


def explain(err):
    hint = HINTS.get(err.status, "")
    if err.status == 403 and "signature" in str(err.detail).lower():
        hint = "blocked by the API's firewall, not a billing problem. Check the User-Agent header."
    cid = f" (correlation id {err.correlation})" if err.correlation else ""
    return f"HTTP {err.status}: {err.detail}{cid}" + (f"\n  -> {hint}" if hint else "")


def load_input(args):
    body = {}
    if args.input:
        body.update(json.loads(Path(args.input).read_text()))
    for pair in args.param or []:
        key, _, value = pair.partition("=")
        try:
            body[key] = json.loads(value)
        except ValueError:
            body[key] = value
    return body


SHORT_SIDE = {"480p": 480, "720p": 720, "1080p": 1080}


def rate_for(text, resolution):
    """First '$X at <resolutions>' in text whose resolutions include this one."""
    for price, where in re.findall(r"\$([0-9.]+)(?: per second of generated video)? at ([0-9p ,or]+?)(?:,| and|\.)", text):
        if resolution in where:
            return float(price)
    return None


def token_price(description, resolution):
    """The per-1,000-token rate. Only the sentence about tokens is read: the same text also
    lists per-second prices, and mixing the two once produced a 50x wrong quote."""
    marker = "1,000 video tokens costs"
    i = description.find(marker)
    return rate_for(description[i:], resolution) if i >= 0 else None


def second_price(description, resolution):
    """The approximate per-second price, used to cross-check the token maths."""
    i = description.find("1,000 video tokens")
    return rate_for(description[:i] if i >= 0 else description, resolution)


def estimate(model, body, aspect=None):
    """The API's own estimate. Some video models answer with a pricing formula instead of a
    number; for those the cost is computed from that formula and the output size:
    tokens = ceil(width x height x seconds x 24 / 1024), priced per 1,000 tokens.
    That figure is the list price, before any customer discount, so approval errs high."""
    result, _ = request("POST", f"{BASE}/estimate/{model}", body)
    if result.get("type") != "description":
        return result
    text = result.get("pricing_description", "")
    res = str(body.get("resolution", "720p"))
    rate = token_price(text, res)
    w, h = (int(x) for x in str(body.get("aspect_ratio") or aspect or "9:16").split(":"))
    short = SHORT_SIDE.get(res)
    if not (rate and short):
        return {"usd": None, "note": text}
    long_side = round(short * max(w, h) / min(w, h))
    seconds = float(body.get("duration", 5))
    tokens = math.ceil(short * long_side * seconds * 24 / 1024)
    usd = tokens / 1000 * rate
    note = (f"list price from the model's formula: {tokens} video tokens x ${rate}/1,000 "
            f"({short}x{long_side}, {seconds:g}s); a customer discount may lower it")
    per_s = second_price(text, res)
    if per_s and abs(usd - per_s * seconds) > 0.15 * per_s * seconds:
        # The two readings disagree: quote the higher one and say so.
        usd = max(usd, per_s * seconds)
        note += f"; WARNING the per-second price (${per_s}/s) disagrees, quoting the higher figure"
    return {"usd": f"{usd:.3f}", "credits": None, "note": note}


def log(entry):
    entry["logged_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def submit(model, body, est, note=None):
    try:
        result, cid = request("POST", f"{BASE}/{model}", body, timeout=120)
    except (TimeoutError, urllib.error.URLError) as err:
        # Ambiguous: the request may have been accepted. Never resubmit automatically.
        log({"event": "ambiguous_submit", "model": model, "input": body, "error": str(err), "note": note})
        sys.exit(f"submit timed out or lost the connection: {err}\n"
                 "It may still have been accepted. Check the API dashboard before submitting again.")
    log({"event": "submitted", "model": model, "input": body, "estimate": est, "note": note,
         "request_id": result.get("request_id"), "correlation_id": cid})
    return result


def wait(request_id, timeout_s=900):
    delay, start = 2.0, time.time()
    while True:
        try:
            result, _ = request("GET", f"{BASE}/requests/{request_id}/status")
        except ApiError as err:
            if err.status in (401, 404):
                raise
            result = None  # 5xx: keep polling with backoff
        except (TimeoutError, urllib.error.URLError):
            result = None
        if result and result.get("status") in TERMINAL:
            return result
        if time.time() - start > timeout_s:
            sys.exit(f"still not finished after {timeout_s}s; run `wait {request_id}` again later")
        status = result.get("status") if result else "retrying"
        print(f"  {status} ... next check in {delay:.0f}s", file=sys.stderr)
        time.sleep(delay + random.uniform(0, 0.5))
        delay = min(delay * 1.5, 10.0)


def outputs(result):
    urls = [i["url"] for i in result.get("images") or [] if i.get("url")]
    for key in ("video", "audio"):
        if isinstance(result.get(key), dict) and result[key].get("url"):
            urls.append(result[key]["url"])
    return urls


def download(result, out_dir, name=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for n, url in enumerate(outputs(result), 1):
        ext = Path(url.split("?")[0]).suffix or ".bin"
        stem = name or result.get("request_id", "output")
        target = out_dir / (f"{stem}{ext}" if len(outputs(result)) == 1 else f"{stem}_{n}{ext}")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}),
                                        timeout=300) as resp:
                target.write_bytes(resp.read())
            saved.append(target)
        except urllib.error.URLError as err:
            host = url.split("/")[2]
            print(f"  could not download from {host}: {err}. Allow {host} in the environment's "
                  f"network settings, or open the URL yourself:\n  {url}", file=sys.stderr)
    return saved


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("estimate", "run"):
        p = sub.add_parser(name)
        p.add_argument("model", help="model id, e.g. bytedance/seedance-2.5/image-to-video")
        p.add_argument("-i", "--input", help="JSON file with the request body")
        p.add_argument("-p", "--param", action="append", help="key=value, JSON values allowed")
        p.add_argument("--aspect", default="9:16", help="output ratio for formula-priced video models (image-to-video follows the start image)")
        if name == "run":
            p.add_argument("--yes", action="store_true", help="approve the estimated cost and submit")
            p.add_argument("--max-usd", type=float, default=0.0, help="submit without --yes when the estimate is at most this")
            p.add_argument("--no-wait", action="store_true")
            p.add_argument("--out", help="download results into this folder")
            p.add_argument("--name", help="file name stem for the download")
            p.add_argument("--note", help="free text stored in runs.jsonl, e.g. 'S01-K candidate 3'")
    p = sub.add_parser("wait")
    p.add_argument("request_id")
    p.add_argument("--out")
    p.add_argument("--name")
    p = sub.add_parser("cancel")
    p.add_argument("request_id")
    p = sub.add_parser("upload")
    p.add_argument("file")
    args = ap.parse_args()

    try:
        if args.cmd == "estimate":
            est = estimate(args.model, load_input(args), args.aspect)
            print(f"{args.model}: ${est.get('usd')}" + (f" ({est['note']})" if est.get("note") else ""))

        elif args.cmd == "run":
            body = load_input(args)
            est = estimate(args.model, body, args.aspect)
            if est.get("usd") is None:
                sys.exit(f"no price could be worked out, so nothing was submitted:\n  {est.get('note')}")
            usd = float(est["usd"])
            print(f"estimate: ${usd:.3f}" + (f" ({est['note']})" if est.get("note") else ""))
            if not (args.yes or (args.max_usd and usd <= args.max_usd)):
                sys.exit("not submitted. Re-run with --yes to approve this cost.")
            result = submit(args.model, body, est, args.note)
            rid = result.get("request_id")
            print(f"submitted: {rid}")
            if not args.no_wait:
                final = wait(rid)
                print(f"{final['status']}: {rid}" + (f" ({final.get('error')})" if final.get("error") else ""))
                log({"event": "finished", "request_id": rid, "status": final["status"], "outputs": outputs(final)})
                for url in outputs(final):
                    print(f"  {url}")
                if args.out and final["status"] == "completed":
                    for f in download(final, args.out, args.name):
                        print(f"  saved {f}")

        elif args.cmd == "wait":
            final = wait(args.request_id)
            print(f"{final['status']}: {args.request_id}")
            for url in outputs(final):
                print(f"  {url}")
            if args.out and final["status"] == "completed":
                for f in download(final, args.out, args.name):
                    print(f"  saved {f}")

        elif args.cmd == "cancel":
            request("POST", f"{BASE}/requests/{args.request_id}/cancel")
            print(f"canceled: {args.request_id} (refunded if it was still queued)")

        elif args.cmd == "upload":
            path = Path(args.file)
            ctype = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
                     ".mp4": "video/mp4", ".wav": "audio/wav"}.get(path.suffix.lower())
            if not ctype:
                sys.exit(f"unsupported file type {path.suffix}")
            info, _ = request("POST", f"{BASE}/files/generate-upload-url", {"content_type": ctype})
            # The signed storage URL gets only the returned headers, never the API key.
            put = urllib.request.Request(info["upload_url"], data=path.read_bytes(), method="PUT",
                                         headers=info.get("upload_headers") or {"Content-Type": ctype})
            urllib.request.urlopen(put, timeout=300).read()
            print(info["public_url"])
    except ApiError as err:
        sys.exit(explain(err))


if __name__ == "__main__":
    main()
