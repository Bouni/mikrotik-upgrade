# Mikrotik upgrade

A minimal tool for mass updating Mikrotik routers

## Installation

```
pip install mikrotik-upgrade
```

## Config

Place a config.yaml either in `/etc/mikrotik-upgrade/config.yaml` or in `~/.config/mikrotik-upgrade/config.yaml`

An example can be found in the repo.

## Runing the upgrades

simply call `mikrotik-upgrade`

The output lokks like this

```sh
mikrotik-upgrade  
================================================================================
==                                   Router                                   ==
================================================================================
New version is available
Download updates
Upgrade routerboard
Reboot System
```
