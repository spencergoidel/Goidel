const FIPS_TO_STATE = {
  1: "AL", 2: "AK", 4: "AZ", 5: "AR", 6: "CA", 8: "CO", 9: "CT", 10: "DE", 11: "DC",
  12: "FL", 13: "GA", 15: "HI", 16: "ID", 17: "IL", 18: "IN", 19: "IA", 20: "KS", 21: "KY",
  22: "LA", 23: "ME", 24: "MD", 25: "MA", 26: "MI", 27: "MN", 28: "MS", 29: "MO", 30: "MT",
  31: "NE", 32: "NV", 33: "NH", 34: "NJ", 35: "NM", 36: "NY", 37: "NC", 38: "ND", 39: "OH",
  40: "OK", 41: "OR", 42: "PA", 44: "RI", 45: "SC", 46: "SD", 47: "TN", 48: "TX", 49: "UT",
  50: "VT", 51: "VA", 53: "WA", 54: "WV", 55: "WI", 56: "WY"
};

const STATE_NAMES = {
  AK: "Alaska", GA: "Georgia", ME: "Maine", MI: "Michigan", NC: "North Carolina", NH: "New Hampshire", OH: "Ohio"
};

function showTooltip(tooltip, event, stateCode, race) {
  const date = race ? race.primary_date : "No date available";
  const label = race ? race.cook_rating : "Not a swing race";
  tooltip.innerHTML = `<strong>${STATE_NAMES[stateCode] || stateCode}</strong><br />${label}<br />Primary: ${date}`;
  tooltip.style.left = `${event.clientX + 12}px`;
  tooltip.style.top = `${event.clientY + 12}px`;
  tooltip.style.display = "block";
}

function hideTooltip(tooltip) {
  tooltip.style.display = "none";
}

async function initMap() {
  const tooltip = document.getElementById("tooltip");
  const mapEl = document.getElementById("map");

  const [us, raceData] = await Promise.all([
    d3.json("https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json"),
    fetch("data/races.json").then((r) => r.json())
  ]);

  document.getElementById("updated-at").textContent = `Last refreshed: ${raceData.updated_at}`;

  const raceMap = new Map(raceData.swing_states.map((d) => [d.state, d]));
  const states = topojson.feature(us, us.objects.states).features;

  const width = mapEl.clientWidth;
  const height = 560;

  const svg = d3.select("#map").append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .style("display", "block");

  const projection = d3.geoAlbersUsa().fitSize([width, height], { type: "FeatureCollection", features: states });
  const path = d3.geoPath(projection);

  svg.append("g")
    .selectAll("path")
    .data(states)
    .join("path")
    .attr("d", path)
    .attr("fill", (d) => {
      const code = FIPS_TO_STATE[Number(d.id)];
      return raceMap.has(code) ? "#b45309" : "#d1d5db";
    })
    .attr("stroke", "#fff")
    .attr("stroke-width", 1.1)
    .style("cursor", (d) => {
      const code = FIPS_TO_STATE[Number(d.id)];
      return raceMap.has(code) ? "pointer" : "default";
    })
    .on("mousemove", (event, d) => {
      const code = FIPS_TO_STATE[Number(d.id)];
      showTooltip(tooltip, event, code, raceMap.get(code));
    })
    .on("mouseleave", () => hideTooltip(tooltip))
    .on("click", (_, d) => {
      const code = FIPS_TO_STATE[Number(d.id)];
      if (raceMap.has(code)) {
        window.location.href = `state.html?state=${code}`;
      }
    });

  const legend = svg.append("g").attr("transform", `translate(${width - 210}, ${height - 70})`);
  legend.append("rect").attr("width", 190).attr("height", 50).attr("fill", "#ffffff").attr("stroke", "#cbd5e1").attr("rx", 8);
  legend.append("rect").attr("x", 12).attr("y", 12).attr("width", 16).attr("height", 16).attr("fill", "#b45309");
  legend.append("text").attr("x", 36).attr("y", 25).attr("font-size", 12).attr("fill", "#1f2937").text("Cook swing state");
  legend.append("rect").attr("x", 12).attr("y", 31).attr("width", 16).attr("height", 16).attr("fill", "#d1d5db");
  legend.append("text").attr("x", 36).attr("y", 44).attr("font-size", 12).attr("fill", "#1f2937").text("Other states");
}

initMap().catch((err) => {
  console.error(err);
  const updated = document.getElementById("updated-at");
  updated.textContent = "Unable to load race map data.";
});
