function renderList(el, items, formatter) {
  el.innerHTML = "";
  if (!items || items.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No current data available.";
    el.appendChild(li);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    li.innerHTML = formatter(item);
    el.appendChild(li);
  }
}

async function initStatePage() {
  const params = new URLSearchParams(window.location.search);
  const state = (params.get("state") || "").toUpperCase();

  const data = await fetch("data/races.json").then((r) => r.json());
  const race = data.swing_states.find((d) => d.state === state);

  const title = document.getElementById("race-title");
  const meta = document.getElementById("race-meta");

  if (!race) {
    title.textContent = "State not found in current Cook swing list";
    meta.textContent = "Try one of the highlighted states on the map.";
    return;
  }

  title.textContent = `${race.state_name} Senate Race`;
  meta.textContent = `${race.cook_rating} • Last updated ${data.updated_at}`;
  document.getElementById("primary-date").textContent = race.primary_date || "Not available";

  renderList(document.getElementById("poly-list"), race.odds?.polymarket || [], (m) => {
    const price = m.yes_price !== null && m.yes_price !== undefined ? `${(m.yes_price * 100).toFixed(1)}%` : "N/A";
    return `<a href="${m.url}" target="_blank" rel="noopener noreferrer">${m.title}</a> (${price})`;
  });

  renderList(document.getElementById("kalshi-list"), race.odds?.kalshi || [], (m) => {
    const price = m.yes_price !== null && m.yes_price !== undefined ? `${(m.yes_price * 100).toFixed(1)}%` : "N/A";
    return `<a href="${m.url}" target="_blank" rel="noopener noreferrer">${m.title}</a> (${price})`;
  });

  renderList(document.getElementById("poll-list"), race.polls || [], (p) => {
    const pollVal = p.value ? `: ${p.value}` : "";
    return `<strong>${p.source}</strong>${pollVal}${p.url ? ` (<a href="${p.url}" target="_blank" rel="noopener noreferrer">source</a>)` : ""}`;
  });

  renderList(document.getElementById("story-list"), race.storylines || [], (s) => {
    const date = s.date ? `<span class="story-date">${s.date}</span> — ` : "";
    const src = s.source ? ` <em>${s.source}</em>` : "";
    const link = s.url ? ` (<a href="${s.url}" target="_blank" rel="noopener noreferrer">link</a>)` : "";
    return `${date}${s.point}${src}${link}`;
  });
}

initStatePage().catch((err) => {
  console.error(err);
  document.getElementById("race-title").textContent = "Could not load state data";
});
