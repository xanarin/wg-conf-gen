#!/usr/bin/env -S python3
import argparse
import ipaddress
from pathlib import Path
from subprocess import check_output, CalledProcessError, run, STDOUT
import sys
import os

import yaml

class ConfigParseError(Exception):
    pass

class WgPeer():
    def __init__(self, name, data_dict):
        self.name = name
        self.endpoint_host = data_dict['endpoint_host']
        self.endpoint_port = int(data_dict['endpoint_port'])
        self.private_key = data_dict['private_key']
        self.routes = []
        if data_dict.get("routes"):
            for route in data_dict['routes']:
                try:
                    self.routes.append(ipaddress.ip_network(route))
                except ValueError as verr:
                    raise KeyError(f"IP Route {route} is invalid: {verr}") from verr

        ips =  data_dict['wg_ips']
        if not ips:
            raise KeyError("No IPs specified in wg_ips dictionary")

        # wg_ips are a tuple of (ipaddress.ip_address address, int subnet_mask)
        self.wg_ips = []
        for ip in ips:
            elements = ip.split("/")
            if len(elements) != 2:
                raise KeyError(f"Address {ip} is missing the subnet mask (e.g. /24)")
            address = ipaddress.ip_address(elements[0])
            subnet_mask = int(elements[1])
            self.wg_ips.append((address, subnet_mask))

    @property
    def public_key(self):
        if not self._has_wg():
            raise RuntimeError("'wg' utility not found and needed to calculate public keys")
        completed_proc = run(["wg", "pubkey"], input=self.private_key.encode("ascii"),
                capture_output=True, check=True)
        return completed_proc.stdout.strip().decode()

    def generate_peer_block(self):
        """Generate a Wireguard configuration file [Peer] block"""
        peer_block =   "[Peer]\n"
        peer_block += f"# {self.name} #\n"
        peer_block += f"PublicKey = {self.public_key}\n"
        peer_block += f"Endpoint = {self.endpoint_host}:{self.endpoint_port}\n"

        # Generate AllowedIPs list
        peer_block += "AllowedIPs = "
        for (ip, _) in self.wg_ips:
            peer_block += f"{ip}/{ip.max_prefixlen},"
        for route in self.routes:
            peer_block += f"{route},"
        # Remove last comma and terminate AllowedIPs line
        peer_block = peer_block[:-1] + "\n"

        peer_block += "PersistentKeepalive = 60\n\n"
        return peer_block

    def generate_self_block(self):
        """"Generate a Wireguard configuration file [Interface] block"""
        self_block =  "[Interface]\n"
        self_block += "Address = "
        for (ip, subnet_mask) in self.wg_ips:
            self_block += f"{ip}/{subnet_mask},"
        # Remove last comma and terminate AllowedIPs line
        self_block = self_block[:-1] + "\n"
        self_block += f"PrivateKey = {self.private_key}\n"
        self_block += f"# Public Key is {self.public_key}\n"
        self_block += f"ListenPort = {self.endpoint_port}\n\n"
        return self_block

    @staticmethod
    def _has_wg():
        try:
            check_output(["wg", "--version"], stderr=STDOUT)
            return True
        except CalledProcessError:
            return False

def parse_config(config_data):
    """Takes a configuration file and returns a list of WgPeer objects"""
    definitions = yaml.load(config_data, yaml.loader.FullLoader)

    if not definitions.get("peers"):
        raise ConfigParseError("Definition file missing 'peers' top-level directive")

    peer_defs = definitions['peers']
    if len(peer_defs) < 1:
        raise ConfigParseError("No peers defined in configuration file!")

    peers = []
    for peer_name, peer_def in peer_defs.items():
        try:
            peers.append(WgPeer(peer_name, peer_def))
        except KeyError as kerr:
            raise ConfigParseError(f"Failed to parse peer '{peer_name}': {kerr}") from kerr
    return peers

def parse_args():
    parser = argparse.ArgumentParser("wg-conf-gen", "Generate Wireguard configuration files for a network of nodes")
    parser.add_argument("CONFIG_FILE", help="File containing the YAML description of all nodes")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose output and debugging information")
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        logic(args)

    # pylint: disable=broad-except
    except Exception as err:
        # If we are not in verbose mode, print a nice user error instead of stack traces
        if not args.verbose:
            print(f"ERROR: {err}")
            return 2
        raise err

    return 0

def logic(args):
    with open(args.CONFIG_FILE, "rb") as config_file:
        peers = parse_config(config_file.read())

    # Create output directory
    out_dir = Path(".") / "output_configs"
    os.makedirs(out_dir, exist_ok=True)

    # Generate configuration file for each peer
    for peer in peers:
        out_file_path = out_dir / f"{peer.name}.conf"
        with open(out_file_path, "w", encoding="utf-8") as out_file:
            print(f"Writing config for {peer.name} to {out_file_path}")
            out_file.write(peer.generate_self_block())
            for other_peer in filter(lambda p, cp=peer: p != cp, peers):
                out_file.write(other_peer.generate_peer_block())

if __name__ == "__main__":
    sys.exit(main())
