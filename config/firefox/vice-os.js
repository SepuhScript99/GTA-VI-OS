// GTA VI OS (Vice OS) Firefox ESR Default Preferences
// Installed to /etc/firefox-esr/vice-os.js

// --- Smooth Video & YouTube Playback (VM + Bare Metal) ---
// Disable CPU-heavy AV1 software decoding so YouTube serves VP9/H.264 via FFmpeg
pref("media.av1.enabled", false);
pref("media.ffmpeg.enabled", true);
pref("media.ffvpx.enabled", true);
pref("media.rdd-ffmpeg.enabled", true);
pref("media.mediasource.enabled", true);
pref("media.mediasource.webm.enabled", true);
pref("media.mediasource.mp4.enabled", true);
pref("media.mediasource.vp9.enabled", true);
pref("media.webm.enabled", true);
pref("media.hardware-video-decoding.enabled", true);

// Avoid separate GPU-process/dmabuf stalls on VM software GL (llvmpipe/vmsvga)
pref("layers.gpu-process.enabled", false);
pref("widget.dmabuf.force-enabled", false);

// Ensure full volume and PulseAudio/PipeWire compatibility
pref("media.volume_scale", "1.0");
pref("toolkit.cosmeticAnimations.enabled", false);
pref("general.smoothScroll", true);

// --- Disable First-Run Clutter, Telemetry, and Studies ---
pref("browser.startup.homepage_override.mstone", "ignore");
pref("startup.homepage_welcome_url", "");
pref("startup.homepage_welcome_url.additional", "");
pref("startup.homepage_override_url", "");
pref("browser.aboutwelcome.enabled", false);
pref("browser.shell.checkDefaultBrowser", false);
pref("browser.messaging-system.whatsNewPanel.enabled", false);
pref("datareporting.healthreport.uploadEnabled", false);
pref("datareporting.policy.dataSubmissionEnabled", false);
pref("toolkit.telemetry.enabled", false);
pref("toolkit.telemetry.unified", false);
pref("toolkit.telemetry.archive.enabled", false);
pref("browser.newtabpage.activity-stream.feeds.telemetry", false);
pref("browser.newtabpage.activity-stream.telemetry", false);
pref("browser.ping-centre.telemetry", false);
pref("extensions.pocket.enabled", false);
pref("app.shield.optoutstudies.enabled", false);
pref("browser.discovery.enabled", false);
