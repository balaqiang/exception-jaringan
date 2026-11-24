"""Program utama simulasi jaringan dengan exception handling.

Setiap skenario dibungkus try / except / else / finally:
- try     : menjalankan aksi yang mungkin melanggar aturan bisnis
- except  : menangkap custom exception, subclass ditulis lebih dulu dari base
- else    : hanya berjalan jika tidak ada exception
- finally : selalu berjalan (mencatat statistik / menutup simulasi)

Juga dicontohkan: raise ... from (parse_port, NetworkTopology.get_device),
re-raise (send_critical), dan gaya EAFP (parse_port, get_device).
"""
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

CLIENT_IP = "10.0.0.5"
LAN_PREFIX = "192.168.10."


def build_topology():
    """Membangun topologi LAN Kantor seperti pada UTS."""
    r1 = Router("R1", "10.0.0.1", "aa:aa:aa:00:00:01")
    sw1 = Switch("SW1", LAN_PREFIX + "2", "bb:bb:bb:00:00:01", 24)
    web = Server("WEB-01", LAN_PREFIX + "10", "cc:cc:cc:00:00:10", "HTTP")
    db = Server("DB-01", LAN_PREFIX + "20", "cc:cc:cc:00:00:20", "MySQL")
    # BACKUP-01 dicolokkan ke switch tetapi tidak didaftarkan ke topologi,
    # sehingga tidak pernah di-power_on() -> dipakai untuk skenario OFF.
    backup = Server("BACKUP-01", LAN_PREFIX + "30", "cc:cc:cc:00:00:30", "FTP")

    lan = NetworkTopology("LAN Kantor")
    for device in (r1, sw1, web, db):
        lan.add_device(device)
    lan.connect(r1, sw1, 1000)
    lan.connect(sw1, web, 100)
    lan.connect(sw1, db, 100)
    sw1.connect_port(1, web)
    sw1.connect_port(2, db)
    sw1.connect_port(3, backup)
    r1.add_route(LAN_PREFIX, sw1)
    return lan, r1, sw1, web, db, backup


def parse_port(text):
    """EAFP: langsung konversi ke int, ubah ValueError menjadi PortError."""
    try:
        return int(text)
    except ValueError as error:
        raise PortError(text, "harus berupa angka") from error


def connect_from_config(switch, port_text, device):
    """Mencolokkan perangkat berdasarkan konfigurasi teks, mis. dari file."""
    switch.connect_port(parse_port(port_text), device)


def send_critical(lan, entry_device, packet):
    """Paket kritis: kegagalan dicatat ke audit lalu dilempar ulang (re-raise)."""
    try:
        return lan.send_packet(entry_device, packet)
    except NetworkError as error:
        print(f"  [AUDIT] paket kritis gagal ({type(error).__name__}), diteruskan ke pemanggil")
        raise


def show_cause(error):
    if error.__cause__ is not None:
        print("    penyebab asli:", repr(error.__cause__))


def simulate_packets(lan, entry_device, packets):
    """Mengirim beberapa paket dan menangani kegagalan per paket."""
    delivered = 0
    for packet in packets:
        try:
            lan.send_packet(entry_device, packet)
        except TTLExpiredError as error:        # subclass PacketError -> ditulis dulu
            print("  GAGAL [TTL]     :", error)
        except RoutingError as error:
            print("  GAGAL [ROUTING] :", error)
        except DeviceOfflineError as error:
            print("  GAGAL [OFFLINE] :", error)
        except NetworkError as error:           # base, menangkap sisanya
            print("  GAGAL [JARINGAN]:", error)
        else:
            delivered += 1
            print("  Hasil: TERKIRIM")
        finally:
            print(f"  (TTL tersisa: {packet.ttl})")
    print(f"Ringkasan: {delivered} dari {len(packets)} paket terkirim\n")


