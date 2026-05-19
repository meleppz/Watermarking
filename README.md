# DIGITAL WATERMARKING DCT + ECC (HAMMING 7,4) INTERACTIVE CLI

Dokumentasi ini menjelaskan implementasi sistem penyisipan pesan rahasia (*digital watermarking*) berbasis ranah frekuensi menggunakan kombinasi metode **Discrete Cosine Transform (DCT)**, penyebaran spektrum (**Spread-Spectrum**), dan proteksi kesalahan kode **Error Correction Code (ECC) Hamming(7,4)**.

Aplikasi ini dilengkapi dengan antarmuka berbasis Command Line Interface (CLI) interaktif untuk melakukan simulasi pengujian ketahanan citra terhadap serangan kompresi JPEG.

---

## 📌 1. Overview Program

Program `main_cli.py` dirancang untuk menguji ketahanan sebuah *watermark* digital (dalam hal ini, sebuah *pixel art* biner berbentuk **Huruf "M"** berukuran 8x8 piksel) yang disisipkan ke dalam sebuah citra/gambar induk.

Secara interaktif, pengguna dapat mengontrol parameter kekuatan penyisipan, tingkat replikasi data, hingga sebaran frekuensinya. Alur utama program ini meliputi:
1. **Penerimaan Input:** Pengguna memasukkan berkas gambar kustom (atau otomatis digantikan oleh gambar sintetis).
2. **Proteksi Saluran (ECC Encoding):** *Watermark* biner diubah menjadi barisan bit linear dan diproteksi menggunakan algoritma Hamming(7,4).
3. **Penyisipan (Embedding):** Data biner disisipkan ke dalam koefisien frekuensi menengah (mid-band) DCT dari komponen luminans (Y) citra.
4. **Serangan Kompresi (Simulation):** Citra ber-*watermark* dihantam dengan simulasi kompresi JPEG pada berbagai tingkat *Quality Factor* (QF 95 turun hingga QF 5).
5. **Ekstraksi & Decoding:** Bit *watermark* diambil kembali dari citra rusak, diperbaiki oleh algoritma Hamming, dan direkonstruksi kembali ke bentuk semula.
6. **Ekspor Hasil:** Program mengonversi data hasil pengujian menjadi grafik evaluasi metrik (`cli_metrics_result.png`), grid visualisasi watermark (`cli_wm_grid_result.png`), serta mengekspor sampel gambar hasil kompresi ukuran penuh secara mandiri.

---

## 🛠 2. Arsitektur & Algoritma Utama

### A. Algoritma Watermarking: DCT Spread-Spectrum + Repetition
Sistem ini bekerja pada ranah **frekuensi**, bukan spasial (bukan memanipulasi warna piksel luar secara langsung), sehingga *watermark* bersifat tidak kasat mata (*invisible*).

1. **Transformasi Warna:** Citra masukan diubah dari ruang warna RGB menjadi **YCbCr**. Modifikasi hanya dilakukan pada kanal **Y (Luminance/Kecerahan)** karena mata manusia jauh lebih sensitif terhadap perubahan warna (CbCr) daripada perubahan kecerahan minor.
2. **Pembagian Blok:** Kanal Y dipecah menjadi matriks blok-blok kecil berukuran 8x8 piksel, lalu masing-masing blok dihitung nilai **Discrete Cosine Transform (DCT)**-nya.
3. **Penyisipan Mid-Band (Spread Spectrum):** Bit *watermark* ditanamkan pada koordinat koefisien frekuensi menengah (*mid-band*), seperti posisi (1,2), (2,1), (3,0), dst. Area ini dipilih karena paling seimbang; frekuensi rendah (pojok kiri atas) terlalu sensitif dan merusak visual citra jika diubah, sedangkan frekuensi tinggi (pojok kanan bawah) sangat rentan hilang total saat dikompresi oleh JPEG.
4. **Skema Modifikasi Additive:**
   Koefisien_baru = Koefisien_lama + (Sign * alpha * Noise)
   Di mana Sign = +1 jika bit data adalah 1, dan -1 jika bit data adalah 0. Alpha mewakili parameter kekuatan (`alpha`).
5. **Mekanisme Repetition:** Setiap 1 bit data tidak hanya disimpan di 1 blok, melainkan direplikasi sebanyak N kali (`repeats`) di berbagai blok acak berbeda (menggunakan *Pseudo-Random Number Generator Key* berbasis `seed`). Saat ekstraksi, keputusan bit akhir ditentukan lewat sistem voting mayoritas (*majority vote*).

### B. Algoritma Proteksi: Error Correction Code (ECC) Hamming(7,4)
Untuk meningkatkan ketahanan *watermark* dari degradasi data akibat kompresi ekstrem, pesan dienkode terlebih dahulu menggunakan prinsip kode Hamming(7,4):
* Setiap blok data **4 bit asli** akan dikombinasikan dengan **3 bit paritas (check bits)**, menghasilkan **7 bit kode blok terenkode**.
* Saat proses ekstraksi, perhitungan nilai *Syndrome* pada kode Hamming(7,4) mampu **mendeteksi dan memperbaiki secara otomatis** jika terjadi kerusakan sebesar 1 bit salah (*1-bit error correction*) pada setiap 7-bit blok data yang diterima akibat distorsi kompresi.

