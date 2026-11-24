"""Kelas domain Sistem Manajemen Jaringan Komputer (kode UTS)."""


class Packet:
    def __init__(self, source_ip, destination_ip, payload, ttl=64):
        self.source_ip = source_ip
        self.destination_ip = destination_ip
        self.payload = payload
        self.ttl = ttl                      # lewat setter

    @property
    def ttl(self):
        return self.__ttl

    @ttl.setter
    def ttl(self, value):
        if value < 0 or value > 255:
            raise ValueError("TTL harus 0-255")
        self.__ttl = value


class NetworkDevice:
    device_count = 0                        # class attribute

    def __init__(self, hostname, ip_address, mac_address):
        self._hostname = hostname           # protected
        self.ip_address = ip_address        # lewat setter
        self.__mac_address = mac_address.upper()   # private
        self._is_online = False
        NetworkDevice.device_count += 1

    @staticmethod
    def is_valid_ip(ip):
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        for part in parts:
            if not part.isdigit() or int(part) > 255:
                return False
        return True

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
            raise ValueError(f"IP tidak valid: {value}")
        self.__ip_address = value

    @property
    def mac_address(self):
        return self.__mac_address

    def power_on(self):
        self._is_online = True

    def report(self, message):
        print(f"  {self._hostname}: {message}")

    def process_packet(self, packet):
        is_for_me = packet.destination_ip == self.ip_address
        return self._is_online and is_for_me

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
        return self.__logs


class Router(LoggerMixin, NetworkDevice):
    def __init__(self, hostname, ip_address, mac_address):
        super().__init__(hostname, ip_address, mac_address)
        self.__routing_table = {}           # prefix -> next hop

    def add_route(self, prefix, next_hop):
        self.__routing_table[prefix] = next_hop

    def process_packet(self, packet):       # override
        if not self._is_online:
            return False
        packet.ttl -= 1
        destination = packet.destination_ip
        for prefix, next_hop in self.__routing_table.items():
            if destination.startswith(prefix):
                self.report(f"rute via {next_hop.hostname}")
                return next_hop.process_packet(packet)
        self.log(f"DROP {destination}")
        self.report("tidak ada rute, paket dibuang")
        return False


class Switch(NetworkDevice):
    def __init__(self, hostname, ip_address, mac_address, total_ports):
        super().__init__(hostname, ip_address, mac_address)
        self._total_ports = total_ports
        self.__port_table = {}              # port -> perangkat

    def connect_port(self, port, device):
        if port < 1 or port > self._total_ports:
            raise ValueError(f"Port {port} tidak tersedia")
        self.__port_table[port] = device

    def process_packet(self, packet):       # override
        if not self._is_online:
            return False
        for port, device in self.__port_table.items():
            if device.ip_address == packet.destination_ip:
                self.report(f"ke port {port} (MAC {device.mac_address})")
                return device.process_packet(packet)
        return False


class Server(LoggerMixin, NetworkDevice):
    def __init__(self, hostname, ip_address, mac_address, service):
        super().__init__(hostname, ip_address, mac_address)
        self.service = service

    def process_packet(self, packet):       # override
        if not super().process_packet(packet):
            return False
        self.log(f"{packet.source_ip}: {packet.payload}")
        self.report(f"paket diterima ({self.service})")
        return True


class Link:
    def __init__(self, device_a, device_b, bandwidth):
        self.device_a = device_a
        self.device_b = device_b
        self.bandwidth = bandwidth


class NetworkTopology:
    def __init__(self, name):
        self.name = name
        self.__devices = []                 # aggregation
        self.__links = []                   # composition

    def add_device(self, device):
        device.power_on()
        self.__devices.append(device)

    def connect(self, device_a, device_b, bandwidth):
        link = Link(device_a, device_b, bandwidth)
        self.__links.append(link)

    def send_packet(self, entry_device, packet):
        print(f"Kirim {packet.source_ip} -> {packet.destination_ip}")
        result = entry_device.process_packet(packet)
        status = "TERKIRIM" if result else "GAGAL"
        print("  Hasil:", status)
