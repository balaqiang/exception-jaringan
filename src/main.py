"""Program utama simulasi jaringan (kode UTS)."""
from models import NetworkDevice, NetworkTopology, Packet, Router, Server, Switch


if __name__ == "__main__":
    client_ip = "10.0.0.5"
    lan_prefix = "192.168.10."

    r1 = Router("R1", "10.0.0.1", "aa:aa:aa:00:00:01")
    sw1 = Switch("SW1", lan_prefix + "2", "bb:bb:bb:00:00:01", 24)
    web = Server("WEB-01", lan_prefix + "10", "cc:cc:cc:00:00:10", "HTTP")
    db = Server("DB-01", lan_prefix + "20", "cc:cc:cc:00:00:20", "MySQL")

    lan = NetworkTopology("LAN Kantor")
    for device in (r1, sw1, web, db):
        lan.add_device(device)
    lan.connect(r1, sw1, 1000)
    lan.connect(sw1, web, 100)
    lan.connect(sw1, db, 100)
    sw1.connect_port(1, web)
    sw1.connect_port(2, db)
    r1.add_route(lan_prefix, sw1)
    print(web)
    print("Jumlah perangkat:", NetworkDevice.get_device_count())

    packet_ok = Packet(client_ip, web.ip_address, "GET /index.html")
    packet_lost = Packet(client_ip, "172.16.0.9", "PING")
    for packet in (packet_ok, packet_lost):
        lan.send_packet(r1, packet)
    for device in (web, r1):
        print(f"Log {device.hostname}:", device.get_logs())

    try:
        db.ip_address = lan_prefix + "300"
    except ValueError as error:
        print("Error:", error)

    web2 = Server("WEB-02", lan_prefix + "11", web.mac_address, "HTTP")
    print("web == db  :", web == db)
    print("web == web2:", web == web2)
