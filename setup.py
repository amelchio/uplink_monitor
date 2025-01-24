#!/usr/bin/env python3

from setuptools import setup

setup(
    name="uplink_monitor",
    packages=["uplink_monitor"],
    install_requires=["aioping", "pyyaml", "eternalegypt"],
    entry_points={"console_scripts": ["uplink-monitor = uplink_monitor.__main__:run"]},
)
