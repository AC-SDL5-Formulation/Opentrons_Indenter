# Automated Indenter

Lab dashboard for the Sainsmart 3018 mill and a Vernier Go Direct force sensor. It runs on the **Raspberry Pi** next to the indenter. Sample mixing is still done by generating an Opentrons protocol and uploading it in the Opentrons App — this site does not start the OT-2.

---

## Start the website

On the Pi, in this folder:

```bash
pip install -r requirements.txt
python run_indenter.py
```

Open **http://localhost:8767** on the Pi, or `http://<pi-hostname>:8767` from another computer on the lab Wi‑Fi.

If that port is busy:

```bash
INDENTER_UI_PORT=8770 python run_indenter.py
```

The first visit asks **Low Object** or **High Object**. Choose **Low Object** on the Pi (no heavy glass effects). You can change it later with the switch in the header.

---

## Connect hardware (Connect tab)

Do this in order. Start stays grey until **CNC** and **Force** are green, or you turn on **Virtual mode** to practise without hardware.

### 1. CNC mill

1. Power the 3018 and plug in USB.
2. Your user must be in the `dialout` group (once, then log out and back in):

   ```bash
   sudo usermod -aG dialout $USER
   ```

3. Click **Find ports**. On the Pi you usually want `/dev/ttyUSB0` or `/dev/ttyACM0`.
4. Click **Connect**. Green CNC pill = GRBL answered Idle.

### 2. Force sensor (Bluetooth)

This is **not** like pairing headphones on a phone. Do **not** pair the sensor in the Pi Bluetooth menu or with `bluetoothctl pair`. If you already did, remove/unpair it, then use the dashboard.

**Once on the Pi — turn the radio on:**

```bash
sudo systemctl start bluetooth
sudo bluetoothctl power on
sudo usermod -aG bluetooth $USER
```

Log out and back in after the group change. If Scan is empty later:

```bash
rfkill unblock bluetooth
bluetoothctl list
```

You should see an adapter such as `hci0`.

**Every session:**

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
| Scan finds nothing | Sensor on, Graphical Analysis closed, `bluetoothctl power on`, `bluetooth` group, do not pair in the system Bluetooth menu |
| Force connected but no number | Wait a second, click Zero |
| Pi UI feels frozen | Stay on **Low Object** |

Legacy scripts (`move_to_locations.py`, `elastic_relaxation.py`, `opentrons_newsetup.py`) still work if you need the old terminal flow. Day-to-day use is the dashboard.
