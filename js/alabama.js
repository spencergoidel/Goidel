function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatCountdown(primaryDay) {
  const target = new Date(`${primaryDay}T00:00:00-05:00`);
  const now = new Date();
  const diffMs = target.getTime() - now.getTime();
  const el = document.getElementById("countdown");

  if (Number.isNaN(target.getTime())) {
    el.textContent = "Primary date unavailable";
    return;
  }
  if (diffMs <= 0) {
    el.textContent = "Primary day is here or has passed";
    return;
  }

  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diffMs / (1000 * 60 * 60)) % 24);
  el.textContent = `${days} days, ${hours} hours`;
}

function renderRace(container, race) {
  const card = document.createElement("article");
  card.className = "race-card";

  const title = document.createElement("h3");
  title.textContent = `${race.name} - Race Snapshot`;
  card.appendChild(title);

  const ul = document.createElement("ul");
  (race.snapshot || []).forEach((b) => {
    const li = document.createElement("li");
    li.textContent = b;
    ul.appendChild(li);
  });
  card.appendChild(ul);

  if (!race.polls || race.polls.length === 0) {
    const p = document.createElement("p");
    p.className = "small-note";
    p.textContent = "No polling rows currently available.";
    card.appendChild(p);
    container.appendChild(card);
    return;
  }

  const table = document.createElement("table");
  table.className = "topline-table";

  const headers = (race.columns || []).map((h) => `<th>${escapeHtml(h)}</th>`).join("");
  table.innerHTML = `
    <thead>
      <tr>
        <th>Pollster</th>
        <th>Date</th>
        <th>Sample</th>
        ${headers}
        <th>Spread</th>
      </tr>
    </thead>
    <tbody>
      ${(race.polls || []).map((r) => {
        const pollster = r.pollster_url
          ? `<a href="${escapeHtml(r.pollster_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(r.pollster)}</a>`
          : escapeHtml(r.pollster);
        const vals = (r.values || []).map((v) => `<td>${escapeHtml(v)}</td>`).join("");
        return `
          <tr>
            <td>${pollster}</td>
            <td>${escapeHtml(r.date)}</td>
            <td>${escapeHtml(r.sample)}</td>
            ${vals}
            <td>${escapeHtml(r.spread)}</td>
          </tr>
        `;
      }).join("")}
    </tbody>
  `;

  card.appendChild(table);
  container.appendChild(card);
}

async function init() {
  const data = await fetch("data/alabama_tracker.json").then((r) => r.json());
  document.getElementById("updated-at").textContent = `Last updated: ${data.updated_at}`;
  formatCountdown(data.primary_day);

  const container = document.getElementById("al-races");
  container.innerHTML = "";
  (data.races || []).forEach((race) => renderRace(container, race));
}

init().catch((e) => {
  console.error(e);
  document.getElementById("updated-at").textContent = "Unable to load Alabama tracker data.";
  document.getElementById("countdown").textContent = "Unavailable";
});
