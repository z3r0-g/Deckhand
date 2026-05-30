// ---------------------------------------------------------
// GLOBAL STATE
// ---------------------------------------------------------
window.deckhandHasLoaded = false;

let showOnlyUpdates = true;
let searchTerm = "";
let lastLogs = {};
let currentContainerData = [];

let loadingMessages = [];
let emptyMessages = [];

let loadingInterval = null;

let UI_MODE = window.deckhandUiMode || "fun";

const heatMeta = {
    pro: {
        0: { icon: "✔️", label: "OK",        tip: "Up to date" },
        1: { icon: "⬆️", label: "PATCH",     tip: "Patch update available" },
        2: { icon: "🔧", label: "MINOR",     tip: "Minor update available" },
        3: { icon: "⚠️", label: "MAJOR",     tip: "Major update available" },
        4: { icon: "🔥", label: "CRITICAL",  tip: "Critical update or CVEs" }
    },
    fun: {
        0: { icon: "🧊", label: "COOL",      tip: "Chillin'" },
        1: { icon: "🌡️", label: "WARM",     tip: "A little spicy" },
        2: { icon: "🔥", label: "HOT",       tip: "Getting toasty" },
        3: { icon: "⚠️🔥", label: "BURNING", tip: "This is fine 🔥🐶" },
        4: { icon: "🌋", label: "STREAMING", tip: "Meltdown imminent" }
    }
};


// ---------------------------------------------------------
// ROTATING MESSAGE LOADERS
// ---------------------------------------------------------
async function initLoadingMessages() {
    try {
        const res = await fetch("/static/loading_messages.json");
        const json = await res.json();
        loadingMessages = json.messages || [];
    } catch {
        loadingMessages = ["Loading Deckhand..."];
    }
}

async function initEmptyMessages() {
    try {
        const res = await fetch("/static/empty_messages.json");
        const json = await res.json();
        emptyMessages = json.messages || [];
    } catch {
        emptyMessages = ["Deck's clean, shipshape, and ready to sail!"];
    }
}


// ---------------------------------------------------------
// LOADING SCREEN
// ---------------------------------------------------------
function showLoading() {
    const overlay = document.getElementById("loading-overlay");
    const text = document.getElementById("loading-text");
    overlay.style.display = "flex";
    overlay.style.flexDirection = "column";
    overlay.style.alignItems = "center";
    overlay.style.justifyContent = "center";
    let existingLogo = overlay.querySelector(".loading-logo");
    if (!existingLogo) {
        const logoImg = document.createElement("img");
        logoImg.src = "/static/Deckhand.png";
        logoImg.alt = "Deckhand Logo";
        logoImg.classList.add("loading-logo");
        logoImg.style.maxWidth = "min(280px, 70vw)";
        logoImg.style.maxHeight = "25vh";
        logoImg.style.padding = "1.5rem";
        logoImg.style.width = "auto";
        logoImg.style.objectFit = "contain";
        logoImg.style.marginBottom = "10px";
        overlay.insertBefore(logoImg, text);
    }
    overlay.classList.remove("hidden");
    if (loadingInterval) clearInterval(loadingInterval);

    // Ensure text scales responsively
    text.style.fontSize = "clamp(1.2rem, 4vw, 2.5rem)";
    text.style.padding = "0 20px";

    loadingInterval = setInterval(() => {
        if (loadingMessages.length === 0) return;
        text.textContent =
            loadingMessages[Math.floor(Math.random() * loadingMessages.length)];
    }, 2000);
}
function hideLoading() {
    const overlay = document.getElementById("loading-overlay");
    overlay.classList.add("hidden");

    if (loadingInterval) clearInterval(loadingInterval);

    window.deckhandHasLoaded = true;
}


