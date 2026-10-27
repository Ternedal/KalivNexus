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
    # Kernel format (net/ipv6/route.c, Linux IPv6 HOWTO 11.4): 10 fields per row --
    # dest(32 hex) dest_plen(2) src(32) src_plen(2) next_hop(32) metric(8)
    # refcnt(8) use(8) flags(8) device. Any other shape fails closed.
    widths = (32, 2, 32, 2, 32, 8, 8, 8, 8)
    for line in lines:
        fields = line.split()
        if len(fields) != 10 or not fields[9]:
            return False
        if any(len(fields[i]) != w or any(c not in "0123456789abcdefABCDEF" for c in fields[i])
               for i, w in enumerate(widths)):
            return False
        destination = int(fields[0], 16)
        prefix = int(fields[1], 16)
        if not 0 <= prefix <= 128 or not 0 <= int(fields[3], 16) <= 128:
            return False
        if destination == 0 and prefix == 0 and not _is_loopback_reject(fields):
            return False
    return True


RTF_REJECT = 0x0200


def _is_loopback_reject(fields):
    """The kernel's built-in unreachable ::/0 entry: on lo, REJECT, no next hop.

    It cannot forward a packet (the kernel answers ENETUNREACH), so it is not an
    egress path. Observed in the Docker worker on GitHub runners, 26 Oct 2026.
    Any other ::/0 row -- another device, a next hop, or no REJECT flag -- still fails.
    """
    return (fields[9] == 'lo' and int(fields[4], 16) == 0
            and int(fields[8], 16) & RTF_REJECT == RTF_REJECT)


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
    if not result['pass']:
        # Diagnostics only: show what the verdict was based on. Route tables hold
        # no secrets; output is bounded and never changes the verdict.
        for path in ('/proc/net/route', '/proc/net/ipv6_route'):
            try:
                with open(path, encoding='ascii', errors='replace') as stream:
                    text = stream.read(4096)
            except OSError as exc:
                text = f'<unreadable: {exc.__class__.__name__}>'
            print(f'--- {path}\n{text}', file=sys.stderr)
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
