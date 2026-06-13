'use strict';
const sharp = require('sharp');

// Named color reference points in RGB (Tailwind palette-inspired)
const COLOR_NAMES = [
  { name: 'red',    r: 220, g: 38,  b: 38  },
  { name: 'orange', r: 249, g: 115, b: 22  },
  { name: 'amber',  r: 245, g: 158, b: 11  },
  { name: 'yellow', r: 234, g: 179, b: 8   },
  { name: 'lime',   r: 132, g: 204, b: 22  },
  { name: 'green',  r: 34,  g: 197, b: 94  },
  { name: 'teal',   r: 20,  g: 184, b: 166 },
  { name: 'cyan',   r: 6,   g: 182, b: 212 },
  { name: 'sky',    r: 56,  g: 189, b: 248 },
  { name: 'blue',   r: 59,  g: 130, b: 246 },
  { name: 'indigo', r: 99,  g: 102, b: 241 },
  { name: 'violet', r: 139, g: 92,  b: 246 },
  { name: 'purple', r: 168, g: 85,  b: 247 },
  { name: 'pink',   r: 236, g: 72,  b: 153 },
  { name: 'rose',   r: 244, g: 63,  b: 94  },
  { name: 'brown',  r: 120, g: 53,  b: 15  },
  { name: 'beige',  r: 245, g: 222, b: 179 },
  { name: 'gray',   r: 107, g: 114, b: 128 },
  { name: 'white',  r: 248, g: 250, b: 252 },
  { name: 'black',  r: 15,  g: 23,  b: 42  },
];

function nearestColorName(r, g, b) {
  let minDist = Infinity;
  let best    = COLOR_NAMES[0];
  for (const c of COLOR_NAMES) {
    const d = (r - c.r) ** 2 + (g - c.g) ** 2 + (b - c.b) ** 2;
    if (d < minDist) { minDist = d; best = c; }
  }
  return best.name;
}

function toHex(r, g, b) {
  return '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('');
}

/**
 * Sample the image at low resolution using Sharp's raw pixel output,
 * then derive dominant color, color palette, and descriptive tags.
 * Zero external API calls — all runs locally.
 */
async function analyzeImage(imagePath) {
  // Sample at 48×48 for representative pixel distribution
  let raw, info;
  try {
    const result = await sharp(imagePath)
      .resize(48, 48, { fit: 'fill' })
      .removeAlpha()
      .raw()
      .toBuffer({ resolveWithObject: true });
    raw  = result.data;
    info = result.info;
  } catch {
    return { dominantColor: '#888888', palette: [], tags: [] };
  }

  const pixels = [];
  for (let i = 0; i < raw.length; i += 3) {
    pixels.push([raw[i], raw[i + 1], raw[i + 2]]);
  }

  // ── Average (dominant) color ───────────────────────────────────────────────
  const total   = pixels.length;
  let sumR = 0, sumG = 0, sumB = 0;
  for (const [r, g, b] of pixels) { sumR += r; sumG += g; sumB += b; }
  const avgR = Math.round(sumR / total);
  const avgG = Math.round(sumG / total);
  const avgB = Math.round(sumB / total);
  const dominantColor = toHex(avgR, avgG, avgB);

  // ── Rough k=5 palette via evenly-spaced region sampling ───────────────────
  const regions = [
    pixels.slice(0,          Math.floor(total * 0.2)),
    pixels.slice(Math.floor(total * 0.2), Math.floor(total * 0.4)),
    pixels.slice(Math.floor(total * 0.4), Math.floor(total * 0.6)),
    pixels.slice(Math.floor(total * 0.6), Math.floor(total * 0.8)),
    pixels.slice(Math.floor(total * 0.8)),
  ];
  const palette = regions.map(region => {
    let rS = 0, gS = 0, bS = 0;
    for (const [r, g, b] of region) { rS += r; gS += g; bS += b; }
    const n = region.length || 1;
    return toHex(Math.round(rS / n), Math.round(gS / n), Math.round(bS / n));
  });

  // ── Perceptual brightness (ITU-R 601 luma) ────────────────────────────────
  const luma       = (avgR * 299 + avgG * 587 + avgB * 114) / 1000;
  const brightness = luma > 200 ? 'bright' : luma < 60 ? 'dark' : 'mid-toned';

  // ── Saturation (normalised distance from gray axis) ───────────────────────
  const maxC       = Math.max(avgR, avgG, avgB);
  const minC       = Math.min(avgR, avgG, avgB);
  const saturation = maxC === 0 ? 0 : (maxC - minC) / maxC;
  const colorfulness = saturation > 0.35 ? 'vibrant' : saturation < 0.10 ? 'monochrome' : 'muted';

  // ── Dominant hue channel ──────────────────────────────────────────────────
  const dominantColorName = nearestColorName(avgR, avgG, avgB);

  // ── Landscape temperature ─────────────────────────────────────────────────
  const temperature = avgR > avgB + 20 ? 'warm-toned' : avgB > avgR + 20 ? 'cool-toned' : 'neutral';

  const tags = [brightness, colorfulness, dominantColorName, temperature];

  return { dominantColor, palette, tags };
}

module.exports = { analyzeImage };
