import os
from ultralytics import YOLO
import cv2
from PIL import Image
import exiftool

# Modeli yükle (ilk çalıştırmada otomatik indirir)
model = YOLO('yolov8n.pt')  # Hızlı ama temel; daha doğru için 'yolov8l.pt' kullan

# pCloud senkron klasörü
folder_path = 'P:\Automatic Upload\F'  # Kendi yolunu buraya yaz

# Desteklenen dosya uzantıları
extensions = ('.jpg', '.jpeg', '.png')

# ExifTool başlat
with exiftool.ExifTool() as et:
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(extensions):
            file_path = os.path.join(folder_path, filename)
            
            # Resmi oku
            img = cv2.imread(file_path)
            if img is None:
                print(f"{filename} okunamadı.")
                continue
            
            # Nesne algılama
            results = model(img)
            
            # Algılanan nesneleri topla (güven skoru > 0.5)
            objects = set()
            for result in results:
                for box in result.boxes:
                    conf = box.conf.item()
                    if conf > 0.5:  # Güven eşiği
                        cls = int(box.cls.item())
                        label = model.names[cls]
                        objects.add(label.lower())  # Örneğin 'cat', 'car'
            
            if objects:
                # Mevcut anahtar kelimeleri oku (varsa)
                try:
                    current_tags = et.get_tag('XMP:Subject', file_path) or []
                    if isinstance(current_tags, str):
                        current_tags = current_tags.split(',')
                    current_tags = [tag.strip() for tag in current_tags]
                except:
                    current_tags = []
                
                # Yeni nesneleri ekle, tekrarları önle
                new_tags = list(set(current_tags + list(objects)))
                
                # Metadata'ya yaz
                try:
                    et.execute('-XMP:Subject=' + ','.join(new_tags), file_path.encode('utf-8'))
                    print(f"{filename} için etiketler eklendi: {', '.join(new_tags)}")
                except Exception as e:
                    print(f"{filename} için metadata yazılamadı: {e}")
            else:
                print(f"{filename} için nesne bulunamadı.")
                
print("İşlem tamamlandı!")