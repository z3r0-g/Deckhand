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

            <button onclick="viewLogs('${c.container_id}')">Logs</button>
            <button onclick="viewHistory('${c.container_id}')">History</button>
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
function viewLogs(id) {
    const modal = document.getElementById("log-modal");
    if (!modal) return;

    document.getElementById("log-title").textContent = `Logs for ${id}`;
    document.getElementById("log-body").textContent =
        (lastLogs[id] || ["No logs available"]).join("\n");

    modal.classList.remove("hidden");
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
// MODAL - HISTORY
// ---------------------------------------------------------
function viewHistory(id) {
    const modal = document.getElementById("history-modal");
    if (!modal) return;

    const body = document.getElementById("history-body");

    document.getElementById("history-title").textContent =
        `Update history for ${id}`;
    body.textContent = "Loading history…";

    modal.classList.remove("hidden");

    fetch(`/api/containers/${id}/history`)
        .then(res => res.json())
        .then(items => {
            if (!items || items.length === 0) {
                body.textContent = "No update history recorded.";
                return;
            }

            body.textContent = items
                .map(entry => {
                    const dt = new Date(entry.timestamp * 1000).toLocaleString();
                    return [
                        `Time:   ${dt}`,
                        `Tag:    ${entry.old_tag || "n/a"} → ${entry.new_tag || "n/a"}`,
                        `Digest: ${entry.old_digest || "n/a"} → ${entry.new_digest || "n/a"}`,
                        ``
                    ].join("\n");
                })
                .join("\n");
        })
        .catch(() => {
            body.textContent = "Failed to load history.";
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
