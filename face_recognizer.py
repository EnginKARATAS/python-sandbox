#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D:\ Kök Klasör Yüz Etiketleyici
D:\ kök klasöründeki resimleri tarar ve Windows metadata etiketlerine yüz bilgilerini ekler

Kurulum: 
pip install opencv-contrib-python
pip install pywin32

Windows Etiketler: Sağ tık → Özellikler → Ayrıntılar → Etiketler
"""

print("🔍 Debug: Script başlatılıyor...")

try:
    import cv2
    print(f"✅ Debug: OpenCV {cv2.__version__} yüklendi")
except ImportError as e:
    print(f"❌ Debug: OpenCV yüklenemedi - {e}")
    print("pip install opencv-contrib-python komutunu çalıştırın")
    exit(1)

try:
    import numpy as np
    print("✅ Debug: NumPy yüklendi")
except ImportError:
    print("❌ Debug: NumPy yüklenemedi")
    exit(1)

import os
import pickle
import json
from pathlib import Path
import time
from datetime import datetime
import sys

print("✅ Debug: Temel kütüphaneler yüklendi")

# Windows metadata için
try:
    import win32com.propsys as propsys
    import pywintypes
    from win32com.shell import shell, shellcon
    METADATA_AVAILABLE = True
    print("✓ Windows metadata desteği yüklendi")
except ImportError:
    print("⚠️ Windows metadata desteği için: pip install pywin32")
    METADATA_AVAILABLE = False

print("🔍 Debug: Kütüphaneler kontrol edildi, sınıf tanımlanıyor...")

class DRootFaceTagger:
    def __init__(self):
        print("🚀 D:\\ Kök Klasör Yüz Etiketleyici Başlatılıyor...")
        
        # OpenCV
        try:
            self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            self.recognizer = cv2.face.LBPHFaceRecognizer_create()
            print(f"✓ OpenCV {cv2.__version__} yüklendi")
        except Exception as e:
            print(f"❌ OpenCV hatası: {e}")
            exit(1)
        
        # Dosya yolları
        self.model_file = "d_root_face_model.yml"
        self.labels_file = "d_root_face_labels.pkl"
        self.config_file = "d_root_config.json"
        self.log_file = "d_root_processing_log.txt"
        self.processed_files = "d_root_processed.json"
        
        # D:\ klasörü
        self.target_drive = r"D:\\"
        
        # Konfigürasyon
        self.config = {
            'confidence_threshold': 80,
            'min_face_size': (40, 40),
            'target_face_size': (100, 100),
            'supported_formats': ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'],
            'skip_large_files_mb': 50,
            'max_image_size': (1500, 1500),
            'batch_report_size': 50,
            'backup_metadata': True,
            'fallback_to_filename': True,  # Metadata başarısızsa dosya adına etiket ekle
            'tagging_method': 'both'  # 'metadata', 'filename', 'both'
        }
        
        # Veri yapıları
        self.label_to_id = {}
        self.id_to_label = {}
        self.next_id = 0
        self.processed_count = 0
        self.tagged_count = 0
        self.error_count = 0
        self.processed_files_set = set()
        
        # İstatistikler
        self.person_stats = {}
        self.start_time = None
        
        # Başlangıç
        print("🔍 Debug: Config yükleniyor...")
        self.load_config()
        print("🔍 Debug: Model yükleniyor...")
        self.load_model()
        print("🔍 Debug: İşlenmiş dosyalar yükleniyor...")
        self.load_processed_files()
        
        print(f"🎯 Hedef klasör: {self.target_drive}")
        print("🚀 Sistem hazır!\n")
    
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
            except:
                pass
        self.save_config()
    
    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except:
            pass
    
    def load_model(self):
        """Model ve kişileri yükle"""
        try:
            if os.path.exists(self.model_file) and os.path.exists(self.labels_file):
                self.recognizer.read(self.model_file)
                
                with open(self.labels_file, 'rb') as f:
                    data = pickle.load(f)
                    self.label_to_id = data['label_to_id']
                    self.id_to_label = data['id_to_label']
                    self.next_id = data['next_id']
                
                print(f"📚 Model yüklendi - Kayıtlı kişiler: {list(self.label_to_id.keys())}")
                
                # İstatistikleri initialize et
                for person in self.label_to_id.keys():
                    self.person_stats[person] = {'found_count': 0, 'tagged_count': 0}
                
                return True
        except Exception as e:
            print(f"⚠️ Model yükleme hatası: {e}")
        return False
    
    def add_person(self, person_name, image_paths):
        """Yeni kişi ekle"""
        if isinstance(image_paths, str):
            image_paths = [image_paths]
        
        person_name = person_name.lower().strip()
        
        if person_name not in self.label_to_id:
            self.label_to_id[person_name] = self.next_id
            self.id_to_label[self.next_id] = person_name
            self.next_id += 1
            self.person_stats[person_name] = {'found_count': 0, 'tagged_count': 0}
        
        label_id = self.label_to_id[person_name]
        
        all_face_samples = []
        all_labels = []
        total_faces = 0
        
        for image_path in image_paths:
            if not os.path.exists(image_path):
                continue
            
            try:
                image = cv2.imread(image_path)
                if image is None:
                    continue
                
                faces, gray = self.detect_faces(image)
                
                for i, (x, y, w, h) in enumerate(faces):
                    face_roi = gray[y:y+h, x:x+w]
                    face_roi = cv2.resize(face_roi, self.config['target_face_size'])
                    face_roi = cv2.equalizeHist(face_roi)
                    
                    all_face_samples.append(face_roi)
                    all_labels.append(label_id)
                    total_faces += 1
                
                print(f"  ✓ {os.path.basename(image_path)}: {len(faces)} yüz")
                
            except Exception as e:
                print(f"  ❌ {os.path.basename(image_path)}: {e}")
        
        if total_faces > 0:
            success = self.train_model(all_face_samples, all_labels)
            if success:
                print(f"🎯 '{person_name}' için {total_faces} yüz örneği kaydedildi")
                return True
        
        return False
    
    def batch_add_persons_from_folders(self, root_folder):
        """Kök klasörden tüm kişileri toplu ekle"""
        print(f"\n📁 TOPLU KİŞİ EKLEME: {root_folder}")
        print("="*50)
        
        if not os.path.exists(root_folder):
            print("❌ Klasör bulunamadı!")
            return False
        
        added_persons = 0
        total_faces = 0
        
        # Alt klasörleri tara
        try:
            subfolders = [f for f in os.listdir(root_folder) 
                         if os.path.isdir(os.path.join(root_folder, f))]
            
            if not subfolders:
                print("❌ Alt klasör bulunamadı!")
                return False
            
            print(f"📂 Bulunan klasörler: {', '.join(subfolders)}")
            print()
            
            for folder_name in subfolders:
                person_name = folder_name.lower().strip()
                person_folder = os.path.join(root_folder, folder_name)
                
                print(f"👤 İşleniyor: {person_name}")
                
                # Klasördeki resim dosyalarını bul
                image_files = []
                try:
                    for filename in os.listdir(person_folder):
                        if any(filename.lower().endswith(ext) for ext in self.config['supported_formats']):
                            image_files.append(os.path.join(person_folder, filename))
                    
                    if not image_files:
                        print(f"  ⚠️ {person_name} klasöründe resim bulunamadı")
                        continue
                    
                    print(f"  📷 {len(image_files)} resim bulundu")
                    
                    # Kişiyi ekle
                    if self.add_person(person_name, image_files):
                        added_persons += 1
                        # Son eklenen kişinin yüz sayısını hesapla
                        person_faces = self.person_stats[person_name].get('sample_count', 0)
                        total_faces += person_faces
                    
                    print()
                    
                except Exception as e:
                    print(f"  ❌ {person_name} klasörü işlenirken hata: {e}")
                    continue
                    
        except Exception as e:
            print(f"❌ Kök klasör okuma hatası: {e}")
            return False
        
        # Özet
        print("="*50)
        print("📊 TOPLU EKLEME ÖZETİ:")
        print(f"  👥 Eklenen kişi sayısı: {added_persons}")
        print(f"  👤 Toplam yüz örneği: {total_faces}")
        print(f"  📚 Toplam kayıtlı kişi: {len(self.label_to_id)}")
        
        if added_persons > 0:
            print("\n✅ Toplu ekleme başarılı!")
            print("🎯 Artık D:\\ klasörünü işleyebilirsiniz.")
            return True
        else:
            print("\n❌ Hiç kişi eklenemedi!")
            return False
    
    def train_model(self, face_samples=None, labels=None):
        """Model eğit"""
        try:
            if face_samples and labels:
                if os.path.exists(self.model_file) and len(self.label_to_id) > 1:
                    self.recognizer.update(face_samples, np.array(labels))
                else:
                    self.recognizer.train(face_samples, np.array(labels))
                
                self.recognizer.save(self.model_file)
                self.save_labels()
                return True
        except Exception as e:
            print(f"❌ Model eğitim hatası: {e}")
        return False
    
    def save_labels(self):
        try:
            data = {
                'label_to_id': self.label_to_id,
                'id_to_label': self.id_to_label,
                'next_id': self.next_id
            }
            with open(self.labels_file, 'wb') as f:
                pickle.dump(data, f)
        except:
            pass
    
    def load_processed_files(self):
        """İşlenmiş dosyaları yükle"""
        if os.path.exists(self.processed_files):
            try:
                with open(self.processed_files, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.processed_files_set = set(data.get('files', []))
                print(f"📋 {len(self.processed_files_set)} işlenmiş dosya yüklendi")
            except:
                self.processed_files_set = set()
    
    def save_processed_files(self):
        """İşlenmiş dosyaları kaydet"""
        try:
            with open(self.processed_files, 'w', encoding='utf-8') as f:
                json.dump({'files': list(self.processed_files_set)}, f, indent=2)
        except:
            pass
    
    def log_message(self, message):
        """Log mesajı"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
            print(message)
        except:
            print(message)
    
    def detect_faces(self, image):
        """Yüz tespiti"""
        try:
            # Büyük resimleri küçült
            h, w = image.shape[:2]
            max_w, max_h = self.config['max_image_size']
            
            if w > max_w or h > max_h:
                scale = min(max_w/w, max_h/h)
                new_w, new_h = int(w*scale), int(h*scale)
                image = cv2.resize(image, (new_w, new_h))
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            faces = self.face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=self.config['min_face_size']
            )
            
            return faces, gray
            
        except Exception as e:
            return [], None
    
    def recognize_faces_in_image(self, image_path):
        """Resimdeki yüzleri tanı"""
        try:
            image = cv2.imread(image_path)
            if image is None:
                return []
            
            faces, gray = self.detect_faces(image)
            if len(faces) == 0 or gray is None:
                return []
            
            recognized_persons = []
            
            for (x, y, w, h) in faces:
                face_roi = gray[y:y+h, x:x+w]
                face_roi = cv2.resize(face_roi, self.config['target_face_size'])
                face_roi = cv2.equalizeHist(face_roi)
                
                if len(self.label_to_id) > 0:
                    label_id, confidence = self.recognizer.predict(face_roi)
                    
                    if confidence < self.config['confidence_threshold']:
                        person_name = self.id_to_label.get(label_id)
                        if person_name and person_name not in recognized_persons:
                            recognized_persons.append(person_name)
                            self.person_stats[person_name]['found_count'] += 1
            
            return recognized_persons
            
        except Exception as e:
            return []
    
    def add_windows_metadata_tags(self, file_path, tags):
        """Windows metadata etiketlerini ekle"""
        if not tags:
            return False
        
        # Önce Windows metadata dene
        if METADATA_AVAILABLE:
            try:
                # Windows Property System kullan
                ps = propsys.PSGetPropertyKeyFromName("System.Keywords")
                
                # Mevcut etiketleri al
                existing_tags = []
                try:
                    prop_store = propsys.SHGetPropertyStoreFromParsingName(file_path)
                    prop_value = prop_store.GetValue(ps)
                    if prop_value.vt != 0:  # VT_EMPTY değilse
                        existing_tags = list(prop_value.GetValue())
                except:
                    pass
                
                # Yeni etiketleri ekle
                all_tags = existing_tags[:]
                for tag in tags:
                    if tag not in all_tags:
                        all_tags.append(tag)
                
                if len(all_tags) > len(existing_tags):
                    # Etiketleri kaydet
                    prop_store = propsys.SHGetPropertyStoreFromParsingName(file_path, None, propsys.GPS_READWRITE)
                    prop_variant = propsys.PROPVARIANTType(all_tags)
                    prop_store.SetValue(ps, prop_variant)
                    prop_store.Commit()
                    return True
                    
            except Exception as e:
                # Windows metadata başarısız, dosya adına etiket eklemeye geç
                pass
        
        # Windows metadata başarısızsa, dosya adına etiket ekle
        return self.add_filename_tags(file_path, tags)
    
    def add_filename_tags(self, file_path, tags):
        """Dosya adına etiket ekle (metadata başarısızsa)"""
        try:
            path_obj = Path(file_path)
            base_name = path_obj.stem
            extension = path_obj.suffix
            directory = path_obj.parent
            
            # Mevcut etiketleri temizle (önceki etiketleri kaldır)
            clean_name = base_name
            for person in self.label_to_id.keys():
                clean_name = clean_name.replace(f"_{person}", "").replace(f"-{person}", "")
            
            clean_name = clean_name.rstrip('_-')
            
            # Yeni etiketleri ekle
            tags_str = "_".join(sorted(tags))
            new_name = f"{clean_name}_{tags_str}{extension}"
            new_path = directory / new_name
            
            # Dosya adını değiştir
            if not new_path.exists() and new_path != Path(file_path):
                os.rename(file_path, new_path)
                return True
                
        except Exception as e:
            return False
        
        return False
    
    def get_image_files_in_directory(self, directory):
        """Klasördeki resim dosyalarını bul"""
        image_files = []
        
        try:
            for filename in os.listdir(directory):
                if any(filename.lower().endswith(ext) for ext in self.config['supported_formats']):
                    file_path = os.path.join(directory, filename)
                    
                    # Dosya boyutu kontrolü
                    try:
                        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        if file_size_mb <= self.config['skip_large_files_mb']:
                            image_files.append(file_path)
                        else:
                            self.log_message(f"⏭️ Büyük dosya atlandı ({file_size_mb:.1f}MB): {filename}")
                    except:
                        continue
        except Exception as e:
            self.log_message(f"❌ Klasör okuma hatası: {e}")
        
        return image_files
    
    def process_d_root_images(self):
        """D:\ kök klasöründeki resimleri işle"""
        if not os.path.exists(self.target_drive):
            print(f"❌ {self.target_drive} bulunamadı!")
            return
        
        if len(self.label_to_id) == 0:
            print("❌ Hiç kişi eğitilmemiş! Önce kişi eklemelisiniz.")
            return
        
        print(f"\n🚀 {self.target_drive} kök klasörü taranıyor...")
        print(f"👥 Aranacak kişiler: {list(self.label_to_id.keys())}")
        print(f"⚙️ Güven eşiği: {self.config['confidence_threshold']}")
        
        # Resim dosyalarını bul
        self.log_message(f"Resim dosyaları aranıyor: {self.target_drive}")
        image_files = self.get_image_files_in_directory(self.target_drive)
        
        if not image_files:
            print(f"❌ {self.target_drive} klasöründe resim bulunamadı!")
            return
        
        # İşlenecek dosyaları filtrele
        new_files = [f for f in image_files if f not in self.processed_files_set]
        total_files = len(image_files)
        new_files_count = len(new_files)
        
        print(f"\n📊 Dosya Durumu:")
        print(f"  📁 Toplam resim: {total_files}")
        print(f"  🆕 Yeni dosya: {new_files_count}")
        print(f"  ✅ Daha önce işlenmiş: {total_files - new_files_count}")
        
        if new_files_count == 0:
            print("✅ Tüm dosyalar daha önce işlenmiş!")
            return
        
        # İşleme başla
        self.start_time = time.time()
        self.processed_count = 0
        self.tagged_count = 0
        self.error_count = 0
        
        print(f"\n🎯 İşlem başlıyor... ({new_files_count} dosya)")
        print("="*60)
        
        for i, file_path in enumerate(new_files, 1):
            try:
                filename = os.path.basename(file_path)
                
                # Yüzleri tanı
                recognized_persons = self.recognize_faces_in_image(file_path)
                
                self.processed_count += 1
                
                if recognized_persons:
                    # Windows metadata veya dosya adı etiketleri ekle
                    success = False
                    
                    if self.config['tagging_method'] in ['metadata', 'both']:
                        success = self.add_windows_metadata_tags(file_path, recognized_persons)
                        
                    if not success and self.config['tagging_method'] in ['filename', 'both']:
                        success = self.add_filename_tags(file_path, recognized_persons)
                        if success:
                            # Dosya adı değişti, yeni yolu güncelle
                            path_obj = Path(file_path)
                            directory = path_obj.parent
                            clean_name = path_obj.stem
                            for person in self.label_to_id.keys():
                                clean_name = clean_name.replace(f"_{person}", "").replace(f"-{person}", "")
                            clean_name = clean_name.rstrip('_-')
                            tags_str = "_".join(sorted(recognized_persons))
                            new_filename = f"{clean_name}_{tags_str}{path_obj.suffix}"
                            new_file_path = directory / new_filename
                            self.processed_files_set.add(str(new_file_path))
                    
                    if success:
                        self.tagged_count += 1
                        for person in recognized_persons:
                            self.person_stats[person]['tagged_count'] += 1
                        
                        method = "metadata" if self.config['tagging_method'] == 'metadata' else "filename"
                        self.log_message(f"✅ {filename}: {', '.join(recognized_persons)} ({method})")
                    else:
                        self.log_message(f"⚠️ {filename}: Tanındı ama etiketlenemedi - {', '.join(recognized_persons)}")
                else:
                    self.log_message(f"⏭️ {filename}: Tanınan yüz yok")
                
                # İşlenmiş dosyaları kaydet
                self.processed_files_set.add(file_path)
                
                # İlerleme raporu
                if i % self.config['batch_report_size'] == 0:
                    elapsed = time.time() - self.start_time
                    rate = i / elapsed
                    remaining = (new_files_count - i) / rate if rate > 0 else 0
                    
                    print(f"📊 İlerleme: {i}/{new_files_count} ({i/new_files_count*100:.1f}%) "
                          f"- Etiketlenen: {self.tagged_count} "
                          f"- Kalan süre: {remaining/60:.1f} dakika")
                    
                    # Ara kayıt
                    self.save_processed_files()
                
            except Exception as e:
                self.error_count += 1
                self.log_message(f"❌ {os.path.basename(file_path)}: {str(e)}")
        
        # Son kayıt
        self.save_processed_files()
        
        # Özet rapor
        elapsed_time = time.time() - self.start_time
        self.print_final_report(elapsed_time)
    
    def print_final_report(self, elapsed_time):
        """Final raporu yazdır"""
        print(f"\n{'='*60}")
        print("🎉 İŞLEM TAMAMLANDI!")
        print("="*60)
        
        print(f"⏱️  Geçen süre: {elapsed_time/60:.1f} dakika")
        print(f"📊 İşlenen dosya: {self.processed_count}")
        print(f"✅ Etiketlenen: {self.tagged_count}")
        print(f"❌ Hata: {self.error_count}")
        print(f"🎯 Başarı oranı: {(self.tagged_count/self.processed_count)*100 if self.processed_count > 0 else 0:.1f}%")
        
        print(f"\n👥 KİŞİ İSTATİSTİKLERİ:")
        for person, stats in self.person_stats.items():
            found = stats['found_count']
            tagged = stats['tagged_count']
            print(f"  🔸 {person.title()}: {found} kez bulundu, {tagged} dosya etiketlendi")
        
        self.log_message("İşlem tamamlandı")
        self.log_message(f"Özet: {self.processed_count} işlendi, {self.tagged_count} etiketlendi")


