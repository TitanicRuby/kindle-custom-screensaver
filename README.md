# Kindle Custom Screensaver Uploader

Add your own photos to a jailbroken Kindle's screensaver rotation — no ads, no third-party apps, just your images matched to the device's native grayscale palette.

This works on Kindles jailbroken with a **modern (KPM-based)** jailbreak, such as [WinterBreak2](https://kindlemodding.org/jailbreaking/WinterBreak2/). It uses KOReader's built-in SSH server, so no extra homebrew is required beyond KOReader itself.

> **Note:** I'm not a professional developer or a Kindle-hacking expert — I put this together while poking around my own device out of curiosity. It worked for me, but it's a hobby project, not a maintained/audited tool. Read through the script before running it, use it at your own risk, and feel free to open an issue or PR if you spot something wrong.

> ⚠️ **Disclaimer:** Jailbreaking and modifying system files on your Kindle is done at your own risk. It can potentially cause instability or require a recovery. This guide assumes you already understand the basic risks of jailbreaking. Neither this guide nor its author is responsible for any damage to your device.

**Tested on:** Kindle Paperwhite (11th Generation), firmware 5.16.2.1.1, screensaver resolution **1072×1448**.

Other models/generations almost certainly use different screensaver resolutions and possibly different palette files — **do not assume 1072×1448 is correct for your device.** See [Step 2](#step-2-connect-and-back-up-the-originals) to check your own device's actual specs before converting anything. If you confirm this working on another model, consider opening a PR to add it here.

---

## Prerequisites

- A Kindle jailbroken with a modern jailbreak (e.g. [WinterBreak2](https://kindlemodding.org/jailbreaking/WinterBreak2/)) — see [kindlemodding.org](https://kindlemodding.org/jailbreak-wizard.html) to find the right jailbreak for your model.
- [KOReader](https://kindlemodding.org/jailbreaking/whats-next/getting-koreader/) installed on the Kindle (installable via KPM once jailbroken).
- A PC with:
  - `ssh` and `scp` (built into Linux/macOS; on Windows use WSL, PuTTY, or Git Bash)
  - Python 3 with `Pillow` and `numpy`:
    ```bash
    pip install Pillow numpy --break-system-packages
    ```
- Your Kindle and PC connected to the **same Wi-Fi network**.

---

## Step 1: Enable SSH on the Kindle

1. Open **KOReader**.
2. Tap the top of the screen → open the **tools/cog (Settings)** icon.
3. Find **Network → SSH server**.
4. Tick **"Login without password (DANGEROUS)"** — this is fine on a private home network and avoids needing to set up SSH keys.
5. Tick **SSH server** to start it.
6. Note the **SSH port** shown (typically `2222`) and the Kindle's IP address (shown in the same menu, or check your router's connected-devices list).

> If you toggle the password setting *after* the server is already running, turn **SSH server** off and back on again for the change to take effect.

---

## Step 2: Connect and back up the originals

From your PC:

```bash
ssh -p 2222 root@<kindle-ip>
```

At the password prompt, just press **Enter** (no password needed with the setting above).

You'll see a notice that the root filesystem is mounted **read-only** — this is normal and a safety feature. Leave it read-only for now; we only need write access later, for the actual upload step.

Download a copy of the existing screensavers (for reference and to grab the color palette):

```bash
scp -P 2222 -r root@<kindle-ip>:/usr/share/blanket/screensaver ~/kindle_screensavers
```

The default screensavers use an **indexed grayscale PNG palette**, 1072×1448 pixels (verify your device's exact resolution — see Troubleshooting below if it differs).

---

## Step 3: Prepare your photos

1. Put the photos you want to convert into a folder, e.g. `~/Downloads/imgese`.
2. Download [`batch_convert.py`](./batch_convert.py) from this repo into the same folder (or anywhere you like — just update the path in the script).
3. Open `batch_convert.py` and edit the settings at the top:

    ```python
    source_folder = "/path/to/your/photos"
    original_palette_file = "/path/to/kindle_screensavers/bg_ss00.png"
    output_folder = "kindle_screensavers_new"
    target_size = (1072, 1448)   # match your Kindle's screensaver resolution
    start_number = 20            # continues after the existing bg_ss00–bg_ss19
    ```

4. Run it:

    ```bash
    python3 batch_convert.py
    ```

Each photo is resized/cropped to fill the target resolution, converted to grayscale, and mapped onto the Kindle's exact palette **without dithering** (see Troubleshooting for why this matters), then saved as `bg_ss20.png`, `bg_ss21.png`, etc.

---

## Step 4: Upload to the Kindle

In your SSH session (from Step 2), make the filesystem writable:

```bash
mntroot rw
```

From your **PC**, in a separate terminal, upload the converted images:

```bash
scp -P 2222 kindle_screensavers_new/*.png root@<kindle-ip>:/usr/share/blanket/screensaver/
```

Once the upload finishes, go back to the SSH session and set the filesystem back to read-only (good practice):

```bash
mntroot ro
```

Let the Kindle go to sleep (or trigger sleep manually) to see your new images in the rotation.

---

## Troubleshooting

**My screensaver folder/resolution is different / images look distorted**
Check your Kindle's actual screensaver specs before converting:
```bash
file ~/kindle_screensavers/bg_ss00.png
```
Update `target_size` in the script to match.

**Images came out looking noisy/embossed/textured**
This is caused by Pillow's `.quantize()` applying dithering even when you don't want it — some Pillow versions ignore the `dither=Image.NONE` flag when using a custom palette. The script in this repo works around this by manually mapping each pixel to the nearest palette shade instead of relying on `.quantize()`'s dithering behavior.

**`pip install` fails / `pip: command not found`**
Install pip first:
```bash
sudo apt install python3-pip
```

**`scp` upload fails with "Failure"**
The Kindle's root filesystem is read-only by default. Run `mntroot rw` in your SSH session before uploading, and `mntroot ro` afterward.

**More than 80 photos**
The `bg_ss{NN}` naming pads to two digits (`bg_ss99` is the practical max before the pattern breaks). Split larger batches or adjust the script's naming/format if needed. It's also untested whether the Kindle's screensaver scanner has an upper index limit — verify a newly added high-numbered file actually appears in rotation.

---

## Credits

- [kindlemodding.org](https://kindlemodding.org/) — jailbreak guides and Kindle internals documentation.
- [KOReader](https://koreader.rocks/) — the e-reader app whose built-in SSH server this guide relies on.