// ---------------------------------------------------------
// RENDER STATUS
// ---------------------------------------------------------
function renderStatus(data) {
    hideLoading();

    const root = document.getElementById("deckhand");
    root.innerHTML = "";

    updateSummary(data);

    const filtered = data.filter(c => {
        const matchesUpdate = !showOnlyUpdates || c.update_available;
        const matchesSearch = (c.name + " " + c.image).toLowerCase().includes(searchTerm.toLowerCase());
        return matchesUpdate && matchesSearch;
    });

    // EMPTY STATE
    if (filtered.length === 0) {
        const msg = emptyMessages.length
            ? emptyMessages[Math.floor(Math.random() * emptyMessages.length)]
            : "Yar deck be clean, Cap'n!";

        const div = document.createElement("div");
        div.className = "empty-state";
        div.textContent = msg;

        root.appendChild(div);
        return;
    }

    // NORMAL RENDER
    filtered.forEach(c => {
        const card = document.createElement("div");
        card.className = "card";
        card.setAttribute("data-id", c.container_id);

        const mode = UI_MODE === "pro" ? "pro" : "fun";
        const meta = heatMeta[mode][c.heat] || heatMeta[mode][0];

        card.innerHTML = `
            <div class="name">${c.name}</div>
            <div class="image">${c.image}</div>

            <div class="tag">Host: ${c.endpoint_name || "n/a"}</div>
            <div class="tag">Latest: ${c.latest_tag || "n/a"}</div>

            <div class="heat heat-${c.heat}" title="${meta.tip}">
                <span class="heat-icon">${meta.icon}</span>
                <span class="heat-label">${meta.label}</span>
            </div>

            ${
                c.update_available
                    ? `<button onclick="updateContainer('${c.container_id}')">Update</button>`
                    : ``
            }

            <button onclick="viewEvents('${c.container_id}')">Events</button>
        `;

        root.appendChild(card);
    });
}
// Update Summary Stats (Bottom Tool Bar)
function updateSummary(data) {
    const bar = document.getElementById("summary-stats");
    if (!bar) return;

    const total = data.length;
    const outdated = data.filter(c => c.update_available).length;
    const healthy = total - outdated;
    const critical = data.filter(c => c.heat === 4).length;

    bar.innerHTML = `
        <div class="stat-item">Total: <span>${total}</span></div>
        <div class="stat-item">Outdated: <span class="warn">${outdated}</span></div>
        <div class="stat-item">Critical: <span class="danger">${critical}</span></div>
        <div class="stat-item">Healthy: <span class="success">${healthy}</span></div>
        <button id="prune-btn" onclick="confirmPrune()" style="margin-left:15px; font-size:0.7rem; padding:4px 8px; background:#b30000;">Prune Images</button>
    `;
}


// ---------------------------------------------------------
// POLLING
// ---------------------------------------------------------
async function loadStatus() {
    try {
        const res = await fetch("/api/containers/status");
        const data = await res.json();
        currentContainerData = data;
        renderStatus(data);
    } catch (e) {
        console.error("Polling error:", e);
    }
}

// ---------------------------------------------------------
// UPDATE CONTAINER
// ---------------------------------------------------------
async function updateContainer(id) {
    const card = document.querySelector(`[data-id="${id}"]`);
    if (!card) return;

    card.classList.add("updating");

    const overlay = document.createElement("div");
    overlay.className = "update-overlay";
    overlay.innerHTML = `<div class="spinner"></div><div class="msg">Updating…</div>`;
    card.appendChild(overlay);

    const btn = card.querySelector("button");
    if (btn) btn.disabled = true;

    const res = await fetch(`/api/containers/${id}/update`, { method: "POST" });
    const json = await res.json();

    lastLogs[id] = json.log || ["No logs returned"];

    if (!res.ok) {
        overlay.innerHTML = `<div class="msg fail">Update Failed</div>`;
        setTimeout(() => {
            card.classList.remove("updating");
            overlay.remove();
            if (btn) btn.disabled = false;
        }, 2000);
        return;
    }

    overlay.innerHTML = `<div class="msg success">Updated!</div>`;

    setTimeout(() => {
        overlay.remove();
        card.classList.remove("updating");
        loadStatus();
    }, 1500);
}


// ---------------------------------------------------------
// UPDATE ALL
// ---------------------------------------------------------
const updateAllBtn = document.getElementById("update-all");
if (updateAllBtn) {
    updateAllBtn.addEventListener("click", async () => {
        const res = await fetch("/api/containers/status");
        const data = await res.json();

        const outdated = data.filter(c => c.update_available);

        if (outdated.length === 0) {
            alert("No containers need updating.");
            return;
        }

        const names = outdated.map(c => `• ${c.name}`).join("\n");

        const ok = confirm(
            `Update ALL outdated containers?\n\nThis will update:\n${names}\n\nProceed?`
        );

        if (!ok) return;

        for (const c of outdated) {
            await updateContainer(c.container_id);
        }
    });
}


// ---------------------------------------------------------
// FILTER TOGGLE
// ---------------------------------------------------------
const filterToggle = document.getElementById("filter-toggle");
if (filterToggle) {
    filterToggle.textContent = showOnlyUpdates ? "Show: Outdated" : "Show: All";
    filterToggle.addEventListener("click", () => {
        showOnlyUpdates = !showOnlyUpdates;
        filterToggle.textContent = showOnlyUpdates ? "Show: Outdated" : "Show: All";
        renderStatus(currentContainerData);
    });
}

const searchBtn = document.getElementById("search-btn");
const searchInput = document.getElementById("search-input");
const summaryStats = document.getElementById("summary-stats");

