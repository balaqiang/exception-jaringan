# Sistem Manajemen Jaringan Komputer — Exception Handling

Tugas P9 Pemrograman Berorientasi Objek (IF23U1411 PAGI2): melanjutkan proyek UTS
**Kasus 5 – Simulasi Jaringan Komputer (Network Topology & Traffic Manager)** dengan
menambahkan exception handling.

## Identitas

**Kelompok:** _(isi nomor kelompok sesuai LMS)_

| NIM        | Nama                     | Akun Git        |
|------------|--------------------------|-----------------|
| 2501020053 | I Putu Bala Krishna Dasa | balaqiang       |
| 2501020052 | I Putu Gede Swanjaya     | PetengSz        |
| 2501020062 | Dimas Raditya Putu Jati  | ZeleMarsh7mary  |

## Deskripsi Sistem

Sistem Manajemen Jaringan Komputer dipakai oleh Administrator Jaringan untuk mengelola
infrastruktur perangkat jaringan, memantau status koneksi, dan mensimulasikan pengiriman paket
data antarperangkat dalam topologi LAN/WAN. Administrator mendaftarkan perangkat (Router, Switch,
Server), mengatur alamat IP, alamat MAC, dan bandwidth, lalu menghubungkan perangkat ke tabel
routing atau port switch. Paket berisi alamat pengirim, alamat penerima, dan payload. Router
meneruskan paket antarjaringan berdasarkan tabel routing, Switch meneruskan paket dalam satu
segmen ke port yang sesuai, dan Server menerima paket serta mencatat log trafik.

Asumsi (dari UTS, dengan pembaruan):

1. PC pada gambaran kasus diwakili oleh Server sebagai perangkat akhir.
2. Setiap perangkat memiliki satu alamat IP dan satu alamat MAC; MAC unik dalam satu topologi.
3. Tabel routing memakai awalan IP berupa teks, misalnya `"192.168.10."`.
4. TTL awal paket 64 dan berkurang 1 di setiap router. **Diperbarui:** paket yang tidak punya
   rute, TTL-nya habis, atau dikirim ke perangkat OFF tidak lagi menghasilkan `False` diam-diam,
   melainkan memunculkan exception.
5. **Baru:** perangkat baru berstatus ON setelah didaftarkan ke topologi (`add_device`).

## 1. Aturan Bisnis yang Dapat Dilanggar

| No | Aturan bisnis | Dicek di | Exception |
|----|---------------|----------|-----------|
| 1 | Alamat IP harus IPv4 valid (4 oktet, masing-masing 0–255); MAC harus berformat `XX:XX:XX:XX:XX:XX`; prefix routing berformat `angka.` (mis. `192.168.10.`) | setter `ip_address`, `Packet.source_ip/destination_ip`, `NetworkDevice.__init__`, `Router.add_route()` | `InvalidAddressError` |
| 2 | TTL paket harus bilangan bulat 0–255 dan payload tidak boleh kosong | setter `Packet.ttl`, `Packet.payload` | `PacketError` |
| 3 | Paket yang TTL-nya habis (menjadi 0) di router harus dibuang | `Router.process_packet()` | `TTLExpiredError` |
| 4 | Perangkat yang OFF tidak boleh memproses paket | `process_packet()` pada semua perangkat | `DeviceOfflineError` |
| 5 | Nomor port switch harus 1..`total_ports`, satu port hanya untuk satu perangkat, dan satu perangkat hanya di satu port | `Switch.__init__()`, `Switch.connect_port()` | `PortError` |
| 6 | Paket harus punya rute: prefix tujuan ada di tabel routing dan IP tujuan ada di tabel port switch | `Router/Switch/Server.process_packet()` | `RoutingError` |
| 7 | Bandwidth link harus > 0, perangkat tidak boleh dihubungkan ke dirinya sendiri, MAC/IP tidak boleh ganda dalam satu topologi, dan perangkat harus terdaftar sebelum dihubungkan atau dipakai mengirim paket | `Link.__init__()`, `NetworkTopology.add_device()/connect()/send_packet()` | `TopologyError` |
