# wg-conf-gen

This Python script takes a YAML file enumerating Wireguard peers (with their settings) and creates a `wg-quick` configuration file for each peer so that it can directly connect to all other peers using Wireguard.

It's kind of like Tailscale but static, less secure, and dumber.

## Configuration File
Take a look at `example.yml`. Basically, you must have a top-level `peers:` list containing named peers. Each named peer needs the following fields:
- `endpoint_host` - IP address or FQDN of this host on the non-Wireguard network (probably the internet) that other nodes should use to reach it
- `endpoint_port` - The UDP port that this host will listen on for Wireguard traffic
- `private_key` - The Wireguard Private key (base64-ed Curve25519) that this node will use
- `wg_ips` - A list of IP addresses that this peer will use inside of the Wireguard network. Each IP address requires a subnet mask (i.e. `2001:db8:1234:4321::101/64` or `10.1.0.1/24`)

## Output Files
This script will create a directory called `output_configs` in the current directory and create a configuration file for each peer with the peer's name, like `example.conf`. This file can then be uploaded to the Wireguard peer and set up with `wg-quick`.

For my use case (Debian servers with the `wireguard` package installed), I did the following to get the configuration file working on the peer(s):
```bash
$ # On my host machine
$ /wg-conf-gen.py example.yml 
Writing config for node1 to output_configs/node1.conf
Writing config for node2 to output_configs/node2.conf
Writing config for node3 to output_configs/node3.conf
Writing config for node😎 to output_configs/node😎.conf
$ scp output_config/node1.conf node1.example.com:
node1.conf                                      100%  861    27.8KB/s   00:00 

$ # On node1.example.com
$ sudo mv ~/node1.conf /etc/wireguard/wg0.conf
$ sudo systemctl enable --now wg-quick@wg0
$ sudo wg
interface: wg0
  public key: 8/Ezkexvrzwy6ULixqlogngScYhQn4BpKsx0oUX/c0c=
  private key: (hidden)
  listening port: 45678

peer: 4HbhtecVt8Am1fZVvicmmy4IVoGzB76FJW3unUSA7Qo=
# output truncated here for clarity

$ # All finished!
```
