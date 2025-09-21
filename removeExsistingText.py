import os
import re

def rename_remove_paren2(folder):
    # Dosya adlarında "(2)" geçenleri bul ve kaldır
    for root, _, files in os.walk(folder):
        for file in files:
            new_name = re.sub(r'\(2\)', '', file)  # "(2)" kısmını kaldır
            if new_name != file:
                old_path = os.path.join(root, file)
                new_path = os.path.join(root, new_name)
                try:
                    # Aynı adda bir dosya varsa üzerine yazmamak için kontrol
                    if not os.path.exists(new_path):
                        os.rename(old_path, new_path)
                        print(f"Yeniden adlandırıldı: {file} -> {new_name}")
                    else:
                        print(f"Atlandı (zaten var): {new_name}")
                except Exception as e:
                    print(f"Hata: {file} -> {e}")

if __name__ == "__main__":
    klasor = input("Kontrol edilecek klasör yolunu girin: ").strip()
    rename_remove_paren2(klasor)
