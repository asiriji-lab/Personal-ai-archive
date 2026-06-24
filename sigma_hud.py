"""
ZeroCostBrain — Sigma.js v2 Graph HUD Overlay
WebGL-accelerated UI for ultra-high performance knowledge graphs.
"""

_LEGEND = [
    ("Organization", "#818cf8"), ("Person", "#fbbf24"),
    ("Concept", "#34d399"), ("Technology", "#60a5fa"),
    ("Method", "#a78bfa"), ("Dataset", "#fb923c"),
    ("Model", "#22d3ee"), ("Paper", "#f472b6"),
]

def build_sigma_css():
    return """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
body { margin: 0; padding: 0; overflow: hidden; background: #0d1117; font-family: 'Inter', sans-serif; }
#sigma-container { width: 100vw; height: 100vh; background: #0d1117; }

.glass { background: rgba(13, 17, 23, 0.85); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; color: #f1f5f9; }
#hud { position: fixed; top: 16px; left: 16px; z-index: 1000; padding: 16px 20px; min-width: 270px; }
.hud-title { display: flex; align-items: center; gap: 8px; font-size: 15px; font-weight: 600; margin-bottom: 10px; }
.hud-stats { display: flex; gap: 14px; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #94a3b8; margin-bottom: 12px; }
.hud-stats .sv { color: #f1f5f9; font-weight: 500; }
.live-dot { width: 8px; height: 8px; background: #22c55e; border-radius: 50%; display: inline-block; animation: plive 2s ease-in-out infinite; margin-left: auto; }
@keyframes plive { 0%, 100% { opacity: 1; box-shadow: 0 0 4px #22c55e; } 50% { opacity: .4; box-shadow: 0 0 8px #22c55e; } }

#search-box { display: flex; align-items: center; background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 6px 10px; gap: 8px; }
#search-input { background: none; border: none; outline: none; color: #f1f5f9; font-size: 13px; width: 100%; }
.skbd { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #94a3b8; background: rgba(30, 41, 59, 0.8); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.1); white-space: nowrap; }

.hud-hints { margin-top: 8px; font-size: 10px; color: #475569; line-height: 1.6; }
.hud-hints kbd { background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(255,255,255,0.1); border-radius: 3px; padding: 1px 4px; font-family: 'JetBrains Mono', monospace; }

#legend { position: fixed; bottom: 16px; left: 16px; z-index: 1000; padding: 12px 16px; }
.legend-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 16px; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #94a3b8; }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

#custom-tooltip { display: none; position: fixed; z-index: 1500; padding: 12px 16px; max-width: 360px; font-size: 12px; pointer-events: none; box-shadow: 0 16px 40px -8px rgba(0, 0, 0, 0.6); }
.tt-name { font-weight: 700; font-size: 14px; margin-bottom: 6px; color: #ffffff; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 6px; word-break: break-word; }
.tt-desc { color: #94a3b8; font-size: 11px; line-height: 1.6; max-height: 120px; overflow: hidden; }
.tt-meta { margin-top: 6px; font-size: 10px; color: #475569; font-family: 'JetBrains Mono', monospace; }

#modern-loader { position: fixed; inset: 0; z-index: 3000; display: flex; flex-direction: column; align-items: center; justify-content: center; background: #0d1117; transition: opacity .6s ease; text-align: center; }
#modern-loader.hidden { opacity: 0; pointer-events: none; }
.loader-ring { width: 48px; height: 48px; border: 3px solid rgba(255, 255, 255, 0.07); border-top-color: #818cf8; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 16px; }
.loader-text { color: #94a3b8; font-size: 13px; font-family: 'JetBrains Mono', monospace; }
.loader-sub { color: #475569; font-size: 11px; margin-top: 6px; font-family: 'JetBrains Mono', monospace; }
.loader-error { color: #f87171; font-size: 12px; margin-top: 10px; display: none; max-width: 80%; }
@keyframes spin { to { transform: rotate(360deg); } }

#selection-info { display: none; position: fixed; top: 16px; right: 16px; z-index: 1000; padding: 12px 16px; min-width: 200px; font-size: 12px; }
.sel-name { font-weight: 600; font-size: 13px; color: #f8fafc; margin-bottom: 4px; word-break: break-word; }
.sel-meta { color: #64748b; font-size: 11px; font-family: 'JetBrains Mono', monospace; }
.sel-close { float: right; cursor: pointer; color: #475569; font-size: 16px; line-height: 1; margin-left: 8px; }
.sel-close:hover { color: #94a3b8; }

#stage-slider-wrap { margin-bottom: 8px; }
#stage-slider-wrap label { display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #64748b; margin-bottom: 4px; }
#stage-label { color: #94a3b8; font-family: 'JetBrains Mono', monospace; font-size: 10px; }
#stage-slider { -webkit-appearance: none; appearance: none; width: 100%; height: 4px; border-radius: 2px; background: rgba(30,41,59,0.8); border: 1px solid rgba(255,255,255,0.08); outline: none; cursor: pointer; }
#stage-slider::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 14px; height: 14px; border-radius: 50%; background: #818cf8; cursor: pointer; transition: background 0.2s; border: 2px solid rgba(255,255,255,0.15); }
#stage-slider::-webkit-slider-thumb:hover { background: #a78bfa; }
#stage-slider::-moz-range-thumb { width: 14px; height: 14px; border-radius: 50%; background: #818cf8; cursor: pointer; border: 2px solid rgba(255,255,255,0.15); }
#live-toggle { display: flex; align-items: center; gap: 6px; margin-top: 10px; padding: 6px 10px; background: rgba(30,41,59,0.6); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; cursor: pointer; font-size: 12px; color: #94a3b8; transition: all 0.2s; user-select: none; width: 100%; box-sizing: border-box; }
#live-toggle:hover { border-color: rgba(255,255,255,0.2); color: #cbd5e1; }
#live-toggle.active { background: rgba(34,197,94,0.12); border-color: rgba(34,197,94,0.4); color: #22c55e; }
.live-btn-dot { width: 7px; height: 7px; border-radius: 50%; background: #475569; flex-shrink: 0; transition: all 0.2s; }
#live-toggle.active .live-btn-dot { background: #22c55e; animation: live-pulse 1.2s ease-in-out infinite; }
@keyframes live-pulse { 0%,100% { box-shadow: 0 0 4px #22c55e; } 50% { box-shadow: 0 0 10px #22c55e; opacity: 0.6; } }
.live-hint { font-size: 10px; color: #475569; margin-left: auto; }
#live-toggle.active .live-hint { color: #166534; }

#force-slider-wrap { margin-top: 8px; }
#force-slider-wrap label { display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #64748b; margin-bottom: 4px; }
#force-label { color: #94a3b8; font-family: 'JetBrains Mono', monospace; font-size: 10px; }
#force-slider { -webkit-appearance: none; appearance: none; width: 100%; height: 4px; border-radius: 2px; background: rgba(30,41,59,0.8); border: 1px solid rgba(255,255,255,0.08); outline: none; cursor: pointer; }
#force-slider::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 14px; height: 14px; border-radius: 50%; background: #818cf8; cursor: pointer; transition: background 0.2s; border: 2px solid rgba(255,255,255,0.15); }
#force-slider::-webkit-slider-thumb:hover { background: #a78bfa; }
#force-slider::-moz-range-thumb { width: 14px; height: 14px; border-radius: 50%; background: #818cf8; cursor: pointer; border: 2px solid rgba(255,255,255,0.15); }
.slider-ends { display: flex; justify-content: space-between; font-size: 9px; color: #475569; margin-top: 2px; font-family: 'JetBrains Mono', monospace; }

#canvas-slider-wrap { margin-top: 8px; }
#canvas-slider-wrap label { display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #64748b; margin-bottom: 4px; }
#canvas-label { color: #94a3b8; font-family: 'JetBrains Mono', monospace; font-size: 10px; }
#canvas-slider { -webkit-appearance: none; appearance: none; width: 100%; height: 4px; border-radius: 2px; background: rgba(30,41,59,0.8); border: 1px solid rgba(255,255,255,0.08); outline: none; cursor: pointer; }
#canvas-slider::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 14px; height: 14px; border-radius: 50%; background: #60a5fa; cursor: pointer; transition: background 0.2s; border: 2px solid rgba(255,255,255,0.15); }
#canvas-slider::-webkit-slider-thumb:hover { background: #93c5fd; }
#canvas-slider::-moz-range-thumb { width: 14px; height: 14px; border-radius: 50%; background: #60a5fa; cursor: pointer; border: 2px solid rgba(255,255,255,0.15); }

#scale-toggle { display: flex; align-items: center; gap: 6px; margin-top: 6px; padding: 6px 10px; background: rgba(30,41,59,0.6); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; cursor: pointer; font-size: 12px; color: #94a3b8; transition: all 0.2s; user-select: none; width: 100%; box-sizing: border-box; }
#scale-toggle:hover { border-color: rgba(255,255,255,0.2); color: #cbd5e1; }
#scale-toggle.active { background: rgba(96,165,250,0.12); border-color: rgba(96,165,250,0.4); color: #60a5fa; }
.scale-btn-icon { font-family: 'JetBrains Mono', monospace; font-size: 10px; width: 20px; text-align: center; flex-shrink: 0; }
.scale-hint { font-size: 10px; color: #475569; margin-left: auto; font-family: 'JetBrains Mono', monospace; }
#scale-toggle.active .scale-hint { color: #1d4ed8; }
"""

