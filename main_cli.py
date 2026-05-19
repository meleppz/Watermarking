import sys
import os
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')  # Mencegah pop-up GUI, langsung save file gambar
import matplotlib.pyplot as plt

# Import core logic yang sudah kamu punya
from dct_watermark import (
    generate_binary_watermark,
    embed_watermark_dct,
    extract_watermark_dct,
    jpeg_compress,
    calculate_ber,
    calculate_nc,
    calculate_psnr
)
from ecc import hamming74_encode, hamming74_decode


def load_image(path):
    if path and os.path.exists(path):
        img = Image.open(path).convert('RGB')
        w, h = img.size

        # Sempurnakan ukuran agar pas kelipatan 8 (Syarat Blok DCT 8x8)
        new_w = (w // 8) * 8
        new_h = (h // 8) * 8

        if (new_w != w) or (new_h != h):
            img = img.crop((0, 0, new_w, new_h))
            print(f"[INFO] Gambar di-crop halus dari {w}x{h} menjadi {new_w}x{h_new} agar pas dengan blok 8x8.")

        print(f"[INFO] Menggunakan gambar asli dengan resolusi: {img.size} (W x H)")
        return np.array(img)

    # fallback ke sintetis tetap 256x256 jika gambar tidak diinput
    print("[INFO] Gambar tidak ditemukan/tidak diinput. Membuat citra sintetis 256x256...")
    x = np.linspace(0, 1, 256)
    y = np.linspace(0, 1, 256)
    xx, yy = np.meshgrid(x, y)
    r = (np.sin(xx * np.pi) * np.cos(yy * np.pi) * 127 + 128).astype(np.uint8)
    g = (np.cos(xx * np.pi) * np.sin(yy * np.pi) * 80 + 160).astype(np.uint8)
    b = ((xx * yy) * 100 + 80).astype(np.uint8)
    return np.stack([r, g, b], axis=-1)


def main():
    print("=" * 60)
    print("    DIGITAL WATERMARKING DCT + ECC (HAMMING 7,4) INTERACTIVE CLI    ")
    print("=" * 60)

    # 1. Input Parameter dari User
    try:
        img_path = input("Masukkan path gambar (kosongkan untuk citra sintetis): ").strip()
        alpha = float(input("Masukkan kekuatan Watermark (Alpha) [Saran: 6.0 - 40.0]: ") or 14.0)
        repeats = int(input("Masukkan jumlah Replikasi (Repeats) [Saran: 4 - 16]: ") or 9)
        k_per_bit = int(input("Masukkan parameter sebaran (k_per_bit) [Saran: 4 - 9]: ") or 8)
    except ValueError:
        print("[ERROR] Input harus berupa angka! Silakan jalankan ulang skrip.")
        return

    # 2. Setup Data Gambar & Watermark (Pakai payload kecil 8x8 sesuai tweak_search)
    img = load_image(img_path)
    WM_SHAPE = (8, 8)
    watermark = np.array([
        [1, 0, 0, 0, 0, 0, 0, 1],
        [1, 1, 0, 0, 0, 0, 1, 1],
        [1, 0, 1, 0, 0, 1, 0, 1],
        [1, 0, 0, 1, 1, 0, 0, 1],
        [1, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 0, 0, 0, 0, 0, 1]
    ], dtype=np.uint8)
    wm_bits = watermark.flatten()

    # 3. Proses Proteksi ECC (Hamming 7,4)
    encoded_bits, pad_len = hamming74_encode(wm_bits)

    # Cek kapasitas blok sebelum lanjut agar tidak crash di dct_watermark
    total_blocks = (img.shape[0] // 8) * (img.shape[1] // 8)
    if repeats * encoded_bits.size > total_blocks:
        print(f"\n[ERROR] Konfigurasi terlalu gemuk! Kebutuhan blok ({repeats * encoded_bits.size}) "
              f"melebihi kapasitas gambar ({total_blocks}).")
        print("-> Solusi: Perkecil nilai 'repeats'.")
        return

    # 4. Proses Embed Watermark
    print("\n[PROSES] Menyisipkan watermark ke dalam ranah frekuensi DCT...")
    watermarked = embed_watermark_dct(img.copy(), encoded_bits, seed=7,
                                      alpha=alpha, repeats=repeats, k_per_bit=k_per_bit)

    # Simpan hasil gambar ber-watermark original sebelum kompresi
    Image.fromarray(watermarked).save('cli_watermarked_original.png')
    embed_psnr = calculate_psnr(img, watermarked)
    print(f"[SAVED] Gambar ter-watermark disimpan ke: 'cli_watermarked_original.png'")
    print(f"[METRIK] PSNR Embedding (Kualitas Gambar): {embed_psnr:.2f} dB")

    # 5. Simulasi Kompresi JPEG & Uji Ketahanan
    qf_list = [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95]
    bers, ncs, psnrs, extracted_wms = [], [], [], []

    print("\n[PROSES] Menjalankan simulasi serangan kompresi JPEG...")
    print("-" * 75)
    print(f"{'QF':>4} │ {'BER':>8} │ {'NC':>8} │ {'PSNR (dB)':>10} │ {'Status Ekstraksi':>18}")
    print("-" * 75)

    for qf in qf_list:
        # Kompresi
        comp = jpeg_compress(watermarked, quality=qf)

        # Ekstrak bit ter-encode dari DCT
        extr_enc = extract_watermark_dct(comp, wm_shape=(encoded_bits.size,), seed=7,
                                         repeats=repeats, k_per_bit=k_per_bit)

        # Decode kembali pakai ECC dengan pad_len yang benar
        decoded, _ = hamming74_decode(extr_enc.flatten(), pad_len=pad_len)
        decoded_wm_bits = decoded[:wm_bits.size]
        decoded_wm = decoded_wm_bits.reshape(WM_SHAPE)

        # Hitung Metrik Ketahanan terhadap watermark original asli
        ber = calculate_ber(watermark, decoded_wm)
        nc = calculate_nc(watermark, decoded_wm)
        psnr = calculate_psnr(img, comp)

        bers.append(ber)
        ncs.append(nc)
        psnrs.append(psnr)
        extracted_wms.append(decoded_wm)

        status = "✔ Dapat diekstrak" if (ber < 0.1 and nc >= 0.5) else "✘ GAGAL diekstrak"
        print(f"{qf:>4} │ {ber:>8.4f} │ {nc:>8.4f} │ {psnr:>10.2f} │ {status}")

    print("-" * 75)

    # 6. Eksport Visualisasi Grafik & Grid Watermark
    # Grafik Metrik
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    axes[0].plot(qf_list, bers, 'ro-'); axes[0].set_title('BER vs QF (Makin kecil makin bagus)'); axes[0].grid(True)
    axes[1].plot(qf_list, ncs, 'gs-'); axes[1].set_title('NC vs QF (Makin besar makin bagus)'); axes[1].grid(True)
    axes[2].plot(qf_list, psnrs, 'b^-'); axes[2].set_title('PSNR vs QF (Kualitas Gambar)'); axes[2].grid(True)
    plt.tight_layout()
    plt.savefig('cli_metrics_result.png')

    # 6. Eksport Visualisasi Grafik & Grid Watermark
    # Grafik Metrik
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    axes[0].plot(qf_list, bers, 'ro-'); axes[0].set_title('BER vs QF (Makin kecil makin bagus)'); axes[0].grid(True)
    axes[1].plot(qf_list, ncs, 'gs-'); axes[1].set_title('NC vs QF (Makin besar makin bagus)'); axes[1].grid(True)
    axes[2].plot(qf_list, psnrs, 'b^-'); axes[2].set_title('PSNR vs QF (Kualitas Gambar)'); axes[2].grid(True)
    plt.tight_layout()
    plt.savefig('cli_metrics_result.png')

    # Grid Gambar Watermark Hasil Ekstraksi (Tetap dipertahankan untuk backup)
    cols = min(len(qf_list) + 1, 6)
    rows = ((len(qf_list) + 1) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 2.5, rows * 2.5))
    axes = np.array(axes).flatten()

    axes[0].imshow(watermark, cmap='gray', vmin=0, vmax=1, interpolation='nearest')
    axes[0].set_title('WM Asli'); axes[0].axis('off')

    for i, qf in enumerate(qf_list):
        ax = axes[i + 1]
        ax.imshow(extracted_wms[i], cmap='gray', vmin=0, vmax=1, interpolation='nearest')
        ax.set_title(f'QF = {qf}')
        ax.axis('off')

    for j in range(i + 2, len(axes)):
        axes[j].axis('off')

    plt.tight_layout()
    plt.savefig('cli_wm_grid_result.png')

    # ──────────────────────────────────────────────────────────────
    # FITUR UPDATE: Simpan Gambar Hasil Kompresi Secara Terpisah (Gak Bakal Kekecilan)
    # ──────────────────────────────────────────────────────────────
    print("\n[PROSES] Menyimpan sampel gambar hasil kompresi secara terpisah...")

    # 1. Simpan Gambar Watermarked Original (Sebelum Kompresi)
    Image.fromarray(watermarked).save('res_image_original_watermarked.png')
    print(f" - [SAVED] 'res_image_original_watermarked.png' (PSNR: {embed_psnr:.2f} dB)")

    # 2. Loop untuk menyimpan QF 80, QF 50, dan QF 5 secara mandiri
    target_qfs = [80, 50, 5]
    for target_qf in target_qfs:
        comp_target = jpeg_compress(watermarked, quality=target_qf)
        psnr_target = calculate_psnr(img, comp_target)

        # Cari watermark yang sesuai dengan QF ini untuk dicantumkan di print terminal (opsional)
        qf_idx = qf_list.index(target_qf)
        ber_target = bers[qf_idx]
        nc_target = ncs[qf_idx]

        # Simpan file gambar hasil kompresi ukuran penuh
        filename = f'res_image_compressed_qf_{target_qf}.png'
        Image.fromarray(comp_target).save(filename)
        print(f" - [SAVED] '{filename}' (PSNR: {psnr_target:.2f} dB | BER WM: {ber_target:.4f})")
    # ──────────────────────────────────────────────────────────────

    print("\n[DONE] Evaluasi selesai! Semua file gambar terkompresi disimpan terpisah dengan ukuran asli.")
    print("Kamu bisa buka langsung filenya di folder proyek untuk membandingkan kedetailannya.")
    print("=" * 60)


if __name__ == '__main__':
    main()