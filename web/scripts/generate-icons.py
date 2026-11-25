"""Export the local Atlas SVG mark as browser icons. Requires Pillow only for export."""

from pathlib import Path
from xml.etree import ElementTree

from PIL import Image, ImageDraw

public = Path(__file__).resolve().parents[1] / "public"
source = public / "atlas-mark.svg"
root = ElementTree.parse(source).getroot()
scale = 2048 / 48
canvas = Image.new("RGBA", (2048, 2048))
draw = ImageDraw.Draw(canvas)
for shape in root:
    kind = shape.tag.split("}")[-1]
    if kind == "title":
        continue
    if kind == "rect":
        width, height = float(shape.attrib["width"]), float(shape.attrib["height"])
        radius = float(shape.attrib.get("rx", 0))
        draw.rounded_rectangle(
            (0, 0, width * scale, height * scale),
            radius=radius * scale,
            fill=shape.attrib["fill"],
        )
    elif kind == "polygon":
        points = [tuple(float(n) * scale for n in pair.split(",")) for pair in shape.attrib["points"].split()]
        draw.polygon(points, fill=shape.attrib["fill"])
    else:
        raise ValueError(f"Unsupported logo primitive: {kind}")

for filename, size in [("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)]:
    canvas.resize((size, size), Image.Resampling.LANCZOS).save(public / filename)
canvas.resize((256, 256), Image.Resampling.LANCZOS).save(
    public / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)]
)
(public / "favicon.svg").write_bytes(source.read_bytes())
print("Exported SVG, ICO, Apple touch icon and 192/512px app icons from atlas-mark.svg")
