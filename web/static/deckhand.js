// ---------------------------------------------------------
// GLOBAL STATE
// ---------------------------------------------------------
window.deckhandHasLoaded = false;

let showOnlyUpdates = false;
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
        0: { icon: "🧊", label: "COOL",      tip: "Chillin’" },
        1: { icon: "🌡️", label: "WARM",     tip: "A little spicy" },
        2: { icon: "🔥", label: "HOT",       tip: "Getting toasty" },
        3: { icon: "⚠️🔥", label: "BURNING", tip: "This is fine 🔥🐶" },
        4: { icon: "🌋", label: "STREAMING", tip: "Meltdown imminent" }
    }
};


// ---------------------------------------------------------
// LOADING + EMPTY MESSAGE LOADERS
// ---------------------------------------------------------
async function initLoadingMessages() {
    try {
        const res = await fetch("/web/static/loading_messages.json");
        const json = await res.json();
        loadingMessages = json.messages || [];
    } catch {
        loadingMessages = ["Loading Deckhand..."];
    }
}

async function initEmptyMessages() {
    try {
        const res = await fetch("/web/static/empty_messages.json");
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

    // Ensure the overlay stacks elements vertically and centers them
    overlay.style.display = "flex";
    overlay.style.flexDirection = "column";
    overlay.style.alignItems = "center";
    overlay.style.justifyContent = "center";

    // Add the Deckhand logo above the loading text if it doesn't already exist
    let existingLogo = overlay.querySelector(".loading-logo");
    if (!existingLogo) {
        const logoImg = document.createElement("img");
        logoImg.src = "/web/static/Deckhand.png";
        logoImg.alt = "Deckhand Logo";
        logoImg.classList.add("loading-logo");
        
        // Apply responsive scaling styles
        logoImg.style.maxWidth = "80vw";
        logoImg.style.height = "auto";
        logoImg.style.marginBottom = "20px";

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

    const filtered = data.filter(c => !showOnlyUpdates || c.update_available);

    // EMPTY STATE
    if (filtered.length === 0) {
        const msg = emptyMessages.length
            ? emptyMessages[Math.floor(Math.random() * emptyMessages.length)]
            : "No containers found, Cap'n.";

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

            <div class="tag">Current: ${c.current_tag || "n/a"}</div>
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

loadStatus();
setInterval(loadStatus, 15000);


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
document.getElementById("update-all").addEventListener("click", async () => {
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


// ---------------------------------------------------------
// FILTER TOGGLE
// ---------------------------------------------------------
document.getElementById("filter-toggle").addEventListener("click", () => {
    showOnlyUpdates = !showOnlyUpdates;
    document.getElementById("filter-toggle").textContent =
        showOnlyUpdates ? "Show: Outdated" : "Show: All";

    renderStatus(currentContainerData);
});


// ---------------------------------------------------------
// LOG MODAL
// ---------------------------------------------------------
function viewLogs(id) {
    const modal = document.getElementById("log-modal");
    document.getElementById("log-title").textContent = `Logs for ${id}`;
    document.getElementById("log-body").textContent =
        (lastLogs[id] || ["No logs available"]).join("\n");

    modal.classList.remove("hidden");
}

document.getElementById("close-log").addEventListener("click", () => {
    document.getElementById("log-modal").classList.add("hidden");
});


// ---------------------------------------------------------
// HISTORY MODAL
// ---------------------------------------------------------
function viewHistory(id) {
    const modal = document.getElementById("history-modal");
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

document.getElementById("close-history").addEventListener("click", () => {
    document.getElementById("history-modal").classList.add("hidden");
});


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
Promise.all([
    initLoadingMessages(),
    initEmptyMessages()
]).then(() => {
    setTimeout(() => {
        if (!window.deckhandHasLoaded) showLoading();
    }, 1000);
});


// ---------------------------------------------------------
// MANUAL REFRESH
// ---------------------------------------------------------
document.getElementById("refresh-status").addEventListener("click", () => {
    const btn = document.getElementById("refresh-status");
    btn.disabled = true;
    btn.textContent = "Refreshing…";

    loadStatus().finally(() => {
        setTimeout(() => {
            btn.disabled = false;
            btn.textContent = "Refresh";
        }, 600);
    });
});


// ---------------------------------------------------------
// SCHEDULER SETTINGS
// ---------------------------------------------------------
document.getElementById("scheduler-settings").addEventListener("click", async () => {
    const res = await fetch("/api/scheduler/config");
    const cfg = await res.json();

    document.getElementById("sched-enabled").checked = cfg.enabled;
    document.getElementById("sched-interval").value = cfg.interval_minutes;

    document.getElementById("scheduler-modal").classList.remove("hidden");
});

document.getElementById("sched-save").addEventListener("click", async () => {
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

document.getElementById("sched-close").addEventListener("click", () => {
    document.getElementById("scheduler-modal").classList.add("hidden");
});
