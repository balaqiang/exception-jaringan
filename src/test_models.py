"""Unit test: memastikan setiap aturan bisnis memunculkan exception yang tepat.

Jalankan dengan: python -m unittest -v
"""
import contextlib
import io
import unittest

from exceptions import (
    DeviceOfflineError,
    InvalidAddressError,
    NetworkError,
    PacketError,
    PortError,
    RoutingError,
    TopologyError,
    TTLExpiredError,
)
from models import NetworkDevice, NetworkTopology, Packet, Router, Server, Switch


class TestExceptionHierarchy(unittest.TestCase):
    def test_semua_turunan_network_error(self):
        for cls in (InvalidAddressError, PacketError, TTLExpiredError, DeviceOfflineError,
                    PortError, RoutingError, TopologyError):
            self.assertTrue(issubclass(cls, NetworkError), cls.__name__)

    def test_ttl_expired_turunan_packet_error(self):
        self.assertTrue(issubclass(TTLExpiredError, PacketError))

    def test_str_menyertakan_hostname(self):
        self.assertEqual(str(DeviceOfflineError("R9")),
                         "[R9] perangkat OFF, tidak dapat memproses paket")

    def test_atribut_konteks(self):
        error = PortError(30, "tidak tersedia", "SW9")
        self.assertEqual((error.port, error.hostname), (30, "SW9"))
        error = PacketError("TTL salah", "ttl", 300)
        self.assertEqual((error.field, error.value), ("ttl", 300))


class TestAturanAlamat(unittest.TestCase):
    def test_ip_tidak_valid_di_setter(self):
        server = Server("S1", "10.1.1.1", "dd:dd:dd:00:00:01", "HTTP")
        with self.assertRaises(InvalidAddressError):
            server.ip_address = "10.1.1.256"
        self.assertEqual(server.ip_address, "10.1.1.1")   # IP lama tidak berubah

    def test_mac_tidak_valid(self):
        with self.assertRaises(InvalidAddressError):
            Server("S2", "10.1.1.2", "bukan-mac", "HTTP")

    def test_perangkat_gagal_tidak_dihitung(self):
        before = NetworkDevice.get_device_count()
        with self.assertRaises(InvalidAddressError):
            Server("S3", "999.1.1.1", "dd:dd:dd:00:00:03", "HTTP")
        self.assertEqual(NetworkDevice.get_device_count(), before)

    def test_prefix_routing_tidak_valid(self):
        router = Router("R2", "10.2.0.1", "dd:dd:dd:00:00:04")
        with self.assertRaises(InvalidAddressError):
            router.add_route("10.2", router)


class TestAturanPaket(unittest.TestCase):
    def test_ttl_di_luar_jangkauan(self):
        with self.assertRaises(PacketError):
            Packet("10.0.0.5", "10.0.0.6", "PING", ttl=256)

    def test_payload_kosong(self):
        with self.assertRaises(PacketError):
            Packet("10.0.0.5", "10.0.0.6", "")


class TestAturanPortDanTopologi(unittest.TestCase):
    def setUp(self):
        self.switch = Switch("SWX", "10.3.0.2", "ee:ee:ee:00:00:01", 2)
        self.server = Server("SX", "10.3.0.10", "ee:ee:ee:00:00:10", "HTTP")
        self.lan = NetworkTopology("Lab")

    def test_port_di_luar_jangkauan(self):
        with self.assertRaises(PortError):
            self.switch.connect_port(3, self.server)

    def test_port_sudah_dipakai(self):
        self.switch.connect_port(1, self.server)
        other = Server("SY", "10.3.0.11", "ee:ee:ee:00:00:11", "HTTP")
        with self.assertRaises(PortError):
            self.switch.connect_port(1, other)

    def test_bandwidth_nol(self):
        self.lan.add_device(self.switch)
        self.lan.add_device(self.server)
        with self.assertRaises(TopologyError):
            self.lan.connect(self.switch, self.server, 0)

    def test_get_device_raise_from(self):
        with self.assertRaises(TopologyError) as ctx:
            self.lan.get_device("TIDAK-ADA")
        self.assertIsInstance(ctx.exception.__cause__, StopIteration)
        self.assertEqual(ctx.exception.topology, "Lab")

    def test_perangkat_ganda(self):
        self.lan.add_device(self.server)
        with self.assertRaises(TopologyError):
            self.lan.add_device(self.server)


class TestPengirimanPaket(unittest.TestCase):
    def setUp(self):
        self.router = Router("RT", "10.0.0.1", "f0:f0:f0:00:00:01")
        self.switch = Switch("ST", "10.4.0.2", "f0:f0:f0:00:00:02", 4)
        self.server = Server("WT", "10.4.0.10", "f0:f0:f0:00:00:10", "HTTP")
        self.offline = Server("OT", "10.4.0.30", "f0:f0:f0:00:00:30", "FTP")
        self.lan = NetworkTopology("Uji")
        for device in (self.router, self.switch, self.server):
            self.lan.add_device(device)
        self.switch.connect_port(1, self.server)
        self.switch.connect_port(2, self.offline)
        self.router.add_route("10.4.0.", self.switch)

    def send(self, destination, ttl=64):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.lan.send_packet(self.router, Packet("10.0.0.5", destination, "X", ttl))

    def test_paket_terkirim(self):
        self.assertTrue(self.send("10.4.0.10"))

    def test_tidak_ada_rute(self):
        with self.assertRaises(RoutingError):
            self.send("172.16.0.1")

    def test_perangkat_off(self):
        with self.assertRaises(DeviceOfflineError):
            self.send("10.4.0.30")

    def test_ttl_habis(self):
        with self.assertRaises(TTLExpiredError):
            self.send("10.4.0.10", ttl=1)


if __name__ == "__main__":
    unittest.main()