def build_sigma_html(node_count, edge_count, stamp):
    legend = "".join(
        f'<div class="legend-item"><span class="legend-dot" style="background:{c}"></span>{n}</div>'
        for n, c in _LEGEND
    )
    return f"""
<div id="sigma-container"></div>
<div id="modern-loader">
    <div class="loader-ring"></div>
    <div class="loader-text">Loading graph data...</div>
    <div class="loader-sub" id="loader-sub"></div>
    <div class="loader-error"></div>
</div>
<div id="hud" class="glass">
  <div class="hud-title"><span>&#9883;</span><span>ZeroCostBrain</span><span class="live-dot"></span></div>
  <div class="hud-stats">
    <span><span class="sv" id="node-count">{node_count}</span> nodes</span>
    <span><span class="sv" id="edge-count">{edge_count}</span> edges</span>
    <span id="update-time" style="color:#475569;font-family:'JetBrains Mono',monospace;font-size:11px">{stamp}</span>
  </div>
  <div id="search-box">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="2.5" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
    <input id="search-input" type="text" placeholder="Search nodes..." autocomplete="off"/>
    <span class="skbd">Ctrl K</span>
  </div>
  <div class="hud-hints">
    <kbd>Click</kbd> node to highlight &nbsp;·&nbsp; <kbd>Esc</kbd> reset &nbsp;·&nbsp; <kbd>L</kbd> live
  </div>
  <div id="stage-slider-wrap">
    <label for="stage-slider">
      <span>Stage</span>
      <span id="stage-label">Wide</span>
    </label>
    <input id="stage-slider" type="range" min="0" max="100" value="100">
    <div class="slider-ends"><span>Compact</span><span>Wide</span></div>
  </div>
  <button id="live-toggle" title="Toggle live force simulation (L)">
    <span class="live-btn-dot"></span>
    <span>Live Mode</span>
    <span class="live-hint">Off</span>
  </button>
  <div id="force-slider-wrap">
    <label for="force-slider">
      <span>Force</span>
      <span id="force-label">Medium</span>
    </label>
    <input id="force-slider" type="range" min="0" max="100" value="50">
    <div class="slider-ends"><span>Calm</span><span>Wild</span></div>
  </div>
  <div id="canvas-slider-wrap">
    <label for="canvas-slider">
      <span>Canvas</span>
      <span id="canvas-label">1.0×</span>
    </label>
    <input id="canvas-slider" type="range" min="100" max="12800" value="100" step="10">
    <div class="slider-ends"><span>1×</span><span>128×</span></div>
  </div>
  <button id="scale-toggle" title="Toggle stage size between 32× and 128×">
    <span class="scale-btn-icon">⬡</span>
    <span>Stage Size</span>
    <span class="scale-hint" id="scale-hint">Wide</span>
  </button>
</div>
<div id="legend" class="glass"><div class="legend-grid">{legend}</div></div>
<div id="custom-tooltip" class="glass">
  <div class="tt-name"></div>
  <div class="tt-desc"></div>
  <div class="tt-meta"></div>
</div>
<div id="selection-info" class="glass">
  <span class="sel-close" id="sel-close" title="Deselect">&#x2715;</span>
  <div class="sel-name" id="sel-name"></div>
  <div class="sel-meta" id="sel-meta"></div>
</div>
"""