if (searchBtn && searchInput && summaryStats) {
    searchInput.value = searchTerm;

    searchBtn.addEventListener("click", () => {
        searchBtn.classList.add("hidden");
        summaryStats.classList.add("hidden");
        searchInput.classList.remove("hidden");
        searchInput.focus();
    });

    searchInput.addEventListener("input", (e) => {
        searchTerm = e.target.value;
        renderStatus(currentContainerData);
    });

    searchInput.addEventListener("blur", () => {
        searchInput.classList.add("hidden");
        searchBtn.classList.remove("hidden");
        summaryStats.classList.remove("hidden");
    });
}


// ---------------------------------------------------------
// MODAL - LOGS
// ---------------------------------------------------------
async function viewEvents(id) {
    const modal = document.getElementById("log-modal");
    const body = document.getElementById("log-body");
    if (!modal || !body) return;

    document.getElementById("log-title").textContent = `Events & History: ${id}`;
    body.innerHTML = '<div class="loading">Loading timeline...</div>';
    modal.classList.remove("hidden");

    try {
        // Fetch Intelligence Events (Phase 2) and Manual Update History (Phase 1)
        const [evRes, histRes] = await Promise.all([
            fetch(`/api/containers/${id}/events`),
            fetch(`/api/containers/${id}/history`)
        ]);

        const events = await evRes.json() || [];
        const history = await histRes.json() || [];

        // Standardize data for a unified timeline
        let combined = [];

        events.forEach(event => {
            combined.push({
                time: new Date(event.timestamp),
                type: event.event_type,
                payload: event.payload,
                icon: event.event_type.includes("mismatch") ? "⚠️" : (event.event_type.includes("bump") ? "🚀" : "🔔")
            });
        });

        history.forEach(entry => {
            combined.push({
                time: new Date(entry.timestamp * 1000),
                type: "manual_update",
                payload: { from: entry.old_tag, to: entry.new_tag, digest: entry.new_digest },
                icon: "🛠️"
            });
        });

        // Sort chronologically (newest first)
        combined.sort((a, b) => b.time - a.time);

        if (combined.length === 0) {
            body.innerHTML = '<div class="empty-state">No events or update history recorded.</div>';
            return;
        }

        body.innerHTML = "";

        // Filter Controls
        const filterBar = document.createElement("div");
        filterBar.className = "modal-filters";
        filterBar.innerHTML = `
            <button class="filter-btn active" data-filter="all">All</button>
            <button class="filter-btn" data-filter="manual">Manual Updates</button>
            <button class="filter-btn" data-filter="auto">Automated Alerts</button>
        `;
        body.appendChild(filterBar);

        const timelineRoot = document.createElement("div");
        body.appendChild(timelineRoot);

        const renderTimeline = (filterType) => {
            timelineRoot.innerHTML = "";
            
            const filtered = combined.filter(item => {
                if (filterType === 'all') return true;
                if (filterType === 'manual') return item.type === 'manual_update';
                if (filterType === 'auto') return item.type !== 'manual_update';
                return true;
            });

            if (filtered.length === 0) {
                timelineRoot.innerHTML = '<div class="empty-state">No matching events found.</div>';
            } else {
                filtered.forEach(item => {
                    const div = document.createElement("div");
                    div.className = "timeline-item";
                    
                    let detailsHtml = "";
                    if (item.payload && typeof item.payload === 'object') {
                        detailsHtml = Object.entries(item.payload).map(([k, v]) => 
                            `<span class="detail-chip"><b>${k}:</b> ${v}</span>`
                        ).join("");
                    }

                    div.innerHTML = `
                        <div class="timeline-marker">${item.icon}</div>
                        <div class="timeline-content">
                            <div class="timeline-header">
                                <span class="event-type">${item.type.replace(/_/g, ' ')}</span>
                                <span class="event-time">${item.time.toLocaleTimeString()} - ${item.time.toLocaleDateString()}</span>
                            </div>
                            <div class="event-details">${detailsHtml}</div>
                        </div>
                    `;
                    timelineRoot.appendChild(div);
                });
            }

            // Show session logs only when viewing manual or all events
            if (filterType !== 'auto' && lastLogs[id]) {
                const sessionLog = document.createElement("div");
                sessionLog.className = "session-logs";
                sessionLog.innerHTML = `
                    <hr>
                    <div style="font-size: 0.75rem; opacity: 0.6; margin: 10px 0;">Raw Output (Current Session):</div>
                    <pre style="background: rgba(0,0,0,0.1); padding: 8px; border-radius: 4px; font-size: 0.7rem;">${lastLogs[id].join('\n')}</pre>
                `;
                timelineRoot.appendChild(sessionLog);
            }
        };

        // Bind Filter Events
        filterBar.querySelectorAll(".filter-btn").forEach(btn => {
            btn.onclick = () => {
                filterBar.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                renderTimeline(btn.dataset.filter);
            };
        });

        // Initial Render
        renderTimeline('all');
    } catch (e) {
        body.innerHTML = '<div class="error">Failed to load audit history.</div>';
    }
}

