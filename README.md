# NieR Comptuer Vision Autofisher
<a href="https://github.com/jonathanlo411/nier-cv-autofish/releases"><img src="https://img.shields.io/github/v/release/jonathanlo411/nier-cv-autofish?color=f56827"></a>
<a href="https://github.com/jonathanlo411/nier-cv-autofish/blob/main/LICENSE"><img src="https://img.shields.io/github/license/jonathanlo411/nier-cv-autofish"></a>

This program uses computer vision to automatically fish in NieR:Automata. It is completely standalone and will work without needing to modify game volume, sound, or graphics as other autofishers tend to require.

## Quickstart
As a requirement, you must have some sort of Python 3 locally.
1. Clone repository and install dependencies from `requirements.txt`.
2. Run `python -u app.py` and start Nier:Automata (order doesnt matter).
3. Get to a fishing spot in game, and enter fishing mode (hold E on PC).
4. Without moving the camera, press the F1 key to start autofishing.

> Note: The autofisher is CV based, do not move the camera while it is autofishing. If you do reset your fishing position and press F1 again.

### CLI Options

The capture region is automatically centered on your monitor, so no manual coordinate setup is needed. A couple of flags are available to customize behavior:

| Flag | Default | Description |
| --- | --- | --- |
| `--monitor-index` | `1` | Which monitor to capture from (`mss` indexing: `0` = all monitors combined, `1` = primary, `2` = secondary, etc). Use this if the game is running on a secondary display. |
| `--no-display` | off (window shown) | Disables the live preview/classifier popup window. Useful if you don't need the visual overlay or want to save on resources. |

```bash
# Default: primary monitor, preview window shown
python -u app.py

# Capture from a secondary monitor
python -u app.py --monitor-index 2

# Run without the preview window
python -u app.py --no-display
```

## Models
There are various models available for usage but the highest performance one is using `bg_subtract` which utilizes the diffeences in the background and foreground frames and calculates based on spikes of pixel activity within the region of interest (ROI). If you are interested in testing any models locally, take a video of you fishing and move them into the data folder as `input1.mp4`, `input2.mp4`, etc. From there you can install dependencies and run from project root:
```bash
python models/<MODEL>.py

# Example
python models/bg_subtraction_detector.py
```
Results will be populated in the output directory.

## License
This project is licensed under the MIT License. See `LICENSE` for more information.