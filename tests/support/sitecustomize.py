"""Deny external sockets in fresh Python subprocesses launched by the test suite."""

import ipaddress
import socket

_original_connect = socket.socket.connect


def _connect(sock, address):
    if (
        sock.family in (socket.AF_INET, socket.AF_INET6)
        and not ipaddress.ip_address(address[0]).is_loopback
    ):
        raise AssertionError(f"External network prohibited in subprocess: {address}")
    return _original_connect(sock, address)


socket.socket.connect = _connect
