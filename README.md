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

## 2. Daftar Custom Exception

Semua exception ada di [`src/exceptions.py`](src/exceptions.py). Setiap kelas punya `__init__`
dengan atribut konteks dan memanggil `super().__init__(pesan)` (rantai sampai ke `Exception`).
`NetworkError` adalah base exception, sehingga seluruh pelanggaran aturan bisnis dapat ditangkap
dengan satu `except NetworkError`.

```
Exception
└── NetworkError                (message, hostname)
    ├── InvalidAddressError     (address, kind)
    ├── PacketError             (field, value)
    │   └── TTLExpiredError     (destination)
    ├── DeviceOfflineError      (action)
    ├── PortError               (port)
    ├── RoutingError            (destination)
    └── TopologyError           (topology)
```

| Nama | Class induk | Atribut konteks | Kapan dimunculkan | Method yang memunculkan | Cara program menangani |
|------|-------------|-----------------|-------------------|-------------------------|------------------------|
| `NetworkError` | `Exception` | `message`, `hostname` | Base, tidak di-raise langsung | — | `except NetworkError` terakhir sebagai penangkap umum di `simulate_packets`, `run_rule_checks`, dan `main` |
| `InvalidAddressError` | `NetworkError` | `address`, `kind` | IP / MAC / prefix routing tidak valid | setter `ip_address`, `Packet.source_ip/destination_ip`, `NetworkDevice.__init__`, `Router.add_route` | Ditampilkan "Ditolak (alamat)"; nilai lama tetap dipakai |
| `PacketError` | `NetworkError` | `field`, `value` | TTL di luar 0–255 / bukan integer, payload kosong | setter `Packet.ttl`, `Packet.payload` | Ditampilkan "Ditolak (paket)"; paket tidak dibuat |
| `TTLExpiredError` | `PacketError` | `destination` | TTL habis saat diteruskan router | `Router.process_packet` | Ditangkap paling awal di `simulate_packets` sebagai "GAGAL [TTL]" |
| `DeviceOfflineError` | `NetworkError` | `action` | Perangkat OFF diminta memproses paket | `process_packet` (semua perangkat) | "GAGAL [OFFLINE]"; simulasi lanjut ke paket berikutnya |
| `PortError` | `NetworkError` | `port` | Port di luar 1..total, sudah dipakai, perangkat sudah tercolok, port bukan angka | `Switch.__init__`, `Switch.connect_port`, `parse_port` (`raise ... from ValueError`) | "Ditolak (port)" beserta penyebab aslinya |
| `RoutingError` | `NetworkError` | `destination` | Tidak ada prefix yang cocok / IP tidak ada di tabel port | `Router/Switch/Server.process_packet` | "GAGAL [ROUTING]"; pada paket kritis dicatat audit lalu di-re-raise ke `main` |
| `TopologyError` | `NetworkError` | `topology` | Bandwidth ≤ 0, link ke diri sendiri, MAC/IP ganda, perangkat belum terdaftar / tidak ditemukan | `Link.__init__`, `NetworkTopology.add_device/connect/send_packet/get_device`, `Router.add_route` | "Ditolak (topologi)"; `get_device` menyertakan penyebab `StopIteration` |

## 3. Class Diagram (Revisi)

![Class Diagram](docs/class-diagram.png)

Sumber diagram: [`docs/class-diagram.mmd`](docs/class-diagram.mmd) (Mermaid).

Perubahan dari class diagram UTS:

- Ditambahkan delapan class bertanda stereotype «exception» dengan relasi generalization ke
  `NetworkError`, dan `NetworkError` ke `Exception`; `TTLExpiredError` merupakan turunan `PacketError`.
- Catatan (note) kuning pada tiap class domain menunjukkan method/setter mana yang memunculkan
  exception apa; garis putus-putus «raise» adalah dependency ke exception.
- Atribut dan method baru: setter `source_ip`, `destination_ip`, `payload` pada `Packet`;
  `is_valid_mac()`, `MAC_PATTERN`, `power_off()` pada `NetworkDevice`; `PREFIX_PATTERN` pada
  `Router`; `get_device()` pada `NetworkTopology`. `send_packet()` kini mengembalikan `bool`.
- `LoggerMixin` diberi stereotype «mixin».

Notasi: `+` public, `#` protected, `-` private, garis bawah = class/static member, segitiga
kosong = generalization, belah ketupat hitam = composition, belah ketupat putih = aggregation,
panah = association, putus-putus = dependency.
