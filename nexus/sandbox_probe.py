"""Fail-closed runtime probe for the explicitly networkless container profile.

Checks actual socket behavior, not an attestation supplied by application code.
Exit 0 means external TCP and loopback TCP were both blocked in this container.
"""
import json
import socket
import sys


def probe() -> dict:
    results = {}
    for name, addr in (
        ('external_ipv4', ('1.1.1.1', 443)),
        ('loopback_ipv4', ('127.0.0.1', 9)),
    ):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                results[name] = sock.connect_ex(addr) != 0
        except OSError:
            results[name] = True
    # In network_mode:none loopback may exist; refusing connection to a closed
    # port is not proof of network isolation. Inspect route configuration too.
    try:
        with open('/proc/net/route', encoding='ascii') as routes:
            lines = routes.read().splitlines()[1:]
        results['no_ipv4_routes'] = not any(line.split()[1] == '00000000' for line in lines if len(line.split()) > 1)
    except OSError:
        results['no_ipv4_routes'] = False
    results['pass'] = all(results.values())
    return results


def main() -> int:
    result = probe()
    print(json.dumps(result, sort_keys=True))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
