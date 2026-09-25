# Automated Indenter

Lab dashboard for the Sainsmart 3018 mill and a Vernier Go Direct force sensor. It runs on the **Raspberry Pi** next to the indenter. Sample mixing is still done by generating an Opentrons protocol and uploading it in the Opentrons App — this site does not start the OT-2.

---

## How to run commands (please read once)

The black window is the **terminal**. You type a line, then press **Enter**.

- **One at a time** means: copy **only one** line, press Enter, wait until you see the prompt again (`$` or `ianng@…`). Then do the next line.
- **OK to paste as a group** means: you may copy the whole grey box, paste once, and press Enter. The lines run in order.
- **No text appearing is often success.** Many Linux commands stay silent when they work. An error is a red or long message, not a blank line.
- If you ever see `[bluetooth]#`, the Bluetooth tool is waiting. Type `quit` and press Enter. Do not paste more commands into that prompt.

You will need the word `sudo` for some lines. It may ask for the Pi password. Typing the password shows **no dots**. That is normal. Type it and press Enter.

---

## Start the website

On the Pi, open a terminal and go to this project folder. These two lines are **OK to paste as a group**:

```bash
pip install -r requirements.txt
python run_indenter.py
```

Open **http://localhost:8767** on the Pi, or `http://<pi-hostname>:8767` from another computer on the lab Wi‑Fi.

If that port is busy, run **this single line** instead of `python run_indenter.py`:

```bash
INDENTER_UI_PORT=8770 python run_indenter.py
```

The first visit asks **Low Object** or **High Object**. Choose **Low Object** on the Pi (no heavy glass effects). You can change it later with the switch in the header.

---

## Connect hardware (Connect tab)

Do this in order. Start stays grey until **CNC** and **Force** are green, or you turn on **Virtual mode** to practise without hardware.

### 1. CNC mill

1. Power the 3018 and plug in USB.
2. **Once only** — allow your account to use USB serial. Run **this single line** (no output is OK):

   ```bash
   sudo usermod -aG dialout $USER
   ```

   Then **log out of the Pi and log back in** (or reboot). Skip this step next time.
3. On the website click **Find ports**. On the Pi you usually want `/dev/ttyUSB0` or `/dev/ttyACM0`.
4. Click **Connect**. Green CNC pill = GRBL answered Idle.

### 2. Force sensor (Bluetooth)

This is **not** like pairing headphones on a phone. Do **not** pair the sensor in the Pi Bluetooth menu. Do **not** type `bluetoothctl pair`. If you already paired it that way, unpair/remove it there, then use only the website Scan / Connect buttons.

#### First time on this Pi (do these one at a time)

Run **one line, press Enter, wait**, then the next. Do **not** paste this whole list at once — `bluetoothctl` can steal the following lines and look frozen.

**Line 1** — start the Bluetooth service. No output is OK.

```bash
sudo systemctl start bluetooth
```

**Line 2** — turn the radio on. You may see `Changing power on succeeded`, or nothing. If you get a `[bluetooth]#` prompt, type `quit` and press Enter.

```bash
bluetoothctl --timeout 8 power on
```

**Line 3** — allow your account to use Bluetooth. No output is OK.

```bash
sudo usermod -aG bluetooth $USER
```

Then **log out and log back in** (or reboot). The group change does nothing until you do that.

#### Check that Bluetooth is really on (OK to paste as a group)

These lines **should print something**. Paste the box once:

```bash
systemctl is-active bluetooth
bluetoothctl --timeout 5 show
bluetoothctl --timeout 5 list
hciconfig -a
groups
```

What “good” looks like:

- `is-active` prints `active`
- `list` or `hciconfig` mentions `hci0` (the Pi’s Bluetooth radio)
- `groups` includes the word `bluetooth` (only after you logged out and back in)

If `list` / `hciconfig` show nothing: `sudo raspi-config` → Interface Options → Bluetooth → Enable, then reboot.

#### If the website Scan is empty later (one at a time)

**Line 1** — no output is OK:

```bash
rfkill unblock bluetooth
```

**Line 2** — this one should list `hci0`:

```bash
bluetoothctl --timeout 5 list
```

#### Every session (website only — no extra terminal)

1. Turn the Go Direct sensor on. Close **Graphical Analysis** if it is open (only one program can hold the sensor).
2. On the Connect tab click **Scan Bluetooth**.
3. Click the line that looks like `GDX-FOR …`.
4. Click **Connect**, then **Zero**.

Green Force pill + a Newton number (even `0.000`) means it worked. The site remembers the last sensor name.

### 3. Home (and optional jog)

Click **Home**. The mill raises Z first, then goes to origin. Jog only after a successful home.

### Virtual mode

Turn on **Virtual CNC + force** to click through Run without moving hardware. Turn it off before a real indent.

---

## Run an indent (Run tab)

1. Click wells on the `main_rack_A` grid (well 0 is selected by default).
2. Choose **Stress–strain** or **Relaxation**.
3. Check the switches you want (coarse / fine / indent / stop on crack / home at end) instead of commenting code.
4. Contact area default is **25.52 mm²**. Stress is `σ (MPa) = F (N) / A (mm²)`. Do not mix these CSVs with older spreadsheet numbers.
5. Press **Start**. Watch the live force curve.
6. **Stop** raises Z, then homes. Use that if anything looks wrong.

Results land in the **Results** tab and as a CSV under `results/`.

---

## Opentrons prep (Prep tab)

This site **does not** run the OT-2.

1. Toggle the recipe steps (dispense reagents, mix, transfer, UV-stand pickup).
2. Edit volumes if needed.
3. **Generate protocol**, then **Download protocol.py**.
4. Open the Opentrons App → import the file → calibrate → Run.

Custom labware names (`allen_8_wellplate_20000ul`, `testwell`) must already exist on that robot. The UV lamp serial line is not included.

---

## If something fails

| Symptom | What to try |
|---|---|
| Website “address already in use” | Use `INDENTER_UI_PORT=8770 python run_indenter.py` |
| CNC not in the port list | Cable, power, `dialout` group, Find ports again |
| Scan finds nothing | Sensor on, Graphical Analysis closed, run the “check that Bluetooth is really on” box above, `bluetooth` group after logout, do not pair in the system Bluetooth menu |
| Terminal looks frozen after Bluetooth commands | You may be inside `[bluetooth]#`. Type `quit` and Enter. Next time run those lines **one at a time**. |
| Force connected but no number | Wait a second, click Zero |
| Pi UI feels frozen | Stay on **Low Object** |

Legacy scripts (`move_to_locations.py`, `elastic_relaxation.py`, `opentrons_newsetup.py`) still work if you need the old terminal flow. Day-to-day use is the dashboard.
