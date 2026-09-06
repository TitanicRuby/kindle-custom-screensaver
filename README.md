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

## Platform notes

This guide was written and tested on **Linux (Zorin OS)**, but everything here is cross-platform:

- **macOS** — `ssh`/`scp` are built in already; the commands in this guide work as-is. For Python packages, use `pip install Pillow numpy` (no `--break-system-packages` needed — see below).
- **Windows** — modern Windows 10/11 ships a built-in OpenSSH client, so `ssh`/`scp` often work directly in PowerShell or Command Prompt with no extra install. If not, WSL, Git Bash, or PuTTY are solid fallbacks.
- **The `--break-system-packages` flag** in the `pip install` command is specific to Debian-based Linux distros (like Zorin), which mark the system Python as "externally managed." On Windows/macOS, just run `pip install Pillow numpy` without that flag.
- **File paths in `batch_convert.py`** — the settings at the top (`source_folder`, `originals_folder`, `output_folder`) use plain paths like `/home/you/photos`. On Windows, use forward slashes too (e.g. `C:/Users/you/photos`) — Python accepts these fine, no backslash-escaping needed.

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

Download a copy of the existing screensavers — **this is your backup**, and it also supplies the palette/naming-pattern reference the script needs later:

```bash
scp -P 2222 -r root@<kindle-ip>:/usr/share/blanket/screensaver ~/kindle_screensavers
```

Check that it actually landed before continuing:

```bash
ls ~/kindle_screensavers
```

You should see all the original `bg_ss*.png` (and similar) files listed. This folder is your only copy of the originals — keep it somewhere safe, especially if you're planning to use `mode = "replace"` later, which deletes the on-device originals once you run its cleanup step.

The default screensavers use an **indexed grayscale PNG palette**, 1072×1448 pixels (verify your device's exact resolution — see Troubleshooting below if it differs).

---

## Step 3: Prepare your photos

1. Put the photos you want to convert into a folder, e.g. `~/Downloads/imgese`.
2. Download [`batch_convert.py`](./batch_convert.py) from this repo (anywhere is fine — just point the settings at the right paths).
3. Open `batch_convert.py` and edit the settings at the top:

    ```python
    source_folder = "/path/to/your/photos"
    originals_folder = "/path/to/kindle_screensavers"   # your Step 2 download
    output_folder = "kindle_screensavers_new"
    target_size = (1072, 1448)   # match your Kindle's screensaver resolution

    mode = "add"          # "add" = keep existing screensavers, add yours after them
                           # "replace" = fully take over the rotation (see below)
    start_number = None   # None = auto-continue after the highest index found in
                           # originals_folder (see note below on adding photos more than once)
    ```

    The script **auto-detects the existing naming pattern** (e.g. `bg_ss00.png`) from the files in `originals_folder` — you don't need to hardcode it. It prints what it detected, so double-check that line of output matches what you'd expect (if your originals folder has multiple sets, like an adult rotation and a kids-mode rotation, it picks the largest group by default — override with `naming_prefix = "bg_ss"` etc. if it picks the wrong one).

4. Choose your mode:
    - **`mode = "add"`** — keeps everything the Kindle already has, just appends your photos as new files (`bg_ss20.png`, `bg_ss21.png`, ...).
    - **`mode = "replace"`** — numbers your photos starting from 0, intended to fully take over the rotation with only your own images. See Step 4b below — this mode does **not** delete anything by itself.

5. Run it:

    ```bash
    python3 batch_convert.py
    ```

Each photo is resized/cropped to fill the target resolution, converted to grayscale, and mapped onto the Kindle's exact palette **without dithering** (see Troubleshooting for why this matters).

### Adding more photos later (running this more than once)

In `mode = "add"`, the script looks at `originals_folder` to figure out the next free index — it takes the **highest number it finds there and continues after it**, so you don't have to track numbers by hand.

The catch: it only knows about what's actually sitting in `originals_folder` on your PC. If you've already uploaded a batch of custom screensavers before, **re-download the current state of the Kindle's screensaver folder before running the script again**, so the previously-added files are accounted for:

```bash
scp -P 2222 -r root@<kindle-ip>:/usr/share/blanket/screensaver ~/kindle_screensavers
```

(same command as Step 2 — just re-run it to refresh your local copy). Then run `batch_convert.py` again with your new photos in `source_folder`; it'll pick up right after your last batch automatically.

If you'd rather set the starting number yourself instead of relying on auto-detection, set `start_number` to a specific integer instead of `None`.

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

### Step 4b: If you used `mode = "replace"` — removing the originals

Replace mode only *adds* your renumbered images; it doesn't touch the originals on the Kindle. To actually end up with **only** your own images in the rotation, the script also writes a `delete_originals.sh` inside your output folder, listing the exact original files it detected in Step 3.

1. **Open and read `delete_originals.sh` before doing anything else.** It's a plain text file — check the file list matches what you expect.
2. Copy it to the Kindle and run it over SSH:

    ```bash
    scp -P 2222 kindle_screensavers_new/delete_originals.sh root@<kindle-ip>:/tmp/
    ssh -p 2222 root@<kindle-ip> "sh /tmp/delete_originals.sh"
    ```

3. It handles `mntroot rw`/`mntroot ro` around the deletion itself, so you don't need to toggle that separately for this step.

Since your Step 2 download already backed up the originals to your PC, nothing is lost even after this — you can always `scp` them back later if you want the defaults back.

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

**More than 80–100 photos**
Digit width is auto-detected from your originals (usually 2 digits, so `99` is the practical max index). The script will refuse to run and tell you the max if your photo count would overflow it. It's also untested whether the Kindle's screensaver scanner has an upper index limit — verify a newly added high-numbered file actually appears in rotation.

**Script detected the wrong naming pattern (e.g. picked kids-mode instead of the main set)**
It picks the largest matching group in `originals_folder` by file count, which is usually right but not guaranteed. Set `naming_prefix = "bg_ss"` (or whatever your device's actual prefix is) at the top of the script to force it.

**`RuntimeError: ... already exist in ... and would be overwritten`**
The script refuses to silently overwrite files already sitting in your output folder. Move/rename/delete the conflicting files, or change `output_folder`/`start_number`.

---

## Credits

- [kindlemodding.org](https://kindlemodding.org/) — jailbreak guides and Kindle internals documentation.
- [KOReader](https://koreader.rocks/) ([source](https://github.com/koreader/koreader)) — the e-reader app whose built-in SSH server this guide relies on.
