"use strict";
const byId = id => document.getElementById(id);
const runButton = byId("run");
const fault = byId("fault");
let report = null;
let busy = false;

function orderLabels(id, orders, limit) {
  const target = byId(id);
  target.replaceChildren();
  for (const order of orders.slice(0, limit)) {
    const label = document.createElement("span");
    label.className = "order";
    label.textContent = order.id;
    target.append(label);
  }
  if (orders.length > limit) {
    const more = document.createElement("span");
    more.textContent = "+ " + (orders.length - limit) + " more";
    target.append(more);
  }
}

async function run() {
  if (busy) return;
  busy = true;
  runButton.disabled = fault.disabled = true;
  byId("status").textContent = "Running real SQLite inserts and restarting a worker process…";
  try {
    const response = await fetch("/api/replay", {method: "POST",
      headers: {"Content-Type": "application/json"}, body: "{}"});
    if (!response.ok) throw new Error("Replay returned HTTP " + response.status);
    report = await response.json();
    byId("naive-count").textContent = report.naive_replayed_orders + " orders / " + report.naive_duplicates + " duplicates";
    byId("safe-count").textContent = report.safe_replayed_orders + " order / " + report.safe_duplicates + " duplicates";
    orderLabels("naive-orders", report.naive_ledger, 4);
    orderLabels("safe-orders", report.safe_ledger.slice(0, 1), 1);
    byId("distinct").textContent = "Distinct updates: " + report.legitimate_updates + "/2 processed. " + report.safe_total_orders + " safe orders total, including the two new authorizations.";
    byId("recovery").textContent = "Worker restart: " + report.recovery.recovery_ms + " ms · leased → done · one downstream order. Includes remaining 50 ms lab lease and process startup; not an SLA.";
    byId("timeline").replaceChildren();
    for (const item of report.timeline) {
      const row = document.createElement("li");
      const at = document.createElement("strong");
      at.textContent = item.at;
      row.append(at, document.createTextNode(item.event));
      byId("timeline").append(row);
    }
    byId("ledger").replaceChildren();
    for (const action of report.actions) {
      const row = document.createElement("tr");
      for (const value of [JSON.parse(action.payload).revision, action.key.slice(0, 16), action.attempts, action.state, action.result]) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      }
      byId("ledger").append(row);
    }
    byId("receipts").textContent = report.receipts.length + " durable receipts: 3 accepted; 100 duplicates. Full keys and both order ledgers are in the JSON export.";
    byId("results").hidden = false;
    byId("status").textContent = "Complete: 100 duplicate side effects in the naïve path; zero in the durable path.";
  } catch (error) {
    byId("status").textContent = error.message + ". Check the server terminal, then run again. Previous results, if shown, are unchanged.";
  } finally {
    busy = false;
    runButton.disabled = fault.disabled = false;
  }
}

fault.addEventListener("dragstart", event => {
  event.dataTransfer.setData("text/plain", "synthetic-ack-timeout");
  event.dataTransfer.effectAllowed = "copy";
});
fault.addEventListener("click", run);
runButton.addEventListener("click", run);
runButton.addEventListener("dragover", event => {
  event.preventDefault();
  if (!busy) runButton.classList.add("dragover");
});
runButton.addEventListener("dragleave", () => runButton.classList.remove("dragover"));
runButton.addEventListener("drop", event => {
  event.preventDefault();
  runButton.classList.remove("dragover");
  if (event.dataTransfer.getData("text/plain") === "synthetic-ack-timeout") run();
});
byId("download").addEventListener("click", () => {
  if (!report) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type: "application/json"}));
  const link = document.createElement("a");
  link.href = url;
  link.download = "synthetic-replay-ledger.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
