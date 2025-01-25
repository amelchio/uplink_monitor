# uplink_monitor

My personal implementation of uplink monitoring with failover handling.

The failover works by adding a route to the secondary uplink with route metric 1. Thus, existing default routes must be set to a higher metric.

This script uses the commands `ip` and `conntrack` which must exist in `PATH`.

A text message can be sent on failover/failback, though only from Netgear LTE modems supported by [Eternal Egypt](http://github.com/amelchio/eternalegypt).

## Configuration

See `etc/uplink-monitor.yaml`.
