"""
Parser for raw dmodex blobs returned by PMIx_server_dmodex_request.

Wire format: PMIx v61 bfrops (non-fully-described), integers encoded as
zigzag + base-128 varints.  Each KVAL in the blob:

  varint_signed(num_vals=1)
  varint_signed(key_len)          # strlen+1, includes null terminator
  key_len bytes                   # key string, null-terminated
  varint_unsigned(value_type)     # PMIX_BYTE_OBJECT = 27
  varint_unsigned(blob_size)      # PMIX_SIZE = uint64_t on 64-bit
  blob_size bytes                 # value payload

The btl.tcp.* payload is an array of mca_btl_tcp_modex_addr_t (32 B each):
  uint8_t  addr[16]              # IPv4: first 4 bytes; rest zero
  uint32_t addr_ifkindex         # kernel interface index (LE)
  uint32_t addr_mask             # CIDR prefix length (LE)
  uint32_t addr_bandwidth        # Mbps (LE)
  uint16_t addr_port             # listen port (network byte order)
  uint8_t  addr_family           # 0 = IPv4, 1 = IPv6
  uint8_t  padding[1]
"""

import struct
import socket

PMIX_BYTE_OBJECT = 27
TCP_MODEX_ADDR_SIZE = 32  # confirmed by _Static_assert in btl_tcp_addr.h


# ---------------------------------------------------------------------------
# Varint decoding
# ---------------------------------------------------------------------------

