-- GTA VI OS (Vice OS) WirePlumber 0.4.x VM & AC97 ALSA Tuning
-- Eliminates snd_intel8x0 / VM IRQ pointer jitter XRUNs by increasing period
-- buffer geometry and disabling batch mode on virtualized audio devices.
if alsa_monitor and alsa_monitor.properties then
    alsa_monitor.properties["vm.node.defaults"] = {
        ["api.alsa.period-size"] = 2048,
        ["api.alsa.period-num"] = 8,
        ["api.alsa.headroom"] = 4096,
        ["api.alsa.disable-batch"] = true,
        ["session.suspend-timeout-seconds"] = 0,
    }
end
