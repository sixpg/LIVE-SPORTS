const M3U_URL = "https://cosmicsports.pages.dev/playlist/livetv.m3u";

let channels = [];
let filtered = [];
let currentCategory = "live";
let hls;
const favorites = new Set(JSON.parse(localStorage.getItem("favorites") || "[]"));

const list = document.getElementById("channelList");
const player = document.getElementById("player");
const search = document.getElementById("search");
const nowPlaying = document.getElementById("nowPlaying");

/* ---------- M3U PARSER ---------- */
function parseM3U(text) {
  const lines = text.split("\n");
  const items = [];
  let info = {};

  for (let line of lines) {
    line = line.trim();
    if (line.startsWith("#EXTINF")) {
      info = {
        name: line.match(/,(.*)$/)?.[1] || "Unknown",
        logo: line.match(/tvg-logo="(.*?)"/)?.[1] || "",
        group: line.match(/group-title="(.*?)"/)?.[1]?.toLowerCase() || "live"
      };
    } else if (line && !line.startsWith("#")) {
      info.url = line;
      items.push({ ...info });
      info = {};
    }
  }
  return items;
}

/* ---------- FETCH CHANNELS ---------- */
async function loadChannels() {
  const res = await fetch(M3U_URL, { cache: "no-store" });
  const text = await res.text();
  channels = parseM3U(text);
  applyFilter();
}

function applyFilter() {
  filtered = channels.filter(c => {
    if (currentCategory === "favorites") return favorites.has(c.url);
    return c.group.includes(currentCategory);
  });
  renderList();
}

/* ---------- RENDER ---------- */
function renderList() {
  list.innerHTML = "";
  const fragment = document.createDocumentFragment();

  filtered.forEach(c => {
    const div = document.createElement("div");
    div.className = "channel";

    div.innerHTML = `
      <img src="${c.logo || "https://via.placeholder.com/80"}">
      <span>${c.name}</span>
      <div class="star ${favorites.has(c.url) ? "active" : ""}">★</div>
    `;

    div.onclick = e => {
      if (e.target.classList.contains("star")) {
        toggleFav(c.url, e.target);
        e.stopPropagation();
        return;
      }
      play(c);
    };

    fragment.appendChild(div);
  });

  list.appendChild(fragment);
}

/* ---------- PLAYER ---------- */
function play(channel) {
  nowPlaying.textContent = channel.name;

  if (hls) hls.destroy();

  if (Hls.isSupported()) {
    hls = new Hls();
    hls.loadSource(channel.url);
    hls.attachMedia(player);
  } else {
    player.src = channel.url;
  }
}

/* ---------- FAVORITES ---------- */
function toggleFav(url, el) {
  favorites.has(url) ? favorites.delete(url) : favorites.add(url);
  el.classList.toggle("active");
  localStorage.setItem("favorites", JSON.stringify([...favorites]));
}

/* ---------- SEARCH (FAST) ---------- */
let searchTimer;
search.oninput = () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    const q = search.value.toLowerCase();
    filtered = channels.filter(c => c.name.toLowerCase().includes(q));
    renderList();
  }, 150);
};

/* ---------- TABS ---------- */
document.querySelectorAll(".tab").forEach(btn => {
  btn.onclick = () => {
    document.querySelector(".tab.active").classList.remove("active");
    btn.classList.add("active");
    currentCategory = btn.dataset.category;
    applyFilter();
  };
});

/* ---------- AUTO REFRESH ---------- */
setInterval(loadChannels, 60000);

/* ---------- INIT ---------- */
loadChannels();
