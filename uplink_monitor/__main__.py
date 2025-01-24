#!/usr/bin/env python3

import asyncio
import logging
import os
import yaml

import uplink_monitor

def run():
    logging.basicConfig(
        format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
        level=os.getenv("UPLINK_MONITOR_LOGLEVEL", "INFO"),
        datefmt='%Y-%m-%d %H:%M:%S')

    cfg = os.getenv("UPLINK_MONITOR_CFG", "/etc/uplink-monitor.yaml")
    with open(cfg, mode="rb") as file:
        config = yaml.safe_load(file)
    monitor = uplink_monitor.UplinkMonitor(config)
    asyncio.run(monitor.loop())

if __name__ == "__main__":
    run()
