import os

# Prevent Hugging Face downloads during execution.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

from pathlib import Path
import sys

import torch
from PIL import Image, ImageOps
from transformers import AutoProcessor, Qwen3VLForConditionalGeneration


base = Path(__file__).resolve().parent
model_folder = base / "models" / "Qwen3-VL-4B-Instruct"
photo_path = Path(sys.argv[1] if len(sys.argv) > 1 else "tv.jpg").resolve()

if not model_folder.is_dir():
    raise SystemExit(f"Model folder missing: {model_folder}")

if not photo_path.is_file():
    raise SystemExit(f"Photo missing: {photo_path}")

# Choose an available processor.
if torch.cuda.is_available():
    device = "cuda"
    dtype = torch.float16
elif torch.backends.mps.is_available():
    device = "mps"  # Apple Silicon GPU
    dtype = torch.float16
else:
    device = "cpu"
    dtype = torch.float32  # Requires considerably more RAM.

print(f"Loading Qwen on {device}...")

processor = AutoProcessor.from_pretrained(
    str(model_folder),
    local_files_only=True,
)

model = Qwen3VLForConditionalGeneration.from_pretrained(
    str(model_folder),
    dtype=dtype,
    attn_implementation="sdpa",
    local_files_only=True,
).to(device).eval()

# Correct phone-photo orientation and retain the entire photograph.
with Image.open(photo_path) as source:
    image = ImageOps.exif_transpose(source).convert("RGB")

# Resize the whole photo to limit memory use. This does NOT crop it.
image.thumbnail((1280, 1280))

prompt = """
Find the TV or monitor in this photograph.
Focus on the game displayed on its screen and ignore the surrounding room.

Describe:
1. Where the display is in the photograph.
2. The visible game characters and their approximate positions.
3. Visible weapons, trees, walls, paths, and other objects.
4. Any readable interface text or visible status indicators.

Distinguish observations from guesses.
Say when details are too small or unclear.
Do not assume which character I control.
"""

messages = [{
    "role": "user",
    "content": [
        {"type": "image", "image": image},
        {"type": "text", "text": prompt},
    ],
}]

print("Processing the photograph...")

inputs = processor.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,
    return_dict=True,
    return_tensors="pt",
).to(device)

print("Generating description...")

with torch.inference_mode():
    output = model.generate(
        **inputs,
        max_new_tokens=350,
        do_sample=False,
    )

# Remove the input prompt tokens from the output.
answer = output[:, inputs["input_ids"].shape[1]:]

print("\nQwen's description:\n")
print(processor.batch_decode(
    answer,
    skip_special_tokens=True,
)[0])