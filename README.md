# NieR Comptuer Vision Autofisher


This program uses computer vision to automatically fish in NieR:Automata. It is completely standalone and will work without needing to modify game volume, sound, or graphics as other autofishers tend to require.

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