const closeLogBtn = document.getElementById("close-log");
if (closeLogBtn) {
    closeLogBtn.addEventListener("click", () => {
        const modal = document.getElementById("log-modal");
        if (modal) modal.classList.add("hidden");
    });
}

const closeHistoryBtn = document.getElementById("close-history");
if (closeHistoryBtn) {
    closeHistoryBtn.addEventListener("click", () => {
        const modal = document.getElementById("history-modal");
        if (modal) modal.classList.add("hidden");
    });
}


// ---------------------------------------------------------
// SSE LIVE UPDATES
// ---------------------------------------------------------
const evtSource = new EventSource("/api/stream/status");

evtSource.onmessage = event => {
    try {
        currentContainerData = JSON.parse(event.data);
        renderStatus(currentContainerData);
    } catch (e) {
        console.error("SSE parse error", e);
    }
};


// ---------------------------------------------------------
// INITIALIZE MESSAGES
// ---------------------------------------------------------
async function init() {
    showLoading();
    await Promise.all([
        initLoadingMessages(),
        initEmptyMessages(),
        loadStatus()
    ]);
}

init();
setInterval(loadStatus, 15000);


// ---------------------------------------------------------
// MANUAL REFRESH
// ---------------------------------------------------------
const refreshBtn = document.getElementById("refresh-status");
if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
        refreshBtn.disabled = true;
        refreshBtn.textContent = "Refreshing…";

        loadStatus().finally(() => {
            setTimeout(() => {
                refreshBtn.disabled = false;
                refreshBtn.textContent = "Refresh";
            }, 600);
        });
    });
}


// ---------------------------------------------------------
// SCHEDULER SETTINGS
// ---------------------------------------------------------
const schedulerSettingsBtn = document.getElementById("scheduler-settings");
if (schedulerSettingsBtn) {
    schedulerSettingsBtn.addEventListener("click", async () => {
        const res = await fetch("/api/scheduler/config");
        const cfg = await res.json();

        document.getElementById("sched-enabled").checked = cfg.enabled;
        document.getElementById("sched-interval").value = cfg.interval_minutes;

        document.getElementById("scheduler-modal").classList.remove("hidden");
    });
}

const schedSaveBtn = document.getElementById("sched-save");
if (schedSaveBtn) {
    schedSaveBtn.addEventListener("click", async () => {
        const enabled = document.getElementById("sched-enabled").checked;
        const interval = parseInt(document.getElementById("sched-interval").value);

        await fetch("/api/scheduler/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                enabled,
                interval_minutes: interval
            })
        });

        document.getElementById("scheduler-modal").classList.add("hidden");
        loadStatus();
    });
}

const schedCloseBtn = document.getElementById("sched-close");
if (schedCloseBtn) {
    schedCloseBtn.addEventListener("click", () => {
        document.getElementById("scheduler-modal").classList.add("hidden");
    });
}

// ---------------------------------------------------------
// MAINTENANCE - PRUNE
// ---------------------------------------------------------
async function confirmPrune() {
    const modal = document.getElementById("log-modal");
    const body = document.getElementById("log-body");
    if (!modal || !body) return;

    document.getElementById("log-title").textContent = "Maintenance: Prune Unused Images";
    body.innerHTML = '<div class="loading">Scanning for dangling images...</div>';
    modal.classList.remove("hidden");

    try {
        const res = await fetch("/api/maintenance/prune/dry-run");
        const dangling = await res.json();

        if (dangling.length === 0) {
            body.innerHTML = '<div class="empty-state">No dangling images found. Your deck is clean!</div>';
            return;
        }

        let list = dangling.map(img => `• [${img.endpoint}] ${img.id.substring(7, 19)} (${img.tags && img.tags.length ? img.tags[0] : 'dangling'})`).join('\n');
        
        body.innerHTML = `
            <p>The following images are unused across your endpoints and can be safely removed:</p>
            <pre style="background:rgba(0,0,0,0.2); padding:10px; border-radius:4px; font-size:0.8rem; overflow-x:auto;">${list}</pre>
            <button id="exec-prune" style="width:100%; margin-top:15px; padding:12px; background:#b30000; font-weight:bold;">Confirm & Prune Now</button>
        `;

        document.getElementById("exec-prune").onclick = async () => {
            body.innerHTML = '<div class="loading">Pruning... this may take a moment.</div>';
            const pRes = await fetch("/api/maintenance/prune", { method: "POST" });
            const result = await pRes.json();
            body.innerHTML = `<div class="msg success">Prune Complete!</div><pre style="font-size:0.7rem; margin-top:10px;">${JSON.stringify(result, null, 2)}</pre>`;
        };
    } catch (e) {
        body.innerHTML = '<div class="msg fail">Failed to scan for prunable images.</div>';
    }
}
