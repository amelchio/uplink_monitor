# uplink_monitor

My personal implementation of uplink monitoring with failover handling.

The failover works by switching the route metric of the secondary uplink between 1 and 1000. Thus, existing default routes must be strictly inside this range.

This script uses the commands `ifmetric` and `conntrack` which must exist in `PATH`.

A text message can be sent on failover/failback, via Netgear LTE modems supported by [Eternal Egypt](http://github.com/amelchio/eternalegypt)
or Huawei modems supported by [huawei-lte-api](https://github.com/Salamek/huawei-lte-api).

## Configuration

See `etc/uplink-monitor.yaml`.
