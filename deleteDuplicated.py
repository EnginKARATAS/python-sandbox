import os
import hashlib

def file_hash(path, block_size=65536):
    """Dosyanın MD5 hash'ini döndürür."""
    hasher = hashlib.md5()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            hasher.update(block)
    return hasher.hexdigest()

def remove_duplicates(folder):
    seen = {}  # { (size, hash) : dosya_yolu }
    duplicates = []

    for root, _, files in os.walk(folder):
        for file in files:
            path = os.path.join(root, file)
            try:
                size = os.path.getsize(path)
                file_id = (size,)  # önce boyut ile grupla

                # Aynı boyutta başka dosya varsa hash hesapla
                if file_id in seen:
                    file_hash_val = file_hash(path)
                    orig_hash_val = file_hash(seen[file_id])
                    if file_hash_val == orig_hash_val:
                        duplicates.append(path)
                        continue
                    else:
                        # Aynı boyutta ama farklı içerik varsa hash'leri ayır
                        seen[(size, file_hash_val)] = path
                else:
                    # Bu boyut ilk kez görülüyorsa kaydet
                    seen[file_id] = path
            except Exception as e:
                print(f"Hata: {path} - {e}")

    # Silmeden önce listele
    if duplicates:
        print("Silinecek kopyalar:")
        for d in duplicates:
            print(d)

        # Onay al
        onay = input("Bu dosyaları silmek istiyor musunuz? (e/h): ").strip().lower()
        if onay == 'e':
            for d in duplicates:
                try:
                    os.remove(d)
                    print(f"Silindi: {d}")
                except Exception as e:
                    print(f"Silinemedi: {d} - {e}")
    else:
        print("Hiçbir kopya bulunamadı.")

if __name__ == "__main__":
    klasor = input("Kontrol edilecek klasör yolunu girin: ").strip()
    remove_duplicates(klasor)