def build_sigma_js():
    return """
<script src="../lib/sigma/graphology.min.js"></script>
<script src="../lib/sigma/sigma.min.js"></script>
<script src="../lib/sigma/graphology-library.min.js"></script>
<script>
window.onload = function() {
    (async function() {
        const loader = document.getElementById("modern-loader");
        const loaderText = loader.querySelector(".loader-text");
        const loaderSub = document.getElementById("loader-sub");
        const loaderError = loader.querySelector(".loader-error");

        function setLoaderStatus(main, sub) {
            loaderText.innerText = main;
            if (sub !== undefined) loaderSub.innerText = sub;
        }

        if (typeof graphology === 'undefined' || typeof Sigma === 'undefined') {
            setLoaderStatus("Library Load Failed");
            loaderError.innerText = "Required libraries could not be loaded.";
            loaderError.style.display = "block";
            return;
        }

        const container = document.getElementById("sigma-container");
        const graph = new graphology.Graph({ multi: false });
        const hideLoader = () => setTimeout(() => loader.classList.add("hidden"), 600);

        try {
            setLoaderStatus("Loading graph data...");
            await new Promise(r => setTimeout(r, 10));

            const response = await fetch("graph_data.json");
            if (!response.ok) throw new Error("HTTP " + response.status + ": Failed to load graph_data.json");
            const data = await response.json();

            setLoaderStatus("Building graph...", data.nodes.length + " nodes · " + data.edges.length + " edges");
            await new Promise(r => setTimeout(r, 10));

            data.nodes.forEach(n => {
                graph.addNode(n.id, {
                    label: n.id,
                    size: Math.log(n.size) * 2,
                    color: n.color.background,
                    x: Math.random() * 1000 - 500,
                    y: Math.random() * 1000 - 500,
                    description: n.title
                });
            });

            data.edges.forEach(e => {
                if (graph.hasNode(e.source) && graph.hasNode(e.target) && !graph.hasEdge(e.source, e.target)) {
                    graph.addEdge(e.source, e.target, { size: 0.6 });
                }
            });

            // --- ForceAtlas2: synchronous pre-layout ---
            setLoaderStatus("Computing layout...", "~2s for " + graph.order + " nodes");
            await new Promise(r => setTimeout(r, 30)); // yield so browser repaints loader

            const fa2 = graphologyLibrary.layoutForceAtlas2;
            const fa2Settings = (fa2.inferSettings ? fa2.inferSettings(graph) : {});
            Object.assign(fa2Settings, {
                barnesHutOptimize: true,
                barnesHutTheta: 0.5,
                strongGravityMode: true,
                gravity: 0.05,
                scalingRatio: 10,
                slowDown: 1 + Math.log(Math.max(1, graph.order))
            });
            fa2.assign(graph, { iterations: 600, settings: fa2Settings });

            // Save settled positions so live mode can restart from a known layout
            const basePositions = new Map();
            graph.forEachNode((node, attrs) => basePositions.set(node, { x: attrs.x, y: attrs.y }));
            const origPositions = new Map(graph.nodes().map(n => [n, { ...basePositions.get(n) }]));
            let canvasScale = 1.0;

            // --- Interaction state ---
            const state = {
                selected: null,
                neighbors: null,
                searchMatches: null
            };

            // --- Live Animation State ---
            const liveFA2Settings = {
                barnesHutOptimize: true, barnesHutTheta: 0.5,
                strongGravityMode: true, gravity: 0.05,
                scalingRatio: 10, slowDown: 3
            };
            let liveLayout = null;
            let liveRafId = null;
            let liveActive = false;
            let liveTimeout = null;

            // Single nodeReducer referencing state (no setSetting swapping)
            function nodeReducer(node, data) {
                const res = { ...data };

                if (data._flashColor) {
                    return { ...res, color: data._flashColor, size: (data.size || 4) * 1.6, zIndex: 3 };
                }

                if (state.searchMatches) {
                    if (state.searchMatches.has(node)) return { ...res, forceLabel: true, zIndex: 1 };
                    return { ...res, color: "#0c111a", label: "", zIndex: 0 };
                }

                if (state.selected) {
                    if (node === state.selected) {
                        return { ...res, color: "#f8fafc", size: (data.size || 4) * 1.6, zIndex: 2, forceLabel: true };
                    }
                    if (state.neighbors && state.neighbors.has(node)) {
                        return { ...res, zIndex: 1, forceLabel: true };
                    }
                    return { ...res, color: "#111827", label: "", zIndex: 0 };
                }

                return res;
            }

            function edgeReducer(edge, data) {
                if (data._flashColor) {
                    return { ...data, color: data._flashColor, size: 2.5, zIndex: 2, hidden: false };
                }
                const base = { ...data, color: "rgba(148, 163, 184, 0.15)", size: 0.6 };

                if (state.searchMatches) {
                    return { ...base, hidden: true };
                }

                if (state.selected) {
                    const [s, t] = graph.extremities(edge);
                    if (s === state.selected || t === state.selected) {
                        return { ...base, color: "rgba(226, 232, 240, 0.75)", size: 0.9, zIndex: 1 };
                    }
                    return { ...base, hidden: true };
                }

                return base;
            }

            setLoaderStatus("Rendering...");
            await new Promise(r => setTimeout(r, 10));

            const renderer = new Sigma(graph, container, {
                // Performance
                zIndex: true,
                hideEdgesOnMove: true,
                hideLabelsOnMove: true,
                enableEdgeEvents: false,
                // Camera bounds
                minCameraRatio: 0.008,
                maxCameraRatio: 12,
                stagePadding: 50, // overridden below after getDimensions()
                // Edges
                defaultEdgeColor: "rgba(148, 163, 184, 0.15)",
                defaultEdgeType: "line",
                renderEdgeLabels: false,
                // Labels
                labelDensity: 0.07,
                labelGridCellSize: 60,
                labelRenderedSizeThreshold: 6,
                labelFont: "Inter, system-ui, sans-serif",
                labelSize: 12,
                labelWeight: "500",
                labelColor: { color: "#e2e8f0" },
                // Nodes
                defaultNodeColor: "#cbd5e1",
                // Reducers
                nodeReducer: nodeReducer,
                edgeReducer: edgeReducer
            });

            // Stage toggle: compact (padding=50) vs wide (2.5× area, negative padding)
            const { width: vw, height: vh } = renderer.getDimensions();
            const minDim = Math.min(vw, vh);
            const STAGE_COMPACT = 50;
            const STAGE_WIDE = (minDim - (minDim - 100) * Math.sqrt(2.5)) / 2;
            renderer.setSetting('stagePadding', STAGE_WIDE);
            renderer.process();

            // --- Tooltip ---
            const tt = document.getElementById("custom-tooltip");
            const ttName = tt.querySelector(".tt-name");
            const ttDesc = tt.querySelector(".tt-desc");
            const ttMeta = tt.querySelector(".tt-meta");

            function showTooltip(node) {
                const attr = graph.getNodeAttributes(node);
                const descMatch = (attr.description || "").match(/<b>.+?<\\/b>(?:<br>(.*))?/s);
                const descText = descMatch ? (descMatch[1] || "").replace(/<[^>]*>?/gm, "").trim() : "";
                ttName.innerText = node;
                ttDesc.innerText = descText;
                ttMeta.innerText = "degree " + graph.degree(node);
                tt.style.display = "block";
            }

            window.addEventListener("mousemove", (e) => {
                if (tt.style.display === "block") {
                    const tx = e.clientX + 18, ty = e.clientY - 8;
                    tt.style.left = (tx + tt.offsetWidth > window.innerWidth ? e.clientX - tt.offsetWidth - 8 : tx) + "px";
                    tt.style.top = (ty + tt.offsetHeight > window.innerHeight ? e.clientY - tt.offsetHeight - 8 : ty) + "px";
                }
            });

            function scheduleRedraw() {
                renderer.process();
                renderer.refresh();
            }

            // --- Live Animation ---
            function startLive() {
                if (liveActive) return;
                liveActive = true;
                renderer.setSetting('hideEdgesOnMove', false);
                renderer.setSetting('hideLabelsOnMove', false);
                if (!liveLayout) {
                    const s = Math.max(0.1, canvasScale);
                    liveLayout = new graphologyLibrary.FA2Layout(graph, { settings: {
                        ...liveFA2Settings,
                        scalingRatio: liveFA2Settings.scalingRatio * s * s,
                    }});
                }
                liveLayout.start();
                const FRAME_MS = 1000 / 30;
                let last = 0;
                function tick(ts) {
                    if (!liveActive) return;
                    if (ts - last >= FRAME_MS) { renderer.refresh(); last = ts; }
                    liveRafId = requestAnimationFrame(tick);
                }
                liveRafId = requestAnimationFrame(tick);
                liveTimeout = setTimeout(() => { if (liveActive) stopLive(); }, 5 * 60 * 1000);
                const btn = document.getElementById('live-toggle');
                btn.classList.add('active');
                btn.querySelector('.live-hint').textContent = 'On';
            }

            function stopLive() {
                if (!liveActive) return;
                liveActive = false;
                if (liveLayout) liveLayout.stop();
                if (liveRafId) { cancelAnimationFrame(liveRafId); liveRafId = null; }
                if (liveTimeout) { clearTimeout(liveTimeout); liveTimeout = null; }
                renderer.setSetting('hideEdgesOnMove', true);
                renderer.setSetting('hideLabelsOnMove', true);
                const btn = document.getElementById('live-toggle');
                btn.classList.remove('active');
                btn.querySelector('.live-hint').textContent = 'Off';
                scheduleRedraw();
            }

            function killLive() {
                if (!liveActive && !liveLayout) return;
                liveActive = false;
                if (liveLayout) { try { liveLayout.kill(); } catch(e) {} liveLayout = null; }
                if (liveRafId) { cancelAnimationFrame(liveRafId); liveRafId = null; }
                if (liveTimeout) { clearTimeout(liveTimeout); liveTimeout = null; }
                renderer.setSetting('hideEdgesOnMove', true);
                renderer.setSetting('hideLabelsOnMove', true);
                const btn = document.getElementById('live-toggle');
                if (btn) { btn.classList.remove('active'); btn.querySelector('.live-hint').textContent = 'Off'; }
            }

            function lerp(a, b, t) { return a + (b - a) * t; }

            function interpolateForce(val) {
                const PRESETS = [
                    { slowDown: 8, gravity: 0.08 },
                    { slowDown: 3, gravity: 0.05 },
                    { slowDown: 1, gravity: 0.01 }
                ];
                const labels = ['Calm', 'Medium', 'Active', 'Wild'];
                const labelIdx = Math.round(val / 33.3);
                if (val <= 50) {
                    const t = val / 50;
                    return { slowDown: lerp(PRESETS[0].slowDown, PRESETS[1].slowDown, t), gravity: lerp(PRESETS[0].gravity, PRESETS[1].gravity, t), label: labels[Math.min(1, labelIdx)] };
                } else {
                    const t = (val - 50) / 50;
                    return { slowDown: lerp(PRESETS[1].slowDown, PRESETS[2].slowDown, t), gravity: lerp(PRESETS[1].gravity, PRESETS[2].gravity, t), label: labels[2 + (t >= 0.5 ? 1 : 0)] };
                }
            }

            // --- Hover: tooltip only, no graph redraw ---
            renderer.on("enterNode", ({ node }) => { showTooltip(node); });
            renderer.on("leaveNode", () => { tt.style.display = "none"; });

            // --- Click to select / deselect ---
            const selInfo = document.getElementById("selection-info");
            const selName = document.getElementById("sel-name");
            const selMeta = document.getElementById("sel-meta");

            function selectNode(node) {
                state.selected = node;
                state.neighbors = new Set([node, ...graph.neighbors(node)]);
                selName.innerText = node;
                const deg = graph.degree(node);
                selMeta.innerText = deg + " connection" + (deg !== 1 ? "s" : "");
                selInfo.style.display = "block";
                showTooltip(node);
                scheduleRedraw();
            }

            function clearSelection() {
                state.selected = null;
                state.neighbors = null;
                selInfo.style.display = "none";
                scheduleRedraw();
            }

            renderer.on("clickNode", ({ node }) => {
                if (state.selected === node) { clearSelection(); return; }
                selectNode(node);
            });

            renderer.on("clickStage", () => {
                if (state.selected) clearSelection();
            });

            document.getElementById("sel-close").addEventListener("click", clearSelection);

            // --- Stage Slider ---
            function applyStage(t) {
                const padding = STAGE_COMPACT + (STAGE_WIDE - STAGE_COMPACT) * t;
                const label = t < 0.25 ? 'Compact' : t < 0.75 ? 'Medium' : 'Wide';
                document.getElementById('stage-label').textContent = label;
                document.getElementById('stage-slider').value = Math.round(t * 100);
                renderer.setSetting('stagePadding', padding);
                renderer.refresh();
                // sync stage size toggle: active = Wide (t=1), inactive = Compact (t=0)
                const btn = document.getElementById('scale-toggle');
                btn.classList.toggle('active', t > 0.75);
                document.getElementById('scale-hint').textContent = t > 0.75 ? 'Wide' : 'Compact';
            }
            document.getElementById('stage-slider').addEventListener('input', (e) => {
                applyStage(Number(e.target.value) / 100);
            });

            // --- Live Toggle ---
            document.getElementById('live-toggle').addEventListener('click', () => {
                liveActive ? stopLive() : startLive();
            });

            let _forceCommitTimer = null;
            document.getElementById('force-slider').addEventListener('input', (e) => {
                const { slowDown, gravity, label } = interpolateForce(Number(e.target.value));
                document.getElementById('force-label').textContent = label;
                liveFA2Settings.slowDown = slowDown;
                liveFA2Settings.gravity = gravity;
                clearTimeout(_forceCommitTimer);
                _forceCommitTimer = setTimeout(() => {
                    if (liveActive) {
                        killLive();
                        liveLayout = null;
                        startLive();
                    }
                }, 150);
            });

            // --- Canvas Scale ---
            let _scaleRafId = null;
            let _scaleCommitTimer = null;
            let _wasLiveBeforeScale = false;

            function _scalePreviewFrame() {
                _scaleRafId = null;
                renderer.getCamera().setState({ x: 0.5, y: 0.5, ratio: 1 / canvasScale });
                renderer.refresh();
            }

            function applyCanvasScalePreview(scale) {
                canvasScale = scale;
                document.getElementById('canvas-label').textContent = scale.toFixed(1) + '×';
                document.getElementById('canvas-slider').value = Math.round(scale * 100);
                if (_scaleRafId) return;
                _scaleRafId = requestAnimationFrame(_scalePreviewFrame);
            }

            function commitCanvasScale() {
                clearTimeout(_scaleCommitTimer);
                _scaleCommitTimer = null;
                if (_scaleRafId) { cancelAnimationFrame(_scaleRafId); _scaleRafId = null; }
                if (liveActive) killLive();
                // Reset to original settled positions, then re-layout with scale-adjusted repulsion
                graph.forEachNode((node) => {
                    const orig = origPositions.get(node);
                    if (orig) { graph.setNodeAttribute(node, 'x', orig.x); graph.setNodeAttribute(node, 'y', orig.y); }
                });
                const s = Math.max(0.1, canvasScale);
                graphologyLibrary.layoutForceAtlas2.assign(graph, {
                    iterations: 150,
                    settings: {
                        barnesHutOptimize: true, barnesHutTheta: 0.5,
                        strongGravityMode: true,
                        gravity: liveFA2Settings.gravity,
                        scalingRatio: liveFA2Settings.scalingRatio * s * s,
                        slowDown: 1 + Math.log(Math.max(1, graph.order)),
                    }
                });
                renderer.process();
                renderer.getCamera().animate({ x: 0.5, y: 0.5, ratio: 1 }, { duration: 300 });
                if (_wasLiveBeforeScale) {
                    _wasLiveBeforeScale = false;
                    startLive();
                }
            }

            document.getElementById('canvas-slider').addEventListener('mousedown', () => {
                _wasLiveBeforeScale = liveActive;
            });
            document.getElementById('canvas-slider').addEventListener('input', (e) => {
                applyCanvasScalePreview(Number(e.target.value) / 100);
                clearTimeout(_scaleCommitTimer);
                _scaleCommitTimer = setTimeout(commitCanvasScale, 150);
            });
            document.getElementById('canvas-slider').addEventListener('change', () => {
                commitCanvasScale();
            });

            // Stage size toggle: Compact (STAGE_COMPACT) ↔ Wide (STAGE_WIDE). Nodes don't move.
            let stageSizeExpanded = true; // starts Wide (matches startup default)
            document.getElementById('scale-toggle').addEventListener('click', () => {
                stageSizeExpanded = !stageSizeExpanded;
                applyStage(stageSizeExpanded ? 1 : 0);
            });

            window.addEventListener('beforeunload', () => {
                if (liveLayout) { liveLayout.kill(); liveLayout = null; }
            });

            // --- Keyboard shortcuts ---
            document.addEventListener("keydown", (e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === "k") {
                    e.preventDefault();
                    document.getElementById("search-input").focus();
                }
                if (e.key === "Escape") {
                    clearSelection();
                    const si = document.getElementById("search-input");
                    if (si.value) {
                        si.value = "";
                        state.searchMatches = null;
                        scheduleRedraw();
                    }
                }
                if (e.key === "l" && !e.ctrlKey && !e.metaKey && document.activeElement !== document.getElementById("search-input")) {
                    e.preventDefault();
                    liveActive ? stopLive() : startLive();
                }
            });

            // --- Search ---
            const searchInput = document.getElementById("search-input");
            searchInput.addEventListener("input", () => {
                const q = searchInput.value.toLowerCase().trim();
                if (!q) {
                    state.searchMatches = null;
                    scheduleRedraw();
                    return;
                }
                state.searchMatches = new Set(
                    graph.nodes().filter(nid => nid.toLowerCase().includes(q))
                );
                scheduleRedraw();
            });

            // --- Live reload polling (for --watch mode) ---
            let lastModified = "";
            setInterval(async () => {
                try {
                    const head = await fetch("graph_data.json", { method: "HEAD", cache: "no-cache" });
                    const lm = head.headers.get("Last-Modified") || head.headers.get("ETag");
                    if (lm && lm === lastModified) return;
                    lastModified = lm;

                    const r = await fetch("graph_data.json?t=" + Date.now());
                    const d = await r.json();

                    const currentNodes = new Set(graph.nodes());
                    const newNodeMap = new Map(d.nodes.map(n => [n.id, n]));
                    const edgeKey = (s, t) => s < t ? s + "||" + t : t + "||" + s;
                    const currentEdges = new Map();
                    graph.forEachEdge((eid, attrs, src, tgt) => currentEdges.set(edgeKey(src, tgt), eid));
                    const newEdgeSet = new Set(d.edges.map(e => edgeKey(e.source, e.target)));

                    // Flash removed nodes red, then drop
                    currentNodes.forEach(nid => {
                        if (!newNodeMap.has(nid)) {
                            graph.setNodeAttribute(nid, '_flashColor', '#ef4444');
                            setTimeout(() => {
                                if (graph.hasNode(nid)) graph.dropNode(nid);
                                if (!liveActive) scheduleRedraw();
                            }, 1500);
                        }
                    });

                    // Flash removed edges red, then drop
                    currentEdges.forEach((eid, key) => {
                        if (!newEdgeSet.has(key)) {
                            graph.setEdgeAttribute(eid, '_flashColor', '#ef4444');
                            setTimeout(() => {
                                if (graph.hasEdge(eid)) graph.dropEdge(eid);
                                if (!liveActive) scheduleRedraw();
                            }, 1500);
                        }
                    });

                    // Add new nodes with green flash, then revert
                    d.nodes.forEach(n => {
                        if (!graph.hasNode(n.id)) {
                            graph.addNode(n.id, {
                                label: n.id, size: Math.log(n.size) * 2, color: "#22c55e",
                                x: Math.random() * 1000 - 500,
                                y: Math.random() * 1000 - 500,
                                description: n.title
                            });
                            setTimeout(() => {
                                if (graph.hasNode(n.id)) graph.setNodeAttribute(n.id, "color", n.color.background);
                                if (!liveActive) scheduleRedraw();
                            }, 2000);
                        } else {
                            graph.setNodeAttribute(n.id, "size", Math.log(n.size) * 2);
                            graph.setNodeAttribute(n.id, "description", n.title);
                        }
                    });

                    // Add new edges with green flash, then revert
                    d.edges.forEach(e => {
                        if (graph.hasNode(e.source) && graph.hasNode(e.target) && !graph.hasEdge(e.source, e.target)) {
                            const eid = graph.addEdge(e.source, e.target, { size: 2.5, _flashColor: '#22c55e' });
                            setTimeout(() => {
                                if (graph.hasEdge(eid)) {
                                    graph.setEdgeAttribute(eid, '_flashColor', null);
                                    graph.setEdgeAttribute(eid, 'size', 0.6);
                                }
                                if (!liveActive) scheduleRedraw();
                            }, 2000);
                        }
                    });

                    document.getElementById("node-count").innerText = d.nodes.length;
                    document.getElementById("edge-count").innerText = d.edges.length;
                    document.getElementById("update-time").innerText = new Date().toISOString().substring(11, 19);
                    if (!liveActive) scheduleRedraw();
                } catch(e) {}
            }, 3000);

            hideLoader();

        } catch (err) {
            console.error("Sigma Startup Error:", err);
            setLoaderStatus("Load Failed");
            loaderError.innerText = err.message;
            loaderError.style.display = "block";
        }
    })();
};
</script>
"""
