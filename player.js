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
  alert("No channel ID provided.\nExample: ?id=581305");
  throw new Error("Missing channel ID");
}

/* =======================
   BUILD STREAM URL
======================= */
const streamUrl = `${SERVER}/live/${USERNAME}/${PASSWORD}/${channelId}.ts`;

const video = document.getElementById("video");

/* =======================
   INIT PLYR
======================= */
new Plyr(video, {
  autoplay: true,
  controls: [
    "play",
    "progress",
    "current-time",
    "mute",
    "volume",
    "fullscreen"
  ]
});

/* =======================
   INIT MPEGTS
======================= */
if (mpegts.getFeatureList().mseLivePlayback) {
  const player = mpegts.createPlayer({
    type: "mpegts",
    url: streamUrl,
    isLive: true
  });

  player.attachMediaElement(video);
  player.load();
  player.play();

  player.on(mpegts.Events.ERROR, (e) => {
    console.error("MPEGTS ERROR:", e);
  });

} else {
  alert("MSE Live Playback is not supported in this browser.");
}
