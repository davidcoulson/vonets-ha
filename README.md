# VONETS WiFi Bridge for Home Assistant

Monitors VONETS WiFi bridges (tested on the VBG1200) through the status endpoints the bridge
serves (the uplink check is open; signal and status need the web login). Set up from the UI with just the bridge's IP address.

Setup asks for the bridge IP and its web admin login (the signal and status data need it; the uplink check does not).

Entities per bridge: uplink connectivity, signal (dBm and %), temperature, uptime, channel,
connected AP (BSSID) and SSID. Polls every 60 seconds.

## Adding bridges
Settings → Devices & services → Add integration → VONETS WiFi Bridge: enter an IP, or scan a network
range (up to 1024 addresses). Bridges that request a DHCP lease on a network HA can see (MAC prefix
`00:17:13`) also show up under Discovered. If the web password changes, HA asks for the new one
(reauth); address and login can be edited with Reconfigure.

## Install
HACS → Custom repositories → add this repo as *Integration* → download → restart HA →
Settings → Devices & services → Add integration → "VONETS WiFi Bridge".

Give each bridge a DHCP reservation: the entry is keyed on the IP address.
