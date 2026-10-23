"""Fail-closed Docker worker isolation smoke test (not a kernel security proof)."""
import json
import os
import socket
import sys


def _no_default_route(path, family):
    """Reject default routes AND malformed/incomplete kernel route tables."""
    if family not in (4, 6):
        raise ValueError('unsupported address family')
    with open(path, encoding='ascii') as stream:
        lines = stream.read().splitlines()
    if not lines:
        return False
    if family == 4:
        header = lines[0].split()
        if header[:3] != ['Iface', 'Destination', 'Gateway']:
            return False
        for line in lines[1:]:
            fields = line.split()
            if len(fields) != 11 or not fields[0]:
                return False
            if any(len(fields[i]) != 8 or any(c not in "0123456789abcdefABCDEF" for c in fields[i]) for i in (1, 2, 7)):
                return False
            try:
                destination = int(fields[1], 16)
                mask = int(fields[7], 16)
            except ValueError:
                return False
            if destination == 0 and mask == 0:
                return False
        return True
    for line in lines:
        fields = line.split()
        if len(fields) != 9 or not fields[8]:
            return False
        try:
            destination = int(fields[0], 16)
            prefix = int(fields[1], 16)
            if (len(fields[0]) != 32 or len(fields[1]) != 8 or
                any(c not in "0123456789abcdefABCDEF" for c in fields[0] + fields[1]) or
                not 0 <= prefix <= 128):
                return False
        except ValueError:
            return False
        if destination == 0 and prefix == 0:
            return False
    return True


def probe(host='mcp-relay', port=8787):
    result = {'no_default_ipv4_route': False, 'no_default_ipv6_route': False,
              'relay_reachable': False}
    for key, path, family in (
        ('no_default_ipv4_route', '/proc/net/route', 4),
        ('no_default_ipv6_route', '/proc/net/ipv6_route', 6),
    ):
        try:
            result[key] = _no_default_route(path, family)
        except (OSError, ValueError):
            result[key] = False
    try:
        with socket.create_connection((host, port), timeout=3):
            result['relay_reachable'] = True
    except (OSError, ValueError):
        pass
    result['pass'] = all(result.values())
    return result


def main():
    result = probe(os.environ.get('NEXUS_PROXY_HOST', 'mcp-relay'),
                   int(os.environ.get('NEXUS_PROXY_PORT', '8787')))
    print(json.dumps(result, sort_keys=True))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
