from io import StringIO
from unittest.mock import patch

from nexus.egress_isolation_probe import _no_default_route, probe


V4 = 'Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n'
V6 = '0' * 32 + ' 00000000 ' + '0' * 32 + ' 00 00000000 00000000 00000000 00000001 lo\n'


def test_ipv4_default_route_rejected():
    with patch('builtins.open', return_value=StringIO(V4 + 'eth0 00000000 0100000A 0003 0 0 0 00000000 0 0 0\n')):
        assert not _no_default_route('/proc/net/route', 4)


def test_ipv4_no_default_route_allowed():
    with patch('builtins.open', return_value=StringIO(V4 + 'eth0 0000000A 00000000 0001 0 0 0 00FFFFFF 0 0 0\n')):
        assert _no_default_route('/proc/net/route', 4)


def test_ipv6_default_route_rejected():
    with patch('builtins.open', return_value=StringIO(V6)):
        assert not _no_default_route('/proc/net/ipv6_route', 6)


def test_empty_procfs_fails_closed():
    with patch('builtins.open', side_effect=lambda *args, **kwargs: StringIO('')):
        assert not _no_default_route('/proc/net/route', 4)
        assert not _no_default_route('/proc/net/ipv6_route', 6)


def test_unreadable_ipv4_does_not_hide_ipv6_result():
    def fake_open(path, **kwargs):
        if path.endswith('/route'):
            raise PermissionError('denied')
        return StringIO(V6)
    with patch('builtins.open', side_effect=fake_open), patch('socket.create_connection', side_effect=OSError):
        result = probe()
    assert result == {'no_default_ipv4_route': False, 'no_default_ipv6_route': False,
                      'relay_reachable': False, 'pass': False}


def test_ipv4_malformed_row_fails_closed():
    with patch('builtins.open', return_value=StringIO(V4 + 'eth0 GARBAGE\n')):
        assert not _no_default_route('/proc/net/route', 4)


def test_ipv4_zero_destination_and_zero_mask_fails_even_if_route_flags_unusual():
    with patch('builtins.open', return_value=StringIO(V4 + 'eth0 00000000 00000000 0000 0 0 0 00000000 0 0 0\n')):
        assert not _no_default_route('/proc/net/route', 4)


def test_ipv6_malformed_row_fails_closed():
    with patch('builtins.open', return_value=StringIO('broken route row\n')):
        assert not _no_default_route('/proc/net/ipv6_route', 6)


def test_ipv6_nondefault_route_allowed():
    row = '20010db8000000000000000000000000 00000020 ' + '0' * 32 + ' 00 00000000 00000000 00000000 00000001 eth0\n'
    with patch('builtins.open', return_value=StringIO(row)):
        assert _no_default_route('/proc/net/ipv6_route', 6)


def test_ipv4_short_hex_destination_fails_closed():
    row = 'eth0 000000A 00000000 0001 0 0 0 00FFFFFF 0 0 0\n'
    with patch('builtins.open', return_value=StringIO(V4 + row)):
        assert not _no_default_route('/proc/net/route', 4)

def test_ipv4_extra_columns_fail_closed():
    row = 'eth0 0000000A 00000000 0001 0 0 0 00FFFFFF 0 0 0 extra\n'
    with patch('builtins.open', return_value=StringIO(V4 + row)):
        assert not _no_default_route('/proc/net/route', 4)

def test_ipv6_extra_columns_fail_closed():
    row = '20010db8000000000000000000000000 00000020 ' + '0' * 32 + ' 00 00000000 00000000 00000000 00000001 eth0 extra\n'
    with patch('builtins.open', return_value=StringIO(row)):
        assert not _no_default_route('/proc/net/ipv6_route', 6)
