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
