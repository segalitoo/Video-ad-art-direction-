#!/usr/bin/env python3
"""Nano Banana Pro (Google Gemini API) and GPT Image (OpenAI API) with your own keys: the `own-keys` route.

    python scripts/img_api.py --provider gemini --prompt-file p.txt --ref kept/F1.jpg --aspect 9:16 --yes --out frames --name F2
    python scripts/img_api.py --provider openai --prompt-file p.txt --max-usd 0.20 --out plates --name A1
    python scripts/img_api.py --provider gemini --prompt-file p.txt --dry-run      # show the request, send nothing

- The price comes from adapters/tools.yml (gemini-api / openai-api). Nothing is sent without
  --yes or a --max-usd cap that covers it: every run is approved first.
- --ref adds a reference image (a local file or a URL). Gemini takes up to several in the one
  request; that is how a chained frame is made from the frame before it. OpenAI takes them
  through its edits endpoint.
- Keys: GEMINI_API_KEY / OPENAI_API_KEY, or the environment's credential proxy for
  generativelanguage.googleapis.com / api.openai.com (then no variable is needed).
- Every request is logged to IMG_RUNS_LOG (default runs.jsonl) before and after it runs.
- Request shapes follow the providers' public docs as of 2026-09 (verify: true in tools.yml).
"""

import argparse
import base64
from datetime import datetime, timezone
import json
import mimetypes
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
import uuid

from PIL import Image

from common import fail, load_tools, parse_aspect

USER_AGENT = "video-ad-art-direction/1.0 (+https://github.com/segalitoo/video-ad-art-direction-)"
LOG = Path(os.environ.get("IMG_RUNS_LOG", os.environ.get("HF_RUNS_LOG", "runs.jsonl")))
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENAI_GEN = "https://api.openai.com/v1/images/generations"
OPENAI_EDIT = "https://api.openai.com/v1/images/edits"
HINTS = {
    400: "The provider rejected the request body; check the model id in adapters/tools.yml.",
    401: "No valid key: set the API key, or add the provider's host to the environment's credentials.",
    403: "Refused: the key has no access to this model, or the network policy blocks the host.",
    404: "Model not found: the id in adapters/tools.yml may have changed.",
    429: "Rate or quota limit: wait, or check the account's billing.",
}


def log(entry):
    entry["logged_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_ref(ref):
    """(bytes, mime) for a local path or a URL."""
    if ref.startswith("http"):
        req = urllib.request.Request(ref, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read(), r.headers.get_content_type() or "image/png"
    p = Path(ref)
    if not p.exists():
        fail(f"reference not found: {ref}")
    return p.read_bytes(), mimetypes.guess_type(p.name)[0] or "image/png"


def model_info(provider):
    tool = load_tools()[f"{provider}-api"]
    return tool["models"]["image"]


def gemini_request(model, prompt, refs, aspect, size):
    parts = [{"text": prompt}] + [{"inline_data": {"mime_type": m, "data": base64.b64encode(b).decode()}}
                                  for b, m in refs]
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect, "imageSize": size}}}
    headers = {"Content-Type": "application/json"}
    if os.environ.get("GEMINI_API_KEY"):
        headers["x-goog-api-key"] = os.environ["GEMINI_API_KEY"]
    return GEMINI.format(model=model), json.dumps(body).encode(), headers


