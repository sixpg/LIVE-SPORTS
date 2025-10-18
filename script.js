const GITHUB_JSON_URL = "https://raw.githubusercontent.com/sixpg/LIVE-SPORTS/refs/heads/main/maxtv.json?token=GHSAT0AAAAAADNJZVZHMOFPGMRFJDATRVRW2HTJWJA";

async function loadChannels() {
  try {
    const res = await fetch(GITHUB_JSON_URL);
    if (!res.ok) throw new Error("Failed to load channels.json from GitHub");
    
    const channels = await res.json();
    const list = document.getElementById('channelList');
    const player = document.getElementById('videoPlayer');

    channels.forEach(channel => {
      const item = document.createElement('div');
      item.className = 'channel';
      item.innerHTML = `
        <img src="${channel.logo || ''}" alt="">
        <span>${channel.name}</span>
      `;
      item.onclick = () => playChannel(channel.url);
      list.appendChild(item);
    });

    // Auto-play first channel
    if (channels.length > 0) playChannel(channels[0].url);

    function playChannel(url) {
      if (Hls.isSupported()) {
        const hls = new Hls();
        hls.loadSource(url);
        hls.attachMedia(player);
        hls.on(Hls.Events.MANIFEST_PARSED, () => player.play());
      } else if (player.canPlayType('application/vnd.apple.mpegurl')) {
        player.src = url;
        player.play();
      } else {
        alert('Your browser does not support HLS playback.');
      }
    }

  } catch (err) {
    console.error(err);
    alert("Could not load channels. Check your GitHub URL or CORS settings.");
  }
}

loadChannels();
