(() => {
  const $ = (id) => document.getElementById(id);
  const socket = io();

  const state = {
    status: null,
    layout: null,
    selected: new Set(),
    wellState: {},
    chart: null,
    otReady: false,
  };

  function api(path, opts) {
    return fetch(path, opts).then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err = new Error(data.error || res.statusText);
        err.data = data;
        throw err;
      }
      return data;
    });
  }

  function post(path, body) {
    return api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      $("tab-" + btn.dataset.tab).classList.add("active");
    });
  });

  function pillClass(el, kind) {
    el.classList.remove("connected", "disconnected", "busy", "error");
    el.classList.add(kind || "disconnected");
  }

  function applyStatus(s) {
    if (!s) return;
    state.status = s;
    const run = s.run || "IDLE";
    $("run-pill").textContent = run;
    $("run-pill").className = "run-pill " + (run === "RUNNING" ? "running" : run === "STOPPING" ? "stopping" : "idle");
    $("link-dot").className = "connection-dot " + (s.cnc.connected || s.force.connected ? "connected" : "disconnected");

    pillClass($("cnc-pill"), s.cnc.state === "connected" ? "connected" : s.cnc.state === "busy" ? "busy" : s.cnc.state === "error" ? "error" : "disconnected");
    $("cnc-state").textContent = s.cnc.status || s.cnc.state;
    pillClass($("force-pill"), s.force.connected ? "connected" : "disconnected");
    $("force-state").textContent = s.force.connected
      ? (s.force.name || "connected") + (s.force.force_n != null ? ` · ${Number(s.force.force_n).toFixed(3)} N` : "")
      : "not connected";
    pillClass($("ot-pill"), s.ot_protocol_ready ? "connected" : "disconnected");
    $("ot-state").textContent = s.ot_protocol_ready ? "protocol ready" : "no protocol yet";
    $("live-force").textContent = s.force.force_n == null ? "—" : Number(s.force.force_n).toFixed(3);

    const pos = s.cnc.position || {};
    $("pos-readout").textContent = `X ${fmt(pos.x)}   Y ${fmt(pos.y)}   Z ${fmt(pos.z)}`;
    $("virtual-toggle").checked = !!s.virtual;
    $("btnStart").disabled = !s.ready;
    $("btnStop").disabled = !(s.run === "RUNNING" || s.run === "STOPPING" || s.cnc.connected);
    $("btnHome").disabled = !(s.cnc.connected || s.virtual);
    $("btnHomeCard").disabled = $("btnHome").disabled;
    $("connect-summary").textContent = s.ready
      ? "Ready to start."
      : "Start stays locked until CNC and Force are green, or Virtual is on.";
    if (s.step) $("protocol-line").textContent = s.step;
  }

  function fmt(v) {
    return v == null || Number.isNaN(v) ? "—" : Number(v).toFixed(2);
  }

  function renderPorts(ports, selected) {
    const sel = $("cnc-port");
    sel.innerHTML = "";
    (ports || []).forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.device;
      opt.textContent = `${p.device}  ${p.description || ""}`.trim();
      sel.appendChild(opt);
    });
    if (!ports || !ports.length) {
      const opt = document.createElement("option");
      opt.value = selected || "";
      opt.textContent = selected || "No ports found";
      sel.appendChild(opt);
    }
    if (selected) sel.value = selected;
  }

  function renderDevices(devices) {
    const list = $("gdx-list");
    list.innerHTML = "";
    (devices || []).forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.name;
      const rssi = d.rssi == null ? "" : `  rssi ${d.rssi}`;
      opt.textContent = d.name + rssi;
      list.appendChild(opt);
    });
  }

  function renderWells(layout) {
    state.layout = layout;
    const grid = $("well-grid");
    grid.innerHTML = "";
    grid.style.gridTemplateColumns = `repeat(${layout.num_x}, minmax(36px, 1fr))`;
    if (state.selected.size === 0 && layout.wells.length) state.selected.add(0);
    layout.wells.forEach((w) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "well";
      btn.dataset.index = String(w.index);
      btn.textContent = String(w.index);
      if (state.selected.has(w.index)) btn.classList.add("selected");
      const st = state.wellState[w.index];
      if (st) btn.classList.add(st);
      btn.addEventListener("click", () => {
        if (state.selected.has(w.index)) state.selected.delete(w.index);
        else state.selected.add(w.index);
        btn.classList.toggle("selected");
      });
      grid.appendChild(btn);
    });
  }

  function setWellState(index, kind) {
    state.wellState[index] = kind;
    const el = document.querySelector(`.well[data-index="${index}"]`);
    if (!el) return;
    el.classList.remove("active", "done", "skipped");
    if (kind) el.classList.add(kind);
  }

  function initChart() {
    const ctx = $("force-plot").getContext("2d");
    state.chart = new Chart(ctx, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Force (N)",
            data: [],
            borderColor: "rgb(15, 166, 155)",
            backgroundColor: "rgba(15, 166, 155, 0.12)",
            tension: 0.15,
            pointRadius: 2,
          },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            type: "linear",
            title: { display: true, text: "Distance (mm) or time (s)" },
          },
          y: { title: { display: true, text: "Force (N)" } },
        },
      },
    });
  }

  function resetChart() {
    state.chart.data.datasets[0].data = [];
    state.chart.update();
  }

  function addPoint(pt) {
    const x = pt.mode === "relaxation" ? Number(pt.time_secs || 0) : Number(pt.distance_mm || 0);
    state.chart.data.datasets[0].data.push({ x, y: Number(pt.force_N) });
    state.chart.update();
    prependResultRow(pt);
  }

  function prependResultRow(pt) {
    const body = $("results-body");
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${pt.well}</td><td>${pt.point_index}</td><td>${pt.force_N}</td><td>${pt.stress_mPa}</td><td>${pt.distance_mm}</td><td>${pt.time_secs || ""}</td>`;
    body.prepend(tr);
    while (body.children.length > 200) body.removeChild(body.lastChild);
  }

  function collectRunSettings() {
    return {
      experiment_name: $("experiment-name").value,
      mode: $("run-mode").value,
      wells: Array.from(state.selected).sort((a, b) => a - b),
      contact_area_mm2: Number($("contact-area").value),
      expected_height: Number($("expected-height").value),
      force_stop_n: Number($("force-stop").value),
      crack_drop_frac: Number($("crack-drop").value),
      relaxation_hold_frac: Number($("relax-hold").value),
      coarse_approach: $("tog-coarse").checked,
      fine_approach: $("tog-fine").checked,
      do_indent: $("tog-indent").checked,
      stop_on_crack: $("tog-crack").checked,
      home_at_end: $("tog-home").checked,
    };
  }

  function collectOtSettings() {
    const rows = [];
    for (let i = 0; i < 4; i += 1) {
      rows.push({
        dmam: Number($(`vol-dmam-${i}`).value),
        amps: Number($(`vol-amps-${i}`).value),
        pbs: Number($(`vol-pbs-${i}`).value),
        xl: Number($(`vol-xl-${i}`).value),
        pi: Number($(`vol-pi-${i}`).value),
      });
    }
    return {
      replicates: Number($("ot-replicates").value),
      DMAm_volumes: rows.map((r) => r.dmam),
      AMPS_volumes: rows.map((r) => r.amps),
      PBS_volumes: rows.map((r) => r.pbs),
      crosslinker_volumes: rows.map((r) => r.xl),
      photoinitiator_volumes: rows.map((r) => r.pi),
      dispense_DMAm: $("ot-d-dmam").checked,
      dispense_AMPS: $("ot-d-amps").checked,
      dispense_crosslinker: $("ot-d-xl").checked,
      dispense_photoinitiator: $("ot-d-pi").checked,
      dispense_PBS: $("ot-d-pbs").checked,
      pipette_mix: $("ot-mix").checked,
      stir_plate_wait: $("ot-stir").checked,
      transfer_to_testplate: $("ot-transfer").checked,
      uv_stand_move: $("ot-uv").checked,
    };
  }

  function fillVolumeTable(defaults) {
    const body = $("vol-body");
    body.innerHTML = "";
    for (let i = 0; i < 4; i += 1) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${i + 1}</td>
        <td><input id="vol-dmam-${i}" type="number" step="0.01" value="${(defaults.DMAm_volumes || [])[i] ?? 0}"></td>
        <td><input id="vol-amps-${i}" type="number" step="0.01" value="${(defaults.AMPS_volumes || [])[i] ?? 0}"></td>
        <td><input id="vol-pbs-${i}" type="number" step="0.01" value="${(defaults.PBS_volumes || [])[i] ?? 0}"></td>
        <td><input id="vol-xl-${i}" type="number" step="0.01" value="${(defaults.crosslinker_volumes || [])[i] ?? 0}"></td>
        <td><input id="vol-pi-${i}" type="number" step="0.01" value="${(defaults.photoinitiator_volumes || [])[i] ?? 0}"></td>`;
      body.appendChild(tr);
    }
  }

  $("btnFindPorts").addEventListener("click", async () => {
    $("cnc-msg").textContent = "Looking for USB ports…";
    try {
      const data = await api("/api/ports");
      renderPorts(data.ports, data.remembered && data.remembered.cnc_port);
      $("cnc-msg").textContent = data.ports.length ? `Found ${data.ports.length} port(s).` : "No serial ports. Plug in the CNC USB cable.";
    } catch (err) {
      $("cnc-msg").textContent = err.message;
    }
  });

  $("btnCncConnect").addEventListener("click", async () => {
    $("cnc-msg").textContent = "Connecting…";
    try {
      const data = await post("/api/cnc/connect", { port: $("cnc-port").value });
      applyStatus(data);
      $("cnc-msg").textContent = data.cnc.status || "Connected.";
    } catch (err) {
      $("cnc-msg").textContent = err.message;
    }
  });

  $("btnCncDisconnect").addEventListener("click", async () => {
    applyStatus(await post("/api/cnc/disconnect"));
    $("cnc-msg").textContent = "Disconnected.";
  });

  $("btnForceScan").addEventListener("click", async () => {
    $("force-msg").textContent = "Scanning Bluetooth… this can take a few seconds.";
    try {
      const data = await post("/api/force/scan");
      renderDevices(data.devices);
      $("force-msg").textContent = data.error || (data.devices.length ? "Select a device, then Connect." : "No devices.");
    } catch (err) {
      $("force-msg").textContent = err.message;
    }
  });

  $("btnForceConnect").addEventListener("click", async () => {
    const name = $("gdx-list").value;
    $("force-msg").textContent = "Connecting…";
    try {
      const data = await post("/api/force/connect", { name });
      applyStatus(data);
      $("force-msg").textContent = data.message || "Connected.";
    } catch (err) {
      $("force-msg").textContent = err.message;
    }
  });

  $("btnForceZero").addEventListener("click", async () => {
    try {
      const data = await post("/api/force/zero");
      applyStatus(data);
      $("force-msg").textContent = `Blank = ${Number(data.blank).toFixed(4)} N`;
    } catch (err) {
      $("force-msg").textContent = err.message;
    }
  });

  async function home() {
    $("cnc-msg").textContent = "Homing (Z up first)…";
    try {
      const data = await post("/api/cnc/home");
      applyStatus(data);
      $("cnc-msg").textContent = "Homed.";
    } catch (err) {
      $("cnc-msg").textContent = err.message;
    }
  }
  $("btnHome").addEventListener("click", home);
  $("btnHomeCard").addEventListener("click", home);

  document.querySelectorAll(".jog").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const step = Number($("jog-step").value) || 1;
      const map = {
        "x+": { dx: step },
        "x-": { dx: -step },
        "y+": { dy: step },
        "y-": { dy: -step },
        "z+": { dz: step },
        "z-": { dz: -step },
      };
      try {
        applyStatus(await post("/api/cnc/jog", map[btn.dataset.jog]));
      } catch (err) {
        $("cnc-msg").textContent = err.message;
      }
    });
  });

  $("virtual-toggle").addEventListener("change", async (ev) => {
    try {
      applyStatus(await post("/api/virtual", { virtual: ev.target.checked }));
      $("connect-summary").textContent = ev.target.checked
        ? "Virtual mode on. Start is unlocked."
        : "Virtual mode off.";
    } catch (err) {
      $("connect-summary").textContent = err.message;
    }
  });

  $("btnStart").addEventListener("click", async () => {
    const settings = collectRunSettings();
    if (!settings.wells.length) {
      $("protocol-line").textContent = "Select at least one well.";
      return;
    }
    resetChart();
    $("results-body").innerHTML = "";
    state.wellState = {};
    document.querySelectorAll(".well").forEach((el) => el.classList.remove("active", "done", "skipped"));
    try {
      const data = await post("/api/run/start", settings);
      applyStatus(data);
      $("protocol-line").textContent = "Starting…";
    } catch (err) {
      $("protocol-line").textContent = err.message;
    }
  });

  $("btnStop").addEventListener("click", async () => {
    try {
      applyStatus(await post("/api/run/stop"));
      $("protocol-line").textContent = "Stopping — retract then home.";
    } catch (err) {
      $("protocol-line").textContent = err.message;
    }
  });

  $("btnSelectNone").addEventListener("click", () => {
    state.selected.clear();
    document.querySelectorAll(".well").forEach((el) => el.classList.remove("selected"));
  });

  $("btnSelectRow0").addEventListener("click", () => {
    if (!state.layout) return;
    for (let i = 0; i < state.layout.num_x; i += 1) {
      state.selected.add(i);
      const el = document.querySelector(`.well[data-index="${i}"]`);
      if (el) el.classList.add("selected");
    }
  });

  $("btnOtGenerate").addEventListener("click", async () => {
    $("ot-msg").textContent = "Generating…";
    try {
      const data = await post("/api/ot/generate", collectOtSettings());
      state.otReady = true;
      $("btnOtDownload").disabled = false;
      $("ot-msg").textContent = "Protocol ready. Download it, then import in the Opentrons App.";
      if (state.status) {
        state.status.ot_protocol_ready = true;
        applyStatus(state.status);
      }
      applyStatus(await api("/api/status"));
    } catch (err) {
      $("ot-msg").textContent = err.message;
    }
  });

  $("btnOtDownload").addEventListener("click", () => {
    window.location = "/api/ot/download";
  });

  $("btnDownloadCsv").addEventListener("click", () => {
    window.location = "/api/results/csv";
  });

  socket.on("status", applyStatus);
  socket.on("step", (p) => {
    $("protocol-line").textContent = p.step || "";
  });
  socket.on("well", (p) => setWellState(p.index, p.state));
  socket.on("point", addPoint);
  socket.on("run_complete", async (p) => {
    $("protocol-line").textContent = p.status === "complete" ? "Run complete." : p.error || "Stopped.";
    $("results-hint").textContent = p.csv ? `Saved ${p.csv}` : "No CSV.";
    loadHistory();
  });
  socket.on("log", (p) => {
    if (p && p.message) $("protocol-line").textContent = p.message;
  });

  async function loadHistory() {
    try {
      const data = await api("/api/results");
      const ul = $("history-list");
      ul.innerHTML = "";
      (data.history || []).forEach((h) => {
        const li = document.createElement("li");
        li.textContent = `${h.ts || ""}  ${h.status || ""}  ${h.csv || ""}`;
        ul.appendChild(li);
      });
      if (data.csv) $("results-hint").textContent = `Last file: ${data.csv}`;
    } catch (_err) {
      /* ignore */
    }
  }

  async function boot() {
    initChart();
    fillVolumeTable({
      DMAm_volumes: [9.36, 1.83, 50, 50],
      AMPS_volumes: [62.72, 0, 50, 50],
      PBS_volumes: [185.92, 152.17, 50, 50],
      crosslinker_volumes: [12, 96, 50, 50],
      photoinitiator_volumes: [30, 30, 50, 50],
    });
    try {
      const layout = await api("/api/layout");
      renderWells(layout);
    } catch (err) {
      $("connect-summary").textContent = "Could not load well map: " + err.message;
    }
    try {
      const ports = await api("/api/ports");
      renderPorts(ports.ports, ports.remembered && ports.remembered.cnc_port);
      if (ports.remembered && ports.remembered.gdx_name) {
        renderDevices([{ name: ports.remembered.gdx_name, rssi: null }]);
        $("gdx-list").value = ports.remembered.gdx_name;
        $("force-msg").textContent = `Last sensor: ${ports.remembered.gdx_name}. Scan if you need a new one.`;
      }
    } catch (_err) {
      /* ignore */
    }
    try {
      applyStatus(await api("/api/status"));
    } catch (_err) {
      /* ignore */
    }
    loadHistory();
  }

  boot();
})();