def openai_request(model, prompt, refs, size, quality):
    headers = {}
    if os.environ.get("OPENAI_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['OPENAI_API_KEY']}"
    if not refs:
        headers["Content-Type"] = "application/json"
        body = {"model": model, "prompt": prompt, "size": size, "quality": quality, "n": 1}
        return OPENAI_GEN, json.dumps(body).encode(), headers
    boundary = uuid.uuid4().hex
    chunks = []
    for key, val in (("model", model), ("prompt", prompt), ("size", size), ("quality", quality)):
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{val}\r\n'.encode())
    for n, (data, mime) in enumerate(refs):
        ext = mimetypes.guess_extension(mime) or ".png"
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image[]"; filename="ref{n}{ext}"\r\n'
                      f"Content-Type: {mime}\r\n\r\n".encode() + data + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    return OPENAI_EDIT, b"".join(chunks), headers


def send(url, body, headers):
    headers = {**headers, "User-Agent": USER_AGENT}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")[:400]
        fail(f"HTTP {err.code}: {detail}\n  -> {HINTS.get(err.code, 'see the provider status page')}")
    except urllib.error.URLError as err:
        fail(f"could not reach {url.split('/')[2]}: {err.reason}. If the network policy blocks it, "
             "allow the host in the environment settings.")


def images_from(provider, result):
    if provider == "gemini":
        parts = ((result.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        return [base64.b64decode(p["inlineData"]["data"]) for p in parts if "inlineData" in p]
    return [base64.b64decode(d["b64_json"]) for d in result.get("data") or [] if d.get("b64_json")]


def crop_to(path, aspect):
    """OpenAI renders 2:3; centre-crop to the storyboard's ratio so every frame matches."""
    w, h = parse_aspect(aspect)
    img = Image.open(path)
    target = w / h
    if abs(img.width / img.height - target) < 0.01:
        return
    if img.width / img.height > target:
        nw = round(img.height * target)
        img = img.crop(((img.width - nw) // 2, 0, (img.width + nw) // 2, img.height))
    else:
        nh = round(img.width / target)
        img = img.crop((0, (img.height - nh) // 2, img.width, (img.height + nh) // 2))
    img.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", required=True, choices=["gemini", "openai"])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--prompt")
    src.add_argument("--prompt-file")
    ap.add_argument("--ref", action="append", default=[], help="reference image, file or URL (repeatable)")
    ap.add_argument("--aspect", default="9:16")
    ap.add_argument("--size", default="2K", help="Gemini image size: 1K, 2K or 4K")
    ap.add_argument("--yes", action="store_true", help="approve the quoted price and send")
    ap.add_argument("--max-usd", type=float, help="send without --yes when the quote is at most this")
    ap.add_argument("--dry-run", action="store_true", help="print the request and send nothing")
    ap.add_argument("--out", default=".")
    ap.add_argument("--name", default="image")
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    prompt = args.prompt or Path(args.prompt_file).read_text(encoding="utf-8").strip()
    model = model_info(args.provider)
    usd = model.get("usd_4k") if args.provider == "gemini" and args.size.upper() == "4K" else model.get("usd")
    refs = [read_ref(r) for r in args.ref] if not args.dry_run else [(b"", "image/png") for _ in args.ref]
    if args.provider == "gemini":
        url, body, headers = gemini_request(model["id"], prompt, refs, args.aspect, args.size.upper())
    else:
        url, body, headers = openai_request(model["id"], prompt, refs, model.get("size", "1024x1536"),
                                            model.get("quality", "high"))
    print(f"{args.provider}: {model['name']} ({model['id']}), {len(args.ref)} reference(s), quote ${usd:.3f} (list, verify)")
    if args.dry_run:
        shown = {k: ("<set>" if k.lower() in ("x-goog-api-key", "authorization") else v) for k, v in headers.items()}
        print(json.dumps({"url": url, "headers": shown, "body_bytes": len(body)}, indent=1))
        return
    if not (args.yes or (args.max_usd is not None and usd <= args.max_usd)):
        fail(f"not sent: approve the ${usd:.3f} quote with --yes, or set --max-usd")

    entry = {"event": "submitted", "provider": args.provider, "model": model["id"], "prompt": prompt,
             "refs": args.ref, "aspect": args.aspect, "estimate": {"usd": f"{usd:.3f}"}, "note": args.note}
    log(entry)
    result = send(url, body, headers)
    blobs = images_from(args.provider, result)
    if not blobs:
        log({"event": "finished", "status": "no_image", "note": args.note})
        fail(f"no image in the response: {json.dumps(result)[:300]}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for n, blob in enumerate(blobs, 1):
        path = out / (f"{args.name}.png" if len(blobs) == 1 else f"{args.name}_{n}.png")
        path.write_bytes(blob)
        crop_to(path, args.aspect)
        files.append(str(path))
        print(f"  saved {path}")
    log({"event": "finished", "status": "completed", "outputs": files, "note": args.note})


if __name__ == "__main__":
    main()
