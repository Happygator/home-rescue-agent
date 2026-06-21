# Plate-Read Spike — Image Sources

## Downloaded (in `plates/`, verified real JPEGs)

| File | Shows | Notes |
|------|-------|-------|
| `ifixit_fridge_ceiling_near_door.jpg` | model sticker on interior ceiling near the door | in-situ, realistic angle |
| `ifixit_fridge_bottom_left_wall.jpg` | sticker low on the left interior wall | partially obscured |
| `ifixit_fridge_top_left_wall.jpg` | sticker high on the left interior wall | good |
| `ifixit_fridge_door_frame_center.jpg` | sticker on the door frame | good |
| `ifixit_fridge_inside_door.jpg` | sticker on the inside of the door | good |

Source: iFixit wiki "Where to Find Refrigerator Model Number" (CDN `guide-images.cdn.ifixit.com`).
These are **real refrigerator plates photographed in place** — realistic test inputs for "can
Gemini find and read a plate in a normal photo." Legibility varies; record the true model
number per image where it's readable to build the answer key, otherwise treat the image as a
"locate + attempt" case.

## User-provided close-ups (8) — BEST test inputs; answer key in `labels.csv`

High-quality real plate photos you supplied. The ground-truth model numbers are already
recorded in `plates/labels.csv`. **Action needed: save the 8 image files into `plates/` with
these exact filenames** (pasted images can't be written to disk automatically):

| Save as | What it is | True model | Difficulty |
|---------|-----------|-----------|-----------|
| `user_plate_01_samsung_fridge.jpg` | Samsung fridge, clean close-up | RF28T5001SR | easy |
| `user_plate_02_compact_fridge.jpg` | No-logo compact fridge, rear label | BC-70-62H-US(E) *(ambiguous)* | hard |
| `user_plate_03_trane_hvac.jpg` | Trane AC condenser, silver foil label | 4TTR6048J1000AA | hard |
| `user_plate_04_whirlpool_fridge.jpg` | Whirlpool fridge, wider/blurry | WRFF3336SZ | medium |
| `user_plate_05_whirlpool_fridge.jpg` | Whirlpool fridge, clear crop (same unit as 04) | WRFF3336SZ | easy |
| `user_plate_06_lg_dishwasher.jpg` | LG dishwasher, clean close-up | LDFC2423V | easy |
| `user_plate_07_whirlpool_dryer.jpg` | Whirlpool GAS dryer | WGD95HEDW0 | medium |
| `user_plate_08_whirlpool_washer.jpg` | Whirlpool front-load washer | WFW95HEDW0 | medium |

Why this set is strong: spans Samsung/LG/Whirlpool/Trane and fridge/washer/dryer/dishwasher/
HVAC/compact; difficulty graded from clean close-up to low-contrast foil to multi-candidate
ambiguous. Plates 04 and 05 are the SAME unit at different quality (read-consistency test).
Plate 03 (Trane) is HVAC, out of the demo's appliance scope but a good OCR stress case;
07/08 (gas dryer, washer with a fire-hazard label) tie into the safety domain.

Real model-number formats captured here (feed into `validate_model` regex / `model_patterns`):
`RF28T5001SR` (+ `/AA` suffix) · `WRFF3336SZ` · `WGD95HEDW0` · `WFW95HEDW0` · `LDFC2423V` ·
`4TTR6048J1000AA` · `BC-70-62H-US(E)`.

## Not yet downloaded (run to add)

```bash
cd "spikes/datasets/plates"
base="https://guide-images.cdn.ifixit.com/igi"
for pair in \
  "IW6pTepl31oyAY3j:ifixit_fridge_ceiling_center.jpg" \
  "Gkcd4axd6b4ZTkfg:ifixit_fridge_top_right_wall.jpg" \
  "MGxRQTRfBsUGZMHL:ifixit_fridge_door_frame_top.jpg" \
  "KLXTkLLCZ4d124vr:ifixit_fridge_rear.jpg"; do
  id="${pair%%:*}"; name="${pair##*:}"
  curl -sL -A "Mozilla/5.0" -o "$name" "$base/$id.huge" && echo "ok $name"
done
```

## Get better close-ups (recommended for accuracy scoring)

The iFixit set is in-situ (sticker-in-context). For a clean accuracy number you also want
tight close-ups of a data plate where the model number fills the frame:
1. **Your own photos** — shoot the plate on any working appliance (fridge interior, microwave,
   range door frame) under 3 lighting conditions. These are your best, true-labeled test cases.
2. **Image search** — "[brand] refrigerator data plate model number" gives close-ups; save the
   URL + the true model number as the label.
3. **Drop-in downloader** — put any `image_url<TAB>filename` lines in `more_plates.tsv` and:
   ```bash
   while IFS=$'\t' read -r url name; do curl -sL -A "Mozilla/5.0" -o "plates/$name" "$url"; done < more_plates.tsv
   ```

## Answer key

`plates/labels.csv` is created and seeded with the 8 user-provided plates. Columns:
`filename,true_model,brand,appliance,difficulty,notes`. The spike scores the model number
Gemini extracts against `true_model` (exact or normalized match — strip spaces/suffixes like
`/AA` and the trailing ` 00`). Append the iFixit in-situ images with their true models once you
read them off the photos; leave `true_model` blank for any where the sticker isn't legible
(those become "locate + attempt" cases, not accuracy cases).

## Provenance / license

- **Reddit was blocked** to automated fetching, so no r/appliancerepair images are here.
- iFixit content is **CC BY-NC-SA**: fine as a private educational eval set. For the public
  demo video / writeup, use **your own** plate photos and attribute any third-party images.
