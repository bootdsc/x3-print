# X3 Print

A small desktop app for printing images on the Orgbro X3 thermal printer over USB,
without the phone app.

The X3 is a 3-inch, 300 dpi label and photo printer sold for use with the "Snap & Tag"
app. Plug it into a PC with a USB-C cable, open X3 Print, drop in a picture, and print.

![X3 Print](docs/screenshot.png)

## Download

Grab `X3Print.exe` from the Releases page, run it, and plug the printer in. There is
nothing to install. Windows only for the ready-made build; on other systems run it from
source (below).

Windows SmartScreen may warn about an unsigned app the first time. Choose
*More info* then *Run anyway*.

## Using it

- **Load** an image by dropping it on the window, pasting it, or clicking the drop area.
- **Size:** rotate, scale to a fraction of the paper width, align left, center or right.
  Long images print down the paper by default.
- **Decimate:** pixel size turns each image pixel into an N x N block of dots, for a
  chunky look; grey levels posterises before dithering.
- **Tone:** brightness, contrast, gamma, sharpen, invert.
- **Dither:** Bayer 2x2 / 4x4 / 8x8, clustered 4x4 / 8x8, Floyd-Steinberg, Atkinson,
  or a plain threshold for line art. Cell scale enlarges the pattern, which holds up
  better against heat spread on the paper.
- **Views:** original, grayscale, decimated, dithered (exactly the dots that will be
  printed) and "on paper", a rough preview of how the dots spread. Zoom to 2x or 4x to
  judge a dither.
- **Printer:** heat, speed, feed after, copies. The print button shows how much paper
  the job uses; STOP halts sending immediately.
- **Library:** save an image with its settings and reload it later. Printed images are
  added automatically. Saved items go in a `library` folder next to the app.

## Run from source

Needs Python 3.10 or newer.

```
pip install pyserial pywebview
python -m x3print
```

Build the single-file Windows app with `build.bat`; it lands in `dist\X3Print.exe`.

There is also a command line, which needs `pillow` and `numpy` as well:

```
python -m x3print status
python -m x3print print photo.jpg --dither bayer2 --density 9
```

## The printer protocol

Measured on one X3 (model string `X3-WBU...`). Other printers in the same family may
work but are untested.

| | |
|---|---|
| USB | CDC serial, VID `0483` PID `5720` |
| Frame | `64` cmd seq len(u16 LE) payload integrity(u32 LE) `9B` |
| Integrity | `(0x12345678 + sum of all preceding bytes + 0x9B) & 0xFFFFFFFF` |
| Head | 864 dots, 108 bytes per row, MSB first, 1 = black |
| Raster | command `0x00`, whole 108-byte rows; four rows per frame prints without pauses |
| Status | pushed as `0xFF` frames about three times a second: status bits, heat, auto-off, speed, battery % |
| Commands | `0x12` model, `0x0A` speed, `0x09` heat, `0x28` paper type, `0x02` feed (dots) |

Command `0x20` prints the self-test page straight away, so sending unknown command IDs
to the printer is not a safe way to explore it.

## Acknowledgements

The YK frame format and the starting command set come from the Orgstra S001 driver in
TiMini-Print (Apache-2.0):

https://github.com/Dejniel/TiMini-Print

## License

Apache-2.0