def _read_varint_unsigned(buf: bytes, pos: int):
    """Base-128 unsigned varint. Returns (value, new_pos)."""
    val = 0
    shift = 0
    while True:
        b = buf[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        shift += 7
        if not (b & 0x80):
            break
    return val, pos


def _read_varint_signed(buf: bytes, pos: int):
    """Base-128 zigzag-encoded signed varint. Returns (value, new_pos)."""
    n, pos = _read_varint_unsigned(buf, pos)
    # zigzag decode: even → positive, odd → negative
    if n & 1:
        value = -((n + 1) >> 1)
    else:
        value = n >> 1
    return value, pos


# ---------------------------------------------------------------------------
# KVAL blob parser
# ---------------------------------------------------------------------------

def parse_dmodex_blob(raw, debug=False) -> dict:
    """
    Parse a raw dmodex blob (bytes or bytearray) into a dict mapping
    key string -> raw bytes payload.
    """
    if hasattr(raw, 'tobytes'):
        buf = raw.tobytes()
    else:
        buf = bytes(raw)

    if debug:
        print(f"[dmodex] buf len={len(buf)} bytes[0:4]={list(buf[:4])}")

    pos = 0
    results = {}

    while pos < len(buf):
        if pos + 2 > len(buf):
            if debug:
                print(f"[dmodex] break: only {len(buf)-pos} bytes left at pos={pos}")
            break

        # num_vals (int32_t, zigzag varint — always 1)
        num_vals, pos = _read_varint_signed(buf, pos)
        if debug:
            print(f"[dmodex] pos={pos} num_vals={num_vals}")
        if num_vals != 1:
            if debug:
                print(f"[dmodex] break: unexpected num_vals={num_vals}")
            break

        # key string: signed int32 length (includes null), then bytes
        key_len, pos = _read_varint_signed(buf, pos)
        if debug:
            print(f"[dmodex] pos={pos} key_len={key_len}")
        if key_len <= 0 or pos + key_len > len(buf):
            if debug:
                print(f"[dmodex] break: bad key_len={key_len}")
            break
        key = buf[pos:pos + key_len - 1].decode('utf-8', errors='replace')
        pos += key_len
        if debug:
            print(f"[dmodex] pos={pos} key={key!r}")

        # value type (uint16_t, unsigned varint)
        val_type, pos = _read_varint_unsigned(buf, pos)
        if debug:
            print(f"[dmodex] pos={pos} val_type={val_type} (BYTE_OBJECT={PMIX_BYTE_OBJECT})")

        if val_type == PMIX_BYTE_OBJECT:
            # blob size (size_t / uint64_t, unsigned varint)
            blob_size, pos = _read_varint_unsigned(buf, pos)
            if debug:
                print(f"[dmodex] pos={pos} blob_size={blob_size}")
            if pos + blob_size > len(buf):
                if debug:
                    print(f"[dmodex] break: blob {blob_size}B overruns buf len={len(buf)}")
                break
            results[key] = buf[pos:pos + blob_size]
            pos += blob_size
        else:
            if debug:
                print(f"[dmodex] break: unhandled val_type={val_type}")
            break

    if debug:
        print(f"[dmodex] parsed keys: {list(results.keys())}")
    return results


# ---------------------------------------------------------------------------
# BTL TCP modex address parser
# ---------------------------------------------------------------------------

def parse_btl_tcp(blob: bytes) -> list:
    """
    Parse a BTL TCP modex payload into a list of dicts:
      {'ip': str, 'port': int, 'family': str, 'mask': int, 'bandwidth_mbps': int}

    Each mca_btl_tcp_modex_addr_t is 32 bytes:
      addr[16]         IPv4: first 4 bytes only; rest zero
      addr_ifkindex    uint32 LE  (kernel interface index)
      addr_mask        uint32 LE  (CIDR prefix length, e.g. 24 for /24)
      addr_bandwidth   uint32 LE  (Mbps)
      addr_port        uint16 network byte order  (big-endian)
      addr_family      uint8  (0 = IPv4, 1 = IPv6)
      padding          uint8
    """
    addrs = []
    for offset in range(0, len(blob) - (TCP_MODEX_ADDR_SIZE - 1), TCP_MODEX_ADDR_SIZE):
        entry = blob[offset:offset + TCP_MODEX_ADDR_SIZE]
        if len(entry) < TCP_MODEX_ADDR_SIZE:
            break

        family_code = entry[30]

        if family_code == 0:  # MCA_BTL_TCP_AF_INET
            ip = socket.inet_ntoa(entry[0:4])
            family = 'IPv4'
        elif family_code == 1:  # MCA_BTL_TCP_AF_INET6
            ip = socket.inet_ntop(socket.AF_INET6, entry[0:16])
            family = 'IPv6'
        else:
            ip = f'unknown(family={family_code})'
            family = 'unknown'

        ifkindex, mask, bandwidth = struct.unpack_from('<III', entry, 16)
        port = struct.unpack_from('>H', entry, 28)[0]  # network byte order

        addrs.append({
            'ip':            ip,
            'port':          port,
            'family':        family,
            'ifkindex':      ifkindex,
            'mask':          mask,
            'bandwidth_mbps': bandwidth,
        })

    return addrs


# ---------------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------------

def get_btl_endpoints(dmodex_data) -> dict:
    """
    Extract BTL TCP endpoints from a raw dmodex blob.

    Args:
        dmodex_data: bytes / bytearray / array.array from dmodex_request()

    Returns:
        dict mapping btl key name -> list of endpoint dicts
        e.g. {'btl.tcp.5.0': [{'ip': '10.0.0.3', 'port': 1024, ...}]}
    """
    kvs = parse_dmodex_blob(dmodex_data)
    endpoints = {}
    for key, blob in kvs.items():
        if key and key.startswith('btl.tcp'):
            endpoints[key] = parse_btl_tcp(blob)
    return endpoints

def print_dmodex(dmodex_data, debug=False) -> None:
    """Parse and pretty-print a dmodex blob."""
    kvs = parse_dmodex_blob(dmodex_data, debug=debug)
    for key, blob in kvs.items():
        print(f'key={key!r}  payload={len(blob)}B')
        if key and key.startswith('btl.tcp'):
            for addr in parse_btl_tcp(blob):
                print(f"  → {addr['ip']}:{addr['port']} ({addr['family']}) "
                      f"/{addr['mask']}  {addr['bandwidth_mbps']} Mbps  "
                      f"ifindex={addr['ifkindex']}")
        else:
            print(f'  (raw bytes, {len(blob)}B)')