---

## 📊 3. Simulasi Serangan & Parameter Penilaian

Citra yang telah berhasil disisipi *watermark* akan diuji ketahanannya melalui serangkaian simulasi **Serangan Kompresi JPEG** dengan rentang *Quality Factor* (QF) dari **95 (kompresi ringan)** hingga **5 (kompresi sangat berat)**.

Keberhasilan performa sistem dievaluasi secara matematis menggunakan 3 metrik parameter standar berikut:

### 1. PSNR (Peak Signal-to-Noise Ratio)
Metrik untuk mengukur derajat kemiripan kualitas visual antara citra asli sebelum diproses dengan citra setelah dimanipulasi (ter-watermark/terkompresi). Satuan ukurnya adalah desibel (dB).
* **Indikator:** Nilai PSNR di atas **35 dB** menandakan kualitas gambar sangat baik dan perubahan tidak kasat mata oleh pandangan manusia.

### 2. BER (Bit Error Rate)
Metrik untuk menghitung persentase tingkat kesalahan bit *watermark* yang berhasil diekstrak dibandingkan dengan data asli.
* **Indikator:** Nilai BER berkisar antara 0.0 sampai 1.0. Nilai BER mendekati **0.0 (0%)** mengindikasikan ekstraksi data yang sempurna tanpa kesalahan. Batas toleransi aman kelolosan sistem ini diatur pada `BER < 0.1`.

### 3. NC (Normalized Correlation)
Metrik statistik untuk mengukur tingkat kedekatan linear atau korelasi kemiripan pola spasial geometri antara matriks *watermark* asli dengan matriks hasil ekstraksi.
* **Indikator:** Nilai NC berkisar antara 0.0 sampai 1.0. Nilai **1.0** berarti pola identik 100%. Batas toleransi keberhasilan ekstraksi sistem diatur pada syarat nilai `NC >= 0.5`.

---

## 🚀 4. Cara Setup & Penggunaan

### Langkah 1: Persiapan Environment
Pastikan komputer Anda sudah terpasang **Python 3.8** atau versi di atasnya. Buka terminal atau Command Prompt, kemudian klon atau masuk ke direktori tempat file proyek disimpan.

### Langkah 2: Instalasi Dependencies
Pasang seluruh pustaka (*library*) eksternal Python yang dibutuhkan dengan mengeksekusi perintah berikut melalui terminal:
```bash
pip install -r requirements.txt
```

### Langkah 3: Menjalankan Program
Jalankan skrip utama `main_cli.py` dengan perintah:
```bash
python main_cli.py
```

### Langkah 4: Interaksi dengan CLI
Saat program berjalan, Anda diminta untuk menginputkan beberapa konfigurasi secara dinamis (Tekan Enter langsung jika ingin menggunakan nilai saran default):
* **Path gambar:** Masukkan nama berkas gambar di folder lokal Anda (contoh: kain.jpg). Jika dikosongkan, sistem otomatis membangkitkan citra berwarna sintetis berukuran 256x256 piksel.
* **Alpha (Kekuatan Watermark):** Nilai kontrol amplitudo penyisipan [Saran: 10.0 - 16.0 untuk gambar asli resolusi tinggi].
* **Repeats (Replikasi):** Berapa kali salinan bit disebar ke seluruh blok citra [Saran: 4 - 16].
* **k_per_bit (Sebaran Koefisien):** Jumlah koefisien mid-band yang dimodifikasi di dalam setiap blok DCT [Saran: 8 atau 9].

## 📁 5. Struktur Berkas Output Hasil
Setelah proses kalkulasi simulasi selesai, program akan melahirkan beberapa berkas visual baru di dalam direktori kerja Anda:
* `cli_metrics_result.png:` Berisi file gambar satu baris yang memuat 3 grafik garis analisis kinerja sistem, yaitu grafik hubungan performa BER vs QF, NC vs QF, dan PSNR vs QF.
* `cli_wm_grid_result.png:` Grid visualisasi perbandingan gambar piksel watermark asli huruf "M" berdampingan dengan bentuk fisik huruf "M" yang berhasil ditarik keluar dari setiap tingkatan pecahan QF kompresi.
* `res_image_original_watermarked.png:` Berkas foto beresolusi penuh setelah disisipi watermark awal (kondisi sebelum diserang).
* `res_image_compressed_qf_[80/50/5].png:` Berkas contoh visual foto ukuran penuh hasil serangan kompresi komparatif pada tingkat QF 80, 50, dan 5 secara terpisah untuk mempermudah analisis kedetailan efek blocking artifact JPEG.