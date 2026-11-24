"""Hierarki custom exception untuk Sistem Manajemen Jaringan Komputer.

NetworkError (base)
├── InvalidAddressError   alamat IP / MAC / prefix routing tidak valid
├── PacketError           data paket tidak valid (TTL di luar 0-255, payload kosong)
│   └── TTLExpiredError   TTL paket habis saat melewati router
├── DeviceOfflineError    perangkat OFF diminta memproses paket
├── PortError             port switch di luar jangkauan atau sudah terpakai
├── RoutingError          tidak ada rute / tujuan tidak ditemukan
└── TopologyError         bandwidth tidak valid, perangkat ganda, link tidak sah
"""


class NetworkError(Exception):
    """Base exception: semua pelanggaran aturan bisnis jaringan."""

    def __init__(self, message, hostname=None):
        super().__init__(message)
        self.message = message
        self.hostname = hostname        # perangkat tempat error terjadi (opsional)

    def __str__(self):
        if self.hostname:
            return f"[{self.hostname}] {self.message}"
        return self.message


class InvalidAddressError(NetworkError):
    """Alamat IP, MAC, atau prefix routing tidak sesuai format."""

    def __init__(self, address, kind="IP", hostname=None):
        self.address = address
        self.kind = kind
        super().__init__(f"Alamat {kind} tidak valid: {address!r}", hostname)


class PacketError(NetworkError):
    """Data paket tidak valid (TTL di luar 0-255 atau payload kosong)."""

    def __init__(self, message, field, value, hostname=None):
        self.field = field              # atribut paket yang bermasalah
        self.value = value              # nilai yang ditolak
        super().__init__(message, hostname)


class TTLExpiredError(PacketError):
    """TTL paket habis (mencapai 0) ketika diteruskan oleh router."""

    def __init__(self, destination, hostname):
        self.destination = destination
        super().__init__(f"TTL paket ke {destination} habis, paket dibuang",
                         "ttl", 0, hostname)


class DeviceOfflineError(NetworkError):
    """Perangkat dalam keadaan OFF diminta memproses paket."""

    def __init__(self, hostname, action="memproses paket"):
        self.action = action            # aksi yang ditolak karena perangkat OFF
        super().__init__(f"perangkat OFF, tidak dapat {action}", hostname)


class PortError(NetworkError):
    """Port switch di luar jangkauan atau sudah dipakai perangkat lain."""

    def __init__(self, port, reason, hostname=None):
        self.port = port
        super().__init__(f"Port {port} {reason}", hostname)


class RoutingError(NetworkError):
    """Tidak ada rute atau perangkat tujuan tidak ditemukan."""

    def __init__(self, destination, hostname):
        self.destination = destination
        super().__init__(f"tidak ada rute ke {destination}, paket dibuang", hostname)


class TopologyError(NetworkError):
    """Pelanggaran aturan topologi: bandwidth, perangkat ganda, link tidak sah."""

    def __init__(self, message, topology=None, hostname=None):
        self.topology = topology        # nama topologi tempat aturan dilanggar
        super().__init__(message, hostname)
