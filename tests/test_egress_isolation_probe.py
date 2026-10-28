from io import StringIO
from unittest.mock import patch

from nexus.egress_isolation_probe import _no_default_route, probe


V4 = 'Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n'
Z = '0' * 32
# Real kernel rows: dest plen src splen next_hop metric refcnt use flags dev (10 fields).
V6 = Z + ' 00 ' + Z + ' 00 ' + 'fe800000000000000000000000000001' + ' 00000400 00000001 00000000 00000003 eth0\n'
V6_LOOPBACK = '00000000000000000000000000000001 80 ' + Z + ' 00 ' + Z + ' 00000000 00000002 00000000 80200001       lo\n'
V6_MULTICAST = 'ff000000000000000000000000000000 08 ' + Z + ' 00 ' + Z + ' 00000100 00000001 00000000 00000001       lo\n'
# Verbatim example row from the Linux IPv6 HOWTO, section 11.4 (::/0 reject route on lo).
V6_HOWTO_LO_REJECT = Z + ' 00 ' + Z + ' 00 ' + Z + ' ffffffff 00000001 00000001 00200200 lo\n'


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
    row = '20010db8000000000000000000000000 20 ' + Z + ' 00 ' + Z + ' 00000100 00000001 00000000 00000001 eth0\n'
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
    row = '20010db8000000000000000000000000 20 ' + Z + ' 00 ' + Z + ' 00000100 00000001 00000000 00000001 eth0 extra\n'
    with patch('builtins.open', return_value=StringIO(row)):
        assert not _no_default_route('/proc/net/ipv6_route', 6)


# Kernel-format regression: before this fix the IPv6 branch demanded 9 fields and an
# 8-hex prefix, which no real kernel emits, so the Docker isolation job could never pass.
def test_ipv6_isolated_table_in_kernel_format_allowed():
    with patch('builtins.open', return_value=StringIO(V6_LOOPBACK + V6_MULTICAST)):
        assert _no_default_route('/proc/net/ipv6_route', 6)


def test_ipv6_default_route_hidden_among_valid_rows_rejected():
    with patch('builtins.open', return_value=StringIO(V6_LOOPBACK + V6 + V6_MULTICAST)):
        assert not _no_default_route('/proc/net/ipv6_route', 6)


def test_ipv6_howto_lo_reject_default_allowed():
    with patch('builtins.open', return_value=StringIO(V6_LOOPBACK + V6_HOWTO_LO_REJECT)):
        assert _no_default_route('/proc/net/ipv6_route', 6)


# Verbatim /proc/net/ipv6_route of the isolated mcp-worker in the Docker isolation
# job on a GitHub runner (26 Oct 2026): only ::1 and the kernel's two ::/0 reject
# entries on lo; no IPv6 on eth0 at all.
CI_WORKER_V6 = (
    Z + ' 00 ' + Z + ' 00 ' + Z + ' ffffffff 00000001 00000000 00200200       lo\n'
    '00000000000000000000000000000001 80 ' + Z + ' 00 ' + Z + ' 00000000 00000004 00000000 80200001       lo\n'
    + Z + ' 00 ' + Z + ' 00 ' + Z + ' ffffffff 00000001 00000000 00200200       lo\n'
)


def test_ipv6_observed_ci_worker_table_allowed():
    with patch('builtins.open', return_value=StringIO(CI_WORKER_V6)):
        assert _no_default_route('/proc/net/ipv6_route', 6)


def _default_row(next_hop=Z, flags='00200200', dev='lo'):
    return Z + ' 00 ' + Z + ' 00 ' + next_hop + ' ffffffff 00000001 00000000 ' + flags + ' ' + dev + '\n'


def test_ipv6_reject_default_on_a_real_interface_rejected():
    with patch('builtins.open', return_value=StringIO(V6_LOOPBACK + _default_row(dev='eth0'))):
        assert not _no_default_route('/proc/net/ipv6_route', 6)


def test_ipv6_default_on_lo_without_reject_flag_rejected():
    with patch('builtins.open', return_value=StringIO(V6_LOOPBACK + _default_row(flags='00200001'))):
        assert not _no_default_route('/proc/net/ipv6_route', 6)


def test_ipv6_reject_default_on_lo_with_next_hop_rejected():
    hop = 'fe800000000000000000000000000001'
    with patch('builtins.open', return_value=StringIO(V6_LOOPBACK + _default_row(next_hop=hop))):
        assert not _no_default_route('/proc/net/ipv6_route', 6)


def test_ipv6_routable_default_next_to_reject_entries_rejected():
    with patch('builtins.open', return_value=StringIO(CI_WORKER_V6 + V6)):
        assert not _no_default_route('/proc/net/ipv6_route', 6)


def test_ipv6_legacy_nine_field_row_fails_closed():
    row = '20010db8000000000000000000000000 00000020 ' + Z + ' 00 00000000 00000000 00000000 00000001 eth0\n'
    with patch('builtins.open', return_value=StringIO(row)):
        assert not _no_default_route('/proc/net/ipv6_route', 6)


def test_ipv6_prefix_over_128_fails_closed():
    row = '20010db8000000000000000000000000 81 ' + Z + ' 00 ' + Z + ' 00000100 00000001 00000000 00000001 eth0\n'
    with patch('builtins.open', return_value=StringIO(row)):
        assert not _no_default_route('/proc/net/ipv6_route', 6)


def test_ipv6_non_hex_next_hop_fails_closed():
    row = '20010db8000000000000000000000000 20 ' + Z + ' 00 ' + 'g' * 32 + ' 00000100 00000001 00000000 00000001 eth0\n'
    with patch('builtins.open', return_value=StringIO(row)):
        assert not _no_default_route('/proc/net/ipv6_route', 6)


def test_failed_probe_prints_route_tables_to_stderr_only(capsys):
    from nexus import egress_isolation_probe as module
    tables = {'/proc/net/route': V4 + 'eth0 00000000 0100000A 0003 0 0 0 00000000 0 0 0\n',
              '/proc/net/ipv6_route': V6_LOOPBACK}
    with patch('builtins.open', side_effect=lambda path, **kw: StringIO(tables[path])), \
            patch('socket.create_connection', side_effect=OSError):
        assert module.main() == 1
    out, err = capsys.readouterr()
    assert out.strip().startswith('{') and out.count('\n') == 1
    assert '/proc/net/ipv6_route' in err and 'eth0 00000000 0100000A' in err