def main():
    """Ana menü"""
    print("🔍 Debug: main() fonksiyonu çağrılıyor...")
    
    try:
        print("🔍 Debug: DRootFaceTagger sınıfı oluşturuluyor...")
        system = DRootFaceTagger()
        print("🔍 Debug: Sınıf başarıyla oluşturuldu!")
    except Exception as e:
        print(f"❌ Debug: Sınıf oluşturma hatası: {e}")
        return
    
    print("="*60)
    print(f"🤖 D:\\ KÖK KLASÖR YÜZ ETİKETLEYİCİ")
    print("="*60)
    
    while True:
        print(f"\n{'='*40}")
        print("🎯 MENÜ SEÇENEKLERİ")
        print("="*40)
        print("1️⃣  Toplu kişi ekleme (klasörden)")
        print("2️⃣  Tek kişi ekle (manuel)")
        print("3️⃣  D:\\ kök klasörü işle")
        print("4️⃣  İstatistikler ve durum")
        print("5️⃣  Ayarlar")
        print("6️⃣  Test - tek dosya")
        print("0️⃣  Çıkış")
        
        try:
            choice = input(f"\n🔢 Seçiminiz (0-6): ").strip()
            
            if choice == '1':
                print(f"\n📁 TOPLU KİŞİ EKLEME")
                print("Klasör yapısı:")
                print("  ana_klasör/")
                print("  ├── engin/")
                print("  │   ├── foto1.jpg")
                print("  │   └── foto2.jpg")
                print("  ├── kedi/")
                print("  │   ├── kedi1.jpg")
                print("  │   └── kedi2.jpg")
                print("  └── ayse/")
                print("      └── ayse1.jpg")
                print()
                
                root_folder = input("Ana klasör yolu: ").strip().strip('"')
                
                if os.path.exists(root_folder):
                    success = system.batch_add_persons_from_folders(root_folder)
                    if success:
                        print("\n🎉 Artık D:\\ işleme adımına geçebilirsiniz!")
                else:
                    print("❌ Klasör bulunamadı")
            
            elif choice == '2':
                print(f"\n👤 TEK KİŞİ EKLEME")
                person_name = input("Kişi/Nesne adı (kedi, engin vs.): ").strip()
                
                if person_name:
                    image_paths = []
                    print("Örnek fotoğraf yolları girin (boş bırak = bitir):")
                    
                    while True:
                        path = input("📁 Fotoğraf yolu: ").strip().strip('"')
                        if not path:
                            break
                        if os.path.exists(path):
                            image_paths.append(path)
                            print("  ✓ Eklendi")
                        else:
                            print("  ❌ Dosya bulunamadı")
                    
                    if image_paths:
                        system.add_person(person_name, image_paths)
                    else:
                        print("❌ Hiç fotoğraf eklenmedi")
            
            elif choice == '3':
                print(f"\n🚀 D:\\ KÖK KLASÖR İŞLEME")
                
                if len(system.label_to_id) == 0:
                    print("❌ Önce kişi eklemelisiniz! (Seçenek 1 veya 2)")
                    continue
                
                print(f"👥 Aranacak kişiler: {list(system.label_to_id.keys())}")
                confirm = input(f"\nD:\\ klasöründeki tüm resimleri işlemek istediğinizden emin misiniz? (E/h): ")
                
                if confirm.lower() in ['e', 'evet', 'yes', 'y']:
                    system.process_d_root_images()
                else:
                    print("❌ İşlem iptal edildi")
            
            elif choice == '4':
                print(f"\n📊 SİSTEM DURUMU:")
                print(f"  👥 Kayıtlı kişi sayısı: {len(system.label_to_id)}")
                print(f"  📁 Hedef klasör: {system.target_drive}")
                print(f"  ✅ İşlenmiş dosya: {len(system.processed_files_set)}")
                print(f"  ⚙️ Güven eşiği: {system.config['confidence_threshold']}")
                print(f"  📝 Log dosyası: {system.log_file}")
                
                if system.person_stats:
                    print(f"\n👥 KİŞİ İSTATİSTİKLERİ:")
                    for person, stats in system.person_stats.items():
                        print(f"  🔸 {person}: {stats['tagged_count']} etiketleme")
            
            elif choice == '5':
                print(f"\n⚙️ AYARLAR")
                print(f"Şu anki ayarlar:")
                print(f"  Güven eşiği: {system.config['confidence_threshold']}")
                print(f"  Etiketleme yöntemi: {system.config['tagging_method']}")
                
                new_threshold = input(f"\nYeni güven eşiği (şuanki: {system.config['confidence_threshold']}): ").strip()
                if new_threshold.isdigit():
                    system.config['confidence_threshold'] = int(new_threshold)
                    print("✅ Güven eşiği güncellendi")
                
                print(f"\nEtiketleme yöntemi:")
                print(f"  1: Sadece Windows metadata")
                print(f"  2: Sadece dosya adı") 
                print(f"  3: Her ikisi (önce metadata, başarısızsa dosya adı)")
                
                method_choice = input(f"Seçim (1-3, şuanki: {system.config['tagging_method']}): ").strip()
                if method_choice == '1':
                    system.config['tagging_method'] = 'metadata'
                    print("✅ Sadece Windows metadata kullanılacak")
                elif method_choice == '2':
                    system.config['tagging_method'] = 'filename'
                    print("✅ Sadece dosya adı kullanılacak")
                elif method_choice == '3':
                    system.config['tagging_method'] = 'both'
                    print("✅ Her iki yöntem kullanılacak (hibrit)")
                
                system.save_config()
            
            elif choice == '6':
                print(f"\n🧪 TEK DOSYA TESTİ")
                test_path = input("Test dosya yolu: ").strip().strip('"')
                
                if os.path.exists(test_path):
                    print(f"Testing: {os.path.basename(test_path)}")
                    persons = system.recognize_faces_in_image(test_path)
                    if persons:
                        print(f"✅ Tanınan: {', '.join(persons)}")
                        # Test etiketleme
                        if system.add_windows_metadata_tags(test_path, persons):
                            print("✅ Windows etiketleri eklendi")
                        else:
                            print("⚠️ Etiket eklenemedi")
                    else:
                        print("❌ Tanınan yüz yok")
                else:
                    print("❌ Dosya bulunamadı")
            
            elif choice == '0':
                print("\n👋 Sistem kapatılıyor...")
                break
            
            else:
                print("❌ Geçersiz seçim!")
                
        except KeyboardInterrupt:
            print(f"\n\n👋 İşlem iptal edildi...")
            break
        except Exception as e:
            print(f"❌ Hata: {e}")
    
    print("İyi günler! 🌟")


if __name__ == "__main__":
    print("🔍 Debug: __main__ bloğu çalışıyor...")
    try:
        main()
    except Exception as e:
        print(f"❌ Debug: main() çağrısında hata: {e}")
        import traceback
        traceback.print_exc()