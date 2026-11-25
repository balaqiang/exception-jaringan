"""Kelas domain Simulasi Jaringan Komputer (dengan exception handling)."""
import re

from exceptions import (
    DeviceOfflineError,
    InvalidAddressError,
    PacketError,
    PortError,
    RoutingError,
    TopologyError,
    TTLExpiredError,
)


class Packet:
    MAX_TTL = 255

    def __init__(self, source_ip, destination_ip, payload, ttl=64):
        self.source_ip = source_ip              # lewat setter
        self.destination_ip = destination_ip    # lewat setter
        self.payload = payload                  # lewat setter
        self.ttl = ttl                          # lewat setter

    @property
    def source_ip(self):
        return self.__source_ip

    @source_ip.setter
    def source_ip(self, value):
        if not NetworkDevice.is_valid_ip(value):
            raise InvalidAddressError(value, "IP sumber")
        self.__source_ip = value

    @property
    def destination_ip(self):
        return self.__destination_ip

    @destination_ip.setter
    def destination_ip(self, value):
        if not NetworkDevice.is_valid_ip(value):
            raise InvalidAddressError(value, "IP tujuan")
        self.__destination_ip = value

    @property
    def payload(self):
        return self.__payload

    @payload.setter
    def payload(self, value):
        if not isinstance(value, str) or not value.strip():
            raise PacketError("Payload paket tidak boleh kosong", "payload", value)
        self.__payload = value

    @property
    def ttl(self):
        return self.__ttl

    @ttl.setter
    def ttl(self, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise PacketError(f"TTL harus bilangan bulat, diterima: {value!r}", "ttl", value)
        if value < 0 or value > Packet.MAX_TTL:
            raise PacketError(f"TTL harus 0-{Packet.MAX_TTL}, diterima: {value}", "ttl", value)
        self.__ttl = value


class NetworkDevice:
    device_count = 0                        # class attribute
    MAC_PATTERN = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")

    def __init__(self, hostname, ip_address, mac_address):
        if not isinstance(hostname, str) or not hostname.strip():
            raise TopologyError("Hostname perangkat tidak boleh kosong")
        mac = str(mac_address).upper()
        if not NetworkDevice.is_valid_mac(mac):
            raise InvalidAddressError(mac_address, "MAC", hostname)
        self._hostname = hostname           # protected
        self.ip_address = ip_address        # lewat setter (bisa raise)
        self.__mac_address = mac            # private
        self._is_online = False
        # dihitung hanya jika semua validasi di atas lolos
        NetworkDevice.device_count += 1

    @staticmethod
    def is_valid_ip(ip):
        if not isinstance(ip, str):
            return False
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        for part in parts:
            if not part.isdigit() or int(part) > 255:
                return False
        return True

    @staticmethod
    def is_valid_mac(mac):
        return bool(NetworkDevice.MAC_PATTERN.match(mac))

    @classmethod
    def get_device_count(cls):
        return cls.device_count

    @property
    def hostname(self):
        return self._hostname

    @property
    def ip_address(self):
        return self.__ip_address

    @ip_address.setter
    def ip_address(self, value):
        if not NetworkDevice.is_valid_ip(value):
            raise InvalidAddressError(value, "IP", self._hostname)
        self.__ip_address = value

    @property
    def mac_address(self):
        return self.__mac_address

    @property
    def is_online(self):
        return self._is_online

    def power_on(self):
        self._is_online = True

    def power_off(self):
        self._is_online = False

    def report(self, message):
        print(f"  {self._hostname}: {message}")

    def process_packet(self, packet):
        if not self._is_online:
            raise DeviceOfflineError(self._hostname)
        return packet.destination_ip == self.ip_address

    def __eq__(self, other):
        if not isinstance(other, NetworkDevice):
            return False
        return self.mac_address == other.mac_address

    def __str__(self):
        status = "ON" if self._is_online else "OFF"
        return f"{type(self).__name__} {self._hostname} ({self.ip_address}) [{status}]"


class LoggerMixin:
    def __init__(self, *args, **kwargs):
        self.__logs = []
        super().__init__(*args, **kwargs)   # lanjut ke class berikutnya di MRO

    def log(self, message):
        self.__logs.append(message)

    def get_logs(self):
        return list(self.__logs)


class Router(LoggerMixin, NetworkDevice):
    PREFIX_PATTERN = re.compile(r"^(\d{1,3}\.){1,3}$")

    def __init__(self, hostname, ip_address, mac_address):
        super().__init__(hostname, ip_address, mac_address)
        self.__routing_table = {}           # prefix -> next hop

    def add_route(self, prefix, next_hop):
        if not isinstance(prefix, str) or not Router.PREFIX_PATTERN.match(prefix):
            raise InvalidAddressError(prefix, "prefix routing", self._hostname)
        if not isinstance(next_hop, NetworkDevice):
            raise TopologyError("Next hop harus berupa perangkat jaringan", hostname=self._hostname)
        if next_hop is self:
            raise TopologyError("Next hop tidak boleh router itu sendiri", hostname=self._hostname)
        self.__routing_table[prefix] = next_hop

    def process_packet(self, packet):       # override
        if not self._is_online:
            raise DeviceOfflineError(self._hostname)
        destination = packet.destination_ip
        if packet.ttl <= 1:                 # setelah dikurangi akan menjadi 0
            packet.ttl = 0
            self.log(f"TTL EXPIRED {destination}")
            raise TTLExpiredError(destination, self._hostname)
        packet.ttl -= 1
        for prefix, next_hop in self.__routing_table.items():
            if destination.startswith(prefix):
                self.report(f"rute via {next_hop.hostname}")
                return next_hop.process_packet(packet)
        self.log(f"DROP {destination}")
        raise RoutingError(destination, self._hostname)


class Switch(NetworkDevice):
    def __init__(self, hostname, ip_address, mac_address, total_ports):
        if isinstance(total_ports, bool) or not isinstance(total_ports, int) or total_ports < 1:
            raise PortError(total_ports, "bukan jumlah port yang valid", hostname)
        super().__init__(hostname, ip_address, mac_address)
        self._total_ports = total_ports
        self.__port_table = {}              # port -> perangkat

    def connect_port(self, port, device):
        if isinstance(port, bool) or not isinstance(port, int):
            raise PortError(port, "harus berupa bilangan bulat", self._hostname)
        if port < 1 or port > self._total_ports:
            raise PortError(port, f"tidak tersedia (1-{self._total_ports})", self._hostname)
        if port in self.__port_table:
            used_by = self.__port_table[port].hostname
            raise PortError(port, f"sudah dipakai {used_by}", self._hostname)
        if device in self.__port_table.values():
            raise PortError(port, f"tidak bisa dipakai, {device.hostname} sudah tercolok", self._hostname)
        self.__port_table[port] = device

    def process_packet(self, packet):       # override
        if not self._is_online:
            raise DeviceOfflineError(self._hostname)
        for port, device in self.__port_table.items():
            if device.ip_address == packet.destination_ip:
                self.report(f"ke port {port} (MAC {device.mac_address})")
                return device.process_packet(packet)
        raise RoutingError(packet.destination_ip, self._hostname)


class Server(LoggerMixin, NetworkDevice):
    def __init__(self, hostname, ip_address, mac_address, service):
        super().__init__(hostname, ip_address, mac_address)
        self.service = service

    def process_packet(self, packet):       # override
        if not super().process_packet(packet):   # raise jika OFF
            raise RoutingError(packet.destination_ip, self._hostname)
        self.log(f"{packet.source_ip}: {packet.payload}")
        self.report(f"paket diterima ({self.service})")
        return True


class Link:
    def __init__(self, device_a, device_b, bandwidth):
        if device_a is device_b:
            raise TopologyError(f"{device_a.hostname} tidak boleh dihubungkan ke dirinya sendiri")
        if isinstance(bandwidth, bool) or not isinstance(bandwidth, (int, float)) or bandwidth <= 0:
            raise TopologyError(f"Bandwidth harus lebih dari 0 Mbps, diterima: {bandwidth!r}")
        self.device_a = device_a
        self.device_b = device_b
        self.bandwidth = bandwidth


class NetworkTopology:
    def __init__(self, name):
        self.name = name
        self.__devices = []                 # aggregation
        self.__links = []                   # composition

    def add_device(self, device):
        if not isinstance(device, NetworkDevice):
            raise TopologyError("Hanya perangkat jaringan yang bisa ditambahkan", self.name)
        for existing in self.__devices:
            if existing == device:
                raise TopologyError(f"MAC {device.mac_address} sudah terdaftar", self.name, existing.hostname)
            if existing.ip_address == device.ip_address:
                raise TopologyError(f"IP {device.ip_address} sudah dipakai", self.name, existing.hostname)
        device.power_on()
        self.__devices.append(device)

    def connect(self, device_a, device_b, bandwidth):
        for device in (device_a, device_b):
            if device not in self.__devices:
                raise TopologyError(f"{device.hostname} belum terdaftar di {self.name}", self.name)
        link = Link(device_a, device_b, bandwidth)   # bisa raise TopologyError
        self.__links.append(link)

    def get_device(self, hostname):
        # EAFP: langsung ambil, tangani jika ternyata tidak ada
        try:
            return next(d for d in self.__devices if d.hostname == hostname)
        except StopIteration as error:
            raise TopologyError(f"perangkat {hostname} tidak ditemukan di {self.name}",
                                self.name) from error

    def send_packet(self, entry_device, packet):
        if entry_device not in self.__devices:
            raise TopologyError(f"{entry_device.hostname} belum terdaftar di {self.name}", self.name)
        print(f"Kirim {packet.source_ip} -> {packet.destination_ip}")
        return entry_device.process_packet(packet)
