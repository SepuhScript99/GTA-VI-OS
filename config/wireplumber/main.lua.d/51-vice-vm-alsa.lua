-- GTA VI OS (Vice OS) WirePlumber 0.4.x VM & AC97 ALSA Tuning
-- 1. Eliminates snd_intel8x0 / VM IRQ pointer jitter XRUNs by increasing period
--    buffer geometry and disabling batch mode on virtualized audio devices.
-- 2. Forces software mixer on snd_intel8x0 (AC'97 STAC9700 reports +60 dB PCM
--    hardware gain, causing PipeWire ACP mixer to overdrive PCM to +57..+60 dB).
if alsa_monitor then
    if alsa_monitor.properties then
        alsa_monitor.properties["vm.node.defaults"] = {
            ["api.alsa.period-size"] = 2048,
            ["api.alsa.period-num"] = 8,
            ["api.alsa.headroom"] = 4096,
            ["api.alsa.disable-batch"] = true,
            ["session.suspend-timeout-seconds"] = 0,
        }
    end
    alsa_monitor.rules = alsa_monitor.rules or {}
    table.insert(alsa_monitor.rules, {
        matches = {
            {
                { "device.name", "matches", "alsa_card.*" },
                { "alsa.driver_name", "equals", "snd_intel8x0" },
            },
        },
        apply_properties = {
            ["api.alsa.soft-mixer"] = true,
        },
    })
end
