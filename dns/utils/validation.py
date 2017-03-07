import ipaddress


def is_ipv6(ip_addr):
    try:
        ipaddress.IPv6Address(ip_addr)
        return True
    except ipaddress.AddressValueError:
        return False
