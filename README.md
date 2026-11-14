# VONETS WiFi Bridge for Home Assistant

Monitors VONETS WiFi bridges (tested on the VBG1200) through the status endpoints the bridge
serves without a login. Set up from the UI with just the bridge's IP address.

Entities per bridge: uplink connectivity, signal (dBm and %), temperature, uptime, channel,
connected AP (BSSID) and SSID. Polls every 60 seconds.

## Install
HACS → Custom repositories → add this repo as *Integration* → download → restart HA →
Settings → Devices & services → Add integration → "VONETS WiFi Bridge".

Give each bridge a DHCP reservation: the entry is keyed on the IP address.
