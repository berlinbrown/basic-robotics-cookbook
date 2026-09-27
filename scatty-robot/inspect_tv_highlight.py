"""Locate objects with local Qwen3-VL; draw predictions on the full photo.

Run from scatty-robot: python inspect_tv_highlight.py images/IMG_0597.jpeg
Uses the same local model as inspect_tv.py. No downloads at runtime.
"""
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

import argparse
import json
import math
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageFont, ImageOps

def parse_prediction(text):
    """Allow a JSON code fence, but reject malformed or truncated output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("Incomplete JSON code fence")
        text = "\n".join(lines[1:-1])
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("objects"), list):
        raise ValueError("Expected a JSON object containing an objects list")
    valid, rejected = [], []
    for item in data["objects"]:
        if not isinstance(item, dict):
            rejected.append(item)
            continue
        label, box = item.get("label"), item.get("box")
        good = isinstance(label, str) and bool(label.strip())
        good = good and isinstance(box, list) and len(box) == 4
        if good:
            good = all(type(v) in (int, float) and math.isfinite(v)
                       and 0 <= v <= 1000 for v in box)
        if good:
            good = box[0] < box[2] and box[1] < box[3]
        if good:
            valid.append({"label": label.strip()[:100], "box": box})
        else:
            rejected.append(item)
    return valid, rejected


def annotate(image, objects):
    result = image.copy()
    draw = ImageDraw.Draw(result)
    size = max(16, round(image.width / 65))
    font = None
    for name in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(name, size)
            break
        except OSError:
            pass
    if font is None:
        font = ImageFont.load_default()
    colors = ["#00E5FF", "#FFCC00", "#FF66CC", "#66FF66", "#FF9966"]
    for index, obj in enumerate(objects):
        x1, y1, x2, y2 = obj["box"]
        x1, x2 = [round(x / 1000 * (image.width - 1)) for x in (x1, x2)]
        y1, y2 = [round(y / 1000 * (image.height - 1)) for y in (y1, y2)]
        color = colors[index % len(colors)]
        draw.rectangle((x1, y1, x2, y2), outline=color,
                       width=max(2, image.width // 500))
        label = f'{index + 1}: {obj["label"]}'
        left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
        width, height = right - left + 10, bottom - top + 10
        tx = max(0, min(x1, image.width - width))
        ty = max(0, min(y1 - height, image.height - height))
        draw.rectangle((tx, ty, tx + width, ty + height), fill=color)
        draw.text((tx + 5 - left, ty + 5 - top), label, font=font, fill="black")
    return result


def main():
    base = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--model", type=Path,
                        default=base / "models/Qwen3-VL-4B-Instruct")
    parser.add_argument("--output-dir", type=Path, default=base / "output")
    parser.add_argument("--targets", default="main game character, hanging lantern, stairs")
    parser.add_argument("--max-side", type=int, default=1280)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--four-bit", action="store_true",
                        help="Optional CUDA quantization; requires preinstalled bitsandbytes")
    args = parser.parse_args()
    if not args.image.is_file() or not args.model.is_dir():
        parser.error("Image and local model directory must exist")
    if args.max_side < 64 or args.max_tokens < 32:
        parser.error("Use max-side >= 64 and max-tokens >= 32")

    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    with Image.open(args.image) as source:
        original = ImageOps.exif_transpose(source).convert("RGB")
    preview = original.copy()
    preview.thumbnail((args.max_side, args.max_side))  # Whole image; no crop.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.output_dir / (args.image.stem + "_highlight")

    if torch.cuda.is_available():
        device, dtype = "cuda", torch.float16
    elif torch.backends.mps.is_available():
        device, dtype = "mps", torch.float16
    else:
        device, dtype = "cpu", torch.float32
    print(f"Loading local Qwen on {device}...", flush=True)
    start = time.perf_counter()
    options = dict(dtype=dtype, attn_implementation="sdpa", local_files_only=True)
    if args.four_bit:
        if device != "cuda":
            parser.error("--four-bit in this script requires CUDA")
        from transformers import BitsAndBytesConfig
        options.update(device_map="auto", quantization_config=BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True))
    model = Qwen3VLForConditionalGeneration.from_pretrained(str(args.model), **options)
    if not args.four_bit:
        model = model.to(device)
    model.eval()
    processor = AutoProcessor.from_pretrained(str(args.model), local_files_only=True)
    print(f"Loaded in {time.perf_counter() - start:.1f}s. Locating objects...", flush=True)

    prompt = (
        "This is a photograph of a monitor displaying a game. Locate these objects "
        f"INSIDE the displayed game: {args.targets}. "
        "Return at most 8 tight bounding boxes. Do not include the monitor itself. "
        "Distinguish hanging objects from objects held by a character. "
        "Omit objects you cannot locate. Return ONLY valid JSON, no commentary: "
        '{"objects":[{"label":"short object name","box":[x1,y1,x2,y2]}]}. '
        "Coordinates MUST be normalized from 0 to 1000 relative to the ENTIRE "
        "input photograph, not relative to the monitor. Origin is top-left; "
        "x increases rightward and y downward. x1,y1 is the upper-left corner; "
        'x2,y2 is the lower-right corner. If none are found return {"objects":[]}.'
    )
    messages = [{"role": "user", "content": [
        {"type": "image", "image": preview}, {"type": "text", "text": prompt}]}]
    inputs = processor.apply_chat_template(messages, tokenize=True,
        add_generation_prompt=True, return_dict=True, return_tensors="pt").to(model.device)
    start = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=args.max_tokens, do_sample=False)
    raw = processor.batch_decode(output[:, inputs["input_ids"].shape[1]:],
                                 skip_special_tokens=True)[0]
    elapsed = time.perf_counter() - start
    raw_path = Path(str(stem) + "_raw.txt")
    raw_path.write_text(raw, encoding="utf-8")
    print(raw)
    try:
        objects, rejected = parse_prediction(raw)
    except (ValueError, TypeError) as exc:
        raise SystemExit(f"Invalid or truncated JSON: {exc}. Raw answer: {raw_path}. "
                         "Try fewer targets or --max-tokens 768. No image drawn.")
    if rejected:
        print(f"Skipped {len(rejected)} invalid box(es).")
    metadata = {"image": str(args.image.resolve()), "model": str(args.model.resolve()),
        "original_size": list(original.size), "input_size": list(preview.size),
        "coordinate_system": "xyxy, 0-1000, relative to full image",
        "generation_seconds": elapsed, "objects": objects, "rejected": rejected}
    Path(str(stem) + ".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    if not objects:
        print("No valid boxes returned. Saved JSON and raw answer; no annotated image created.")
        return
    output_path = Path(str(stem) + ".jpg")
    annotate(original, objects).save(output_path, quality=95)
    print(f"Saved {output_path} ({len(objects)} predicted boxes; {elapsed:.1f}s generation)")
    print("Boxes are model predictions, not verified detections or an attention visualization.")

if __name__ == "__main__":
    main()
