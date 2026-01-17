/* =======================
   IPTV ACCOUNT DETAILS
======================= */
const SERVER   = "https://dhoomtv.xyz:443";
const USERNAME = "P4B9TB9xR8";
const PASSWORD = "humongous2tonight";

/* =======================
   GET CHANNEL ID
======================= */
const params = new URLSearchParams(window.location.search);
const channelId = params.get("id");

if (!channelId) {
  alert("No channel ID provided.\nUse ?id=581305");
  throw new Error("Missing channel ID");
}

/* =======================
   BUILD STREAM URL
======================= */
const streamUrl = `${SERVER}/live/${USERNAME}/${PASSWORD}/${channelId}.m3u8`;

const video = document.getElementById("video");

/* =======================
   INIT PLYR
======================= */
const player = new Plyr(video, {
  autoplay: true,
  controls: [
    "play", "progress", "current-time",
    "mute", "volume", "fullscreen"
  ]
});

/* =======================
   INIT HLS
======================= */
if (Hls.isSupported()) {
  const hls = new Hls({
    enableWorker: true,
    lowLatencyMode: true
  });

  hls.loadSource(streamUrl);
  hls.attachMedia(video);

  hls.on(Hls.Events.ERROR, (event, data) => {
    console.error("HLS ERROR:", data);
  });

} else if (video.canPlayType("application/vnd.apple.mpegurl")) {
  video.src = streamUrl;
}