def run_rule_checks(lan, sw1, web, db):
    """Mencoba aksi yang melanggar (dan satu yang memenuhi) aturan bisnis."""
    scenarios = [
        ("Ubah IP DB-01 menjadi 192.168.10.300",
         lambda: setattr(db, "ip_address", LAN_PREFIX + "300")),
        ("Buat Server dengan MAC 'zz:zz:zz'",
         lambda: Server("WEB-03", LAN_PREFIX + "12", "zz:zz:zz", "HTTP")),
        ("Buat paket dengan TTL 300",
         lambda: Packet(CLIENT_IP, web.ip_address, "PING", ttl=300)),
        ("Buat paket dengan payload kosong",
         lambda: Packet(CLIENT_IP, web.ip_address, "   ")),
        ("Colokkan DB-01 ke port 30 pada SW1 (24 port)",
         lambda: sw1.connect_port(30, db)),
        ("Colokkan perangkat baru ke port 1 yang sudah dipakai",
         lambda: sw1.connect_port(1, Server("WEB-04", LAN_PREFIX + "14",
                                            "cc:cc:cc:00:00:14", "HTTP"))),
        ("Colokkan DB-01 dari konfigurasi teks port 'dua'",
         lambda: connect_from_config(sw1, "dua", db)),
        ("Cari perangkat 'FW-01' di topologi",
         lambda: lan.get_device("FW-01")),
        ("Hubungkan SW1 dan WEB-01 dengan bandwidth 0",
         lambda: lan.connect(sw1, web, 0)),
        ("Daftarkan WEB-01 dua kali ke topologi",
         lambda: lan.add_device(web)),
        ("Ubah IP DB-01 menjadi 192.168.10.21 (valid)",
         lambda: setattr(db, "ip_address", LAN_PREFIX + "21")),
    ]

    accepted = rejected = 0
    for title, action in scenarios:
        print("Uji:", title)
        try:
            action()
        except InvalidAddressError as error:
            rejected += 1
            print("  Ditolak (alamat)  :", error)
            show_cause(error)
        except PacketError as error:
            rejected += 1
            print("  Ditolak (paket)   :", error)
            show_cause(error)
        except PortError as error:
            rejected += 1
            print("  Ditolak (port)    :", error)
            show_cause(error)
        except TopologyError as error:
            rejected += 1
            print("  Ditolak (topologi):", error)
            show_cause(error)
        except NetworkError as error:
            rejected += 1
            print("  Ditolak (lainnya) :", error)
            show_cause(error)
        else:
            accepted += 1
            print("  Diterima: tidak ada aturan bisnis yang dilanggar")
        finally:
            print(f"  -> jumlah perangkat tercatat: {NetworkDevice.get_device_count()}")
    print(f"Ringkasan: {rejected} ditolak, {accepted} diterima\n")


def main():
    print("=== Simulasi Jaringan: LAN Kantor ===")
    try:
        lan, r1, sw1, web, db, backup = build_topology()
    except NetworkError as error:
        print("Topologi gagal dibangun:", error)
        return
    else:
        print(web)
        print(backup)
        print("Jumlah perangkat:", NetworkDevice.get_device_count(), "\n")

    try:
        print("--- Bagian 1: Pengiriman paket ---")
        packets = [
            Packet(CLIENT_IP, web.ip_address, "GET /index.html"),   # berhasil
            Packet(CLIENT_IP, "172.16.0.9", "PING"),                 # tidak ada rute di R1
            Packet(CLIENT_IP, LAN_PREFIX + "99", "PING"),            # tidak ada di port SW1
            Packet(CLIENT_IP, backup.ip_address, "STOR data.zip"),  # BACKUP-01 OFF
            Packet(CLIENT_IP, db.ip_address, "SELECT 1", ttl=1),     # TTL habis di R1
        ]
        simulate_packets(lan, r1, packets)

        print("--- Bagian 2: Uji aturan bisnis ---")
        run_rule_checks(lan, sw1, web, db)

        print("--- Bagian 3: Paket kritis (re-raise) ---")
        try:
            send_critical(lan, r1, Packet(CLIENT_IP, "10.9.9.9", "BACKUP NOW"))
        except RoutingError as error:
            print("  main menerima exception yang dilempar ulang:", error)
        else:
            print("  paket kritis terkirim")
        finally:
            print("  pemeriksaan paket kritis selesai\n")

        print("--- Bagian 4: Log perangkat ---")
        for device in (web, r1):
            print(f"Log {device.hostname}:", device.get_logs())
    except NetworkError as error:
        print("Kesalahan jaringan tak terduga:", error)
    else:
        print("\nSemua skenario selesai dijalankan tanpa crash.")
    finally:
        print("=== Simulasi selesai ===")


if __name__ == "__main__":
    main()
