#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gelişmiş Yüz Kümeleme Sistemi
OpenCV'nin LBPH Face Recognizer'ını doğrudan kullanır
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
import shutil
from collections import defaultdict

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

class SmartFaceClusteringSystem:
    def __init__(self):
        print("🚀 Gelişmiş Yüz Kümeleme Sistemi Başlatılıyor...")
        
        # OpenCV
        try:
            self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            print(f"✓ OpenCV {cv2.__version__} yüklendi")
        except Exception as e:
            print(f"❌ OpenCV hatası: {e}")
            exit(1)
        
        # Dosya yolları
        self.clusters_file = "smart_face_clusters.json"
        self.faces_dir = "extracted_faces"
        self.models_dir = "face_models"
        self.config_file = "smart_clustering_config.json"
        self.log_file = "smart_clustering_log.txt"
        
        # D:\ klasörü
        self.target_drive = "D:\\"
        
        # Konfigürasyon
        self.config = {
            'min_face_size': (60, 60),
            'face_save_size': (150, 150),
            'supported_formats': ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'],
            'skip_large_files_mb': 50,
            'max_image_size': (1200, 1200),
            'confidence_threshold': 70.0,  # LBPH için güven eşiği (ne kadar düşükse o kadar benzer)
            'min_cluster_size': 1,  # En az 1 yüz olması gereken grup
            'max_clusters': 50,  # Maksimum küme sayısı (çok fazla küme önleme)
        }
        
        # Veri yapıları
        self.clusters = {}  # {cluster_id: {'faces': [], 'recognizer': LBPH, 'name': '', 'representative': ''}}
        self.all_faces = []  # Tüm tespit edilen yüzler
        self.image_face_map = {}  # {image_path: [cluster_ids]}
        
        # İstatistikler
        self.stats = {
            'total_images': 0,
            'images_with_faces': 0,
            'total_faces': 0,
            'total_clusters': 0,
            'named_clusters': 0
        }
        
        # Başlangıç
        self.load_config()
        self.load_clusters()
        self.ensure_directories()
        
        print(f"🎯 Hedef klasör: {self.target_drive}")
        print("🚀 Sistem hazır!\n")
    
    def ensure_directories(self):
        """Gerekli klasörleri oluştur"""
        for directory in [self.faces_dir, self.models_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"📁 Oluşturuldu: {directory}")
    
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
    
    def load_clusters(self):
        """Önceki kümeleri ve modelleri yükle"""
        if os.path.exists(self.clusters_file):
            try:
                with open(self.clusters_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    cluster_data = data.get('clusters', {})
                    
                    for cluster_id, cluster_info in cluster_data.items():
                        model_file = os.path.join(self.models_dir, f"{cluster_id}_model.yml")
                        
                        recognizer = cv2.face.LBPHFaceRecognizer_create()
                        if os.path.exists(model_file):
                            try:
                                recognizer.read(model_file)
                            except:
                                pass
                        
                        self.clusters[cluster_id] = {
                            'faces': cluster_info.get('faces', []),
                            'recognizer': recognizer,
                            'name': cluster_info.get('name', ''),
                            'representative': cluster_info.get('representative', ''),
                            'trained': os.path.exists(model_file)
                        }
                    
                    self.all_faces = data.get('all_faces', [])
                    self.image_face_map = data.get('image_map', {})
                    self.stats = data.get('stats', self.stats)
                
                print(f"📚 {len(self.clusters)} küme yüklendi")
            except Exception as e:
                print(f"⚠️ Küme yükleme hatası: {e}")
    
    def save_clusters(self):
        """Kümeleri kaydet"""
        try:
            # Recognizer'ları kaydet
            for cluster_id, cluster_data in self.clusters.items():
                if cluster_data['trained']:
                    model_file = os.path.join(self.models_dir, f"{cluster_id}_model.yml")
                    try:
                        cluster_data['recognizer'].save(model_file)
                    except:
                        pass
            
            # Cluster bilgilerini kaydet (recognizer hariç)
            clusters_to_save = {}
            for cluster_id, cluster_data in self.clusters.items():
                clusters_to_save[cluster_id] = {
                    'faces': cluster_data['faces'],
                    'name': cluster_data['name'],
                    'representative': cluster_data['representative']
                }
            
            data = {
                'clusters': clusters_to_save,
                'all_faces': self.all_faces,
                'image_map': self.image_face_map,
                'stats': self.stats,
                'timestamp': datetime.now().isoformat()
            }
            
            with open(self.clusters_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"❌ Küme kaydetme hatası: {e}")
    
    def detect_faces(self, image):
        """Yüz tespiti - İyileştirilmiş"""
        try:
            # Büyük resimleri küçült
            h, w = image.shape[:2]
            max_w, max_h = self.config['max_image_size']
            
            original_image = image.copy()
            if w > max_w or h > max_h:
                scale = min(max_w/w, max_h/h)
                new_w, new_h = int(w*scale), int(h*scale)
                image = cv2.resize(image, (new_w, new_h))
            else:
                scale = 1.0
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Çoklu ölçekte yüz tespiti
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.05,  # Daha hassas
                minNeighbors=6,    # Daha katı
                minSize=self.config['min_face_size'],
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            # Koordinatları orijinal boyuta çevir
            if scale != 1.0:
                faces = (faces / scale).astype(int)
            
            return faces, cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY), original_image
            
        except Exception as e:
            print(f"Yüz tespit hatası: {e}")
            return [], None, None
    
    def save_face_image(self, image, face_rect, face_id):
        """Yüzü kaydet"""
        try:
            x, y, w, h = face_rect
            # Biraz marj ekle
            margin = max(10, min(w, h) // 10)
            x = max(0, x - margin)
            y = max(0, y - margin)
            w = min(image.shape[1] - x, w + 2*margin)
            h = min(image.shape[0] - y, h + 2*margin)
            
            face_roi = image[y:y+h, x:x+w]
            face_roi = cv2.resize(face_roi, self.config['face_save_size'])
            
            face_filename = f"face_{face_id:06d}.jpg"
            face_path = os.path.join(self.faces_dir, face_filename)
            cv2.imwrite(face_path, face_roi, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            return face_path
        except Exception as e:
            print(f"Yüz kaydetme hatası: {e}")
            return None
    
    def find_matching_cluster(self, face_image):
        """Yüz için uygun küme bul"""
        best_cluster_id = None
        best_confidence = float('inf')
        
        # Yüzü standart boyuta getir
        face_image = cv2.resize(face_image, (100, 100))
        face_image = cv2.equalizeHist(face_image)
        
        for cluster_id, cluster_data in self.clusters.items():
            if not cluster_data['trained'] or not cluster_data['faces']:
                continue
            
            try:
                # LBPH recognizer ile tahmin yap
                label, confidence = cluster_data['recognizer'].predict(face_image)
                
                # Düşük confidence = yüksek benzerlik
                if confidence < best_confidence and confidence < self.config['confidence_threshold']:
                    best_confidence = confidence
                    best_cluster_id = cluster_id
                    
            except Exception as e:
                continue
        
        return best_cluster_id, best_confidence
    
    def create_new_cluster(self, face_image, face_data):
        """Yeni küme oluştur"""
        cluster_id = f"person_{len(self.clusters) + 1:03d}"
        
        # LBPH recognizer oluştur ve eğit
        recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=1, neighbors=8, grid_x=8, grid_y=8, threshold=100.0
        )
        
        # İlk yüz ile eğit
        face_image = cv2.resize(face_image, (100, 100))
        face_image = cv2.equalizeHist(face_image)
        
        try:
            recognizer.train([face_image], np.array([0]))
            trained = True
        except Exception as e:
            print(f"Model eğitim hatası: {e}")
            trained = False
        
        self.clusters[cluster_id] = {
            'faces': [face_data],
            'recognizer': recognizer,
            'name': '',
            'representative': face_data['face_image_path'],
            'trained': trained
        }
        
        return cluster_id
    
    def add_to_cluster(self, cluster_id, face_image, face_data):
        """Kümeye yüz ekle ve modeli güncelle"""
        cluster = self.clusters[cluster_id]
        cluster['faces'].append(face_data)
        
        # Model güncelleme (incremental learning)
        try:
            face_image = cv2.resize(face_image, (100, 100))
            face_image = cv2.equalizeHist(face_image)
            
            # Mevcut modeli güncelle
            if cluster['trained']:
                cluster['recognizer'].update([face_image], np.array([0]))
            else:
                # İlk eğitim
                cluster['recognizer'].train([face_image], np.array([0]))
                cluster['trained'] = True
                
        except Exception as e:
            print(f"Model güncelleme hatası: {e}")
    
    def scan_and_cluster_faces(self):
        """D:\ klasöründeki yüzleri tara ve akıllı kümeleme yap"""
        if not os.path.exists(self.target_drive):
            print(f"❌ {self.target_drive} bulunamadı!")
            return
        
        print(f"\n🔍 {self.target_drive} klasöründeki resimler taranıyor...")
        print("🧠 Gelişmiş LBPH algoritması kullanılıyor...")
        print("="*60)
        
        # Resim dosyalarını bul
        image_files = []
        try:
            for filename in os.listdir(self.target_drive):
                if any(filename.lower().endswith(ext) for ext in self.config['supported_formats']):
                    file_path = os.path.join(self.target_drive, filename)
                    
                    try:
                        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        if file_size_mb <= self.config['skip_large_files_mb']:
                            image_files.append(file_path)
                        else:
                            print(f"⏭️ Büyük dosya atlandı ({file_size_mb:.1f}MB): {filename}")
                    except:
                        continue
        except Exception as e:
            print(f"❌ Klasör okuma hatası: {e}")
            return
        
        if not image_files:
            print(f"❌ {self.target_drive} klasöründe resim bulunamadı!")
            return
        
        print(f"📊 {len(image_files)} resim dosyası bulundu")
        print("🚀 Akıllı kümeleme başlıyor...\n")
        
        face_id_counter = len(self.all_faces)
        processed_count = 0
        faces_found = 0
        clustered_faces = 0
        new_clusters = 0
        
        for i, file_path in enumerate(image_files, 1):
            try:
                filename = os.path.basename(file_path)
                
                # Resmi yükle
                image = cv2.imread(file_path)
                if image is None:
                    continue
                
                # Yüzleri tespit et
                faces, gray, original_image = self.detect_faces(image)
                processed_count += 1
                
                if len(faces) == 0:
                    print(f"⏭️ {filename}: Yüz bulunamadı")
                    continue
                
                image_clusters = []
                
                for face_rect in faces:
                    face_id_counter += 1
                    faces_found += 1
                    
                    x, y, w, h = face_rect
                    face_roi_gray = gray[y:y+h, x:x+w]
                    
                    if face_roi_gray.size == 0:
                        continue
                    
                    # Yüzü kaydet
                    face_image_path = self.save_face_image(original_image, face_rect, face_id_counter)
                    if not face_image_path:
                        continue
                    
                    # Yüz verisi oluştur
                    face_data = {
                        'id': face_id_counter,
                        'source_image': file_path,
                        'face_rect': face_rect.tolist(),
                        'face_image_path': face_image_path,
                    }
                    
                    # Uygun küme bul
                    matching_cluster, confidence = self.find_matching_cluster(face_roi_gray)
                    
                    if matching_cluster and len(self.clusters) < self.config['max_clusters']:
                        # Mevcut kümeye ekle
                        self.add_to_cluster(matching_cluster, face_roi_gray, face_data)
                        image_clusters.append(matching_cluster)
                        clustered_faces += 1
                        print(f"  🔗 {matching_cluster}'e eklendi (güven: {confidence:.1f})")
                    else:
                        # Yeni küme oluştur
                        if len(self.clusters) < self.config['max_clusters']:
                            new_cluster_id = self.create_new_cluster(face_roi_gray, face_data)
                            image_clusters.append(new_cluster_id)
                            new_clusters += 1
                            print(f"  📝 Yeni küme: {new_cluster_id}")
                        else:
                            # Max cluster sayısına ulaştık, en yakın kümeye zorla ekle
                            if self.clusters:
                                fallback_cluster = list(self.clusters.keys())[0]
                                self.add_to_cluster(fallback_cluster, face_roi_gray, face_data)
                                image_clusters.append(fallback_cluster)
                                print(f"  ⚠️ {fallback_cluster}'e zorla eklendi (max küme)")
                    
                    self.all_faces.append(face_data)
                
                # Resim-küme haritasını güncelle
                if image_clusters:
                    self.image_face_map[file_path] = image_clusters
                    unique_clusters = list(set(image_clusters))
                    print(f"👤 {filename}: {len(faces)} yüz → {len(unique_clusters)} küme")
                
                # İlerleme raporu
                if i % 10 == 0:
                    print(f"\n📊 İlerleme: {i}/{len(image_files)} resim")
                    print(f"   👤 Toplam yüz: {faces_found}")
                    print(f"   📦 Aktif küme: {len(self.clusters)}")
                    print(f"   🎯 Kümelenmiş: {clustered_faces}\n")
                    
                    # Ara kayıt
                    self.save_clusters()
                
            except Exception as e:
                print(f"❌ {filename}: {str(e)}")
                continue
        
        # İstatistikleri güncelle
        self.stats.update({
            'total_images': len(image_files),
            'images_with_faces': len(self.image_face_map),
            'total_faces': faces_found,
            'total_clusters': len(self.clusters),
        })
        
        # Son kayıt
        self.save_clusters()
        
        # Özet rapor
        print("\n" + "="*60)
        print("🎉 AKILLI KÜMELEME TAMAMLANDI!")
        print("="*60)
        print(f"📊 İşlenen resim: {processed_count}")
        print(f"👤 Bulunan yüz: {faces_found}")
        print(f"📦 Oluşan küme: {len(self.clusters)}")
        print(f"🆕 Yeni küme: {new_clusters}")
        print(f"🎯 Kümelenen yüz: {clustered_faces}")
        print(f"📁 Yüz klasörü: {self.faces_dir}")
        
        # En büyük kümeleri göster
        print(f"\n📦 EN BÜYÜK KÜMELER:")
        cluster_sizes = [(cid, len(cdata['faces'])) for cid, cdata in self.clusters.items()]
        cluster_sizes.sort(key=lambda x: x[1], reverse=True)
        
        for cluster_id, size in cluster_sizes[:10]:
            name = self.clusters[cluster_id]['name'] or 'İsimsiz'
            print(f"  🔸 {cluster_id}: {size} yüz ({name})")
        
        print(f"\n💡 Şimdi kümelere isim verebilirsiniz!")
    
    def show_cluster_representatives(self):
        """Küme temsilcilerini göster"""
        if not self.clusters:
            print("❌ Henüz hiç küme oluşturulmamış!")
            return
        
        print(f"\n📦 KÜME TEMSİLCİLERİ")
        print("="*50)
        
        # Küme boyutuna göre sırala
        sorted_clusters = sorted(self.clusters.items(), 
                               key=lambda x: len(x[1]['faces']), reverse=True)
        
        for cluster_id, cluster_data in sorted_clusters:
            face_count = len(cluster_data['faces'])
            name = cluster_data['name'] if cluster_data['name'] else 'İsimsiz'
            representative = cluster_data.get('representative', '')
            
            print(f"\n🔸 {cluster_id}:")
            print(f"   👥 Yüz sayısı: {face_count}")
            print(f"   📛 İsim: {name}")
            if representative and os.path.exists(representative):
                print(f"   🖼️ Temsilci: {representative}")
                print(f"      💡 Bu dosyayı açıp kontrol edebilirsiniz")
            
            # İlk birkaç kaynak resmi göster
            sources = set()
            for face_data in cluster_data['faces'][:5]:
                source = os.path.basename(face_data['source_image'])
                sources.add(source)
            
            if sources:
                print(f"   📄 Örnek kaynaklar: {', '.join(list(sources)[:3])}")
                if len(sources) > 3:
                    print(f"      ... ve {len(cluster_data['faces']) - 3} tane daha")
    
    def assign_cluster_names(self):
        """Kümelere isim ata"""
        if not self.clusters:
            print("❌ Henüz hiç küme oluşturulmamış!")
            return
        
        print(f"\n📛 KÜME İSİMLENDİRME")
        print("="*50)
        print("💡 Her küme için bir isim girin (boş bırakırsanız değişmez)")
        print("💡 'q' yazarsanız çıkış yaparsınız")
        print("💡 Küme boyutuna göre sıralandı (büyükten küçüğe)")
        print()
        
        # Küme boyutuna göre sırala
        sorted_clusters = sorted(self.clusters.items(), 
                               key=lambda x: len(x[1]['faces']), reverse=True)
        
        for cluster_id, cluster_data in sorted_clusters:
            face_count = len(cluster_data['faces'])
            current_name = cluster_data['name'] if cluster_data['name'] else 'İsimsiz'
            representative = cluster_data.get('representative', '')
            
            print(f"\n🔸 {cluster_id}:")
            print(f"   👥 {face_count} yüz")
            print(f"   📛 Şu anki isim: {current_name}")
            if representative and os.path.exists(representative):
                print(f"   🖼️ Temsilci resim: {representative}")
                print(f"      💡 Bu dosyayı açıp kontrol edebilirsiniz")
            
            new_name = input(f"   ✏️ Yeni isim (şuanki: {current_name}): ").strip()
            
            if new_name.lower() == 'q':
                break
            
            if new_name:
                self.clusters[cluster_id]['name'] = new_name
                print(f"   ✅ İsim güncellendi: {new_name}")
            else:
                print(f"   ⏭️ İsim değiştirilmedi")
        
        # Kaydet
        self.save_clusters()
        
        # Özet
        named_count = sum(1 for cd in self.clusters.values() if cd['name'])
        print(f"\n📊 {named_count}/{len(self.clusters)} kümeye isim verildi")
        
        self.stats['named_clusters'] = named_count
        print("💡 Artık D:\\ klasörünü etiketleyebilirsiniz!")
    
    def tag_images_with_cluster_names(self):
        """Küme isimlerini kullanarak resimleri etiketle"""
        named_clusters = {cid: cdata['name'] for cid, cdata in self.clusters.items() if cdata['name']}
        
        if not named_clusters:
            print("❌ Hiç kümeye isim verilmemiş!")
            return
        
        print(f"\n🏷️ RESİM ETİKETLEME")
        print("="*50)
        print(f"📛 İsimli küme sayısı: {len(named_clusters)}")
        print(f"📁 Etiketlenecek resim: {len(self.image_face_map)}")
        print()
        
        tagged_count = 0
        error_count = 0
        
        for image_path, cluster_ids in self.image_face_map.items():
            try:
                if not os.path.exists(image_path):
                    continue
                
                # Bu resimdeki kümelerin isimlerini topla
                person_names = set()
                
                for cluster_id in cluster_ids:
                    cluster_name = named_clusters.get(cluster_id)
                    if cluster_name:
                        person_names.add(cluster_name.lower())
                
                if person_names:
                    # Etiketleri ekle
                    success = self.add_tags_to_image(image_path, list(person_names))
                    if success:
                        tagged_count += 1
                        filename = os.path.basename(image_path)
                        print(f"✅ {filename}: {', '.join(person_names)}")
                    else:
                        error_count += 1
                        print(f"⚠️ {os.path.basename(image_path)}: Etiketlenemedi")
                
            except Exception as e:
                error_count += 1
                print(f"❌ {os.path.basename(image_path)}: {str(e)}")
        
        # Özet
        print(f"\n📊 ETİKETLEME ÖZETİ:")
        print(f"✅ Başarılı: {tagged_count}")
        print(f"❌ Hata: {error_count}")
        print(f"📁 Toplam resim: {len(self.image_face_map)}")
        
        if tagged_count > 0:
            print(f"\n🎉 {tagged_count} resim başarıyla etiketlendi!")
    
    def add_tags_to_image(self, file_path, tags):
        """Resme etiket ekle"""
        if not tags:
            return False
        
        # Windows metadata dene
        if METADATA_AVAILABLE:
            try:
                ps = propsys.PSGetPropertyKeyFromName("System.Keywords")
                
                existing_tags = []
                try:
                    prop_store = propsys.SHGetPropertyStoreFromParsingName(file_path)
                    prop_value = prop_store.GetValue(ps)
                    if prop_value.vt != 0:
                        existing_tags = list(prop_value.GetValue())
                except:
                    pass
                
                all_tags = existing_tags[:]
                for tag in tags:
                    if tag not in all_tags:
                        all_tags.append(tag)
                
                if len(all_tags) > len(existing_tags):
                    prop_store = propsys.SHGetPropertyStoreFromParsingName(file_path, None, propsys.GPS_READWRITE)
                    prop_variant = propsys.PROPVARIANTType(all_tags)
                    prop_store.SetValue(ps, prop_variant)
                    prop_store.Commit()
                    return True
                    
            except:
                pass
        
        # Dosya adına etiket ekle
        return self.add_filename_tags(file_path, tags)
    
    def add_filename_tags(self, file_path, tags):
        """Dosya adına etiket ekle"""
        try:
            path_obj = Path(file_path)
            base_name = path_obj.stem
            extension = path_obj.suffix
            directory = path_obj.parent
            
            # Mevcut etiketleri temizle
            clean_name = base_name
            for cluster_data in self.clusters.values():
                if cluster_data['name']:
                    clean_name = clean_name.replace(f"_{cluster_data['name']}", "").replace(f"-{cluster_data['name']}", "")
            
            clean_name = clean_name.rstrip('_-')
            
            # Yeni etiketleri ekle
            tags_str = "_".join(sorted(tags))
            new_name = f"{clean_name}_{tags_str}{extension}"
            new_path = directory / new_name
            
            # Dosya adını değiştir
            if not new_path.exists() and new_path != Path(file_path):
                os.rename(file_path, new_path)
                return True
                
        except:
            return False
        
        return False


def main():
    """Ana menü"""
    print("🔍 Debug: main() fonksiyonu çağrılıyor...")
    
    try:
        print("🔍 Debug: SmartFaceClusteringSystem sınıfı oluşturuluyor...")
        system = SmartFaceClusteringSystem()
        print("🔍 Debug: Sınıf başarıyla oluşturuldu!")
    except Exception as e:
        print(f"❌ Debug: Sınıf oluşturma hatası: {e}")
        return
    
    print("="*60)
    print(f"🤖 AKILLI YÜZ KÜMELEME VE ETİKETLEME SİSTEMİ")
    print("="*60)
    
    while True:
        print(f"\n{'='*40}")
        print("🎯 MENÜ SEÇENEKLERİ")
        print("="*40)
        print("1️⃣  D:\\ klasöründeki yüzleri tara ve akıllı grupla")
        print("2️⃣  Küme temsilcilerini görüntüle") 
        print("3️⃣  Kümelere isim ver")
        print("4️⃣  İsimlendirilmiş kümelerle etiketleme yap")
        print("5️⃣  İstatistikler ve durum")
        print("6️⃣  Ayarlar")
        print("7️⃣  Kümeleri temizle (yeniden başlat)")
        print("0️⃣  Çıkış")
        
        try:
            choice = input(f"\n🔢 Seçiminiz (0-7): ").strip()
            
            if choice == '1':
                print(f"\n🔍 D:\\ KLASÖRÜ AKILLI TARAMA")
                print("💡 Bu işlem LBPH algoritması ile benzer yüzleri gruplar")
                confirm = input(f"D:\\ klasöründeki tüm resimleri taramak istediğinizden emin misiniz? (E/h): ")
                
                if confirm.lower() in ['e', 'evet', 'yes', 'y']:
                    system.scan_and_cluster_faces()
                else:
                    print("❌ İşlem iptal edildi")
            
            elif choice == '2':
                system.show_cluster_representatives()
            
            elif choice == '3':
                system.assign_cluster_names()
            
            elif choice == '4':
                system.tag_images_with_cluster_names()
            
            elif choice == '5':
                print(f"\n📊 SİSTEM DURUMU:")
                print(f"  📁 Hedef klasör: {system.target_drive}")
                print(f"  📷 Toplam resim: {system.stats['total_images']}")
                print(f"  👤 Bulunan yüz: {system.stats['total_faces']}")
                print(f"  📦 Küme sayısı: {len(system.clusters)}")
                print(f"  📛 İsimli küme: {system.stats['named_clusters']}")
                print(f"  📂 Yüz klasörü: {system.faces_dir}")
                print(f"  🤖 Model klasörü: {system.models_dir}")
                
                if system.clusters:
                    print(f"\n📦 KÜME DETAYLARI:")
                    sorted_clusters = sorted(system.clusters.items(), 
                                           key=lambda x: len(x[1]['faces']), reverse=True)
                    
                    for cluster_id, cluster_data in sorted_clusters[:10]:
                        name = cluster_data['name'] if cluster_data['name'] else 'İsimsiz'
                        face_count = len(cluster_data['faces'])
                        trained = "✅" if cluster_data['trained'] else "❌"
                        print(f"  🔸 {cluster_id}: {face_count} yüz - {name} {trained}")
            
            elif choice == '6':
                print(f"\n⚙️ AYARLAR")
                print(f"Şu anki ayarlar:")
                print(f"  Güven eşiği: {system.config['confidence_threshold']}")
                print(f"  Maksimum küme: {system.config['max_clusters']}")
                print(f"  Min yüz boyutu: {system.config['min_face_size']}")
                
                new_threshold = input(f"\nYeni güven eşiği (0-150, şuanki: {system.config['confidence_threshold']}): ").strip()
                try:
                    threshold = float(new_threshold)
                    if 0 <= threshold <= 150:
                        system.config['confidence_threshold'] = threshold
                        print("✅ Güven eşiği güncellendi")
                        print("💡 Düşük değer = daha katı benzerlik")
                        print("💡 Yüksek değer = daha gevşek benzerlik")
                    else:
                        print("❌ Değer 0-150 arasında olmalı")
                except ValueError:
                    if new_threshold:
                        print("❌ Geçersiz sayı")
                
                new_max_clusters = input(f"\nMaksimum küme sayısı (şuanki: {system.config['max_clusters']}): ").strip()
                try:
                    max_clusters = int(new_max_clusters)
                    if 10 <= max_clusters <= 200:
                        system.config['max_clusters'] = max_clusters
                        print("✅ Maksimum küme sayısı güncellendi")
                    else:
                        print("❌ Değer 10-200 arasında olmalı")
                except ValueError:
                    if new_max_clusters:
                        print("❌ Geçersiz sayı")
                
                system.save_config()
            
            elif choice == '7':
                print(f"\n🗑️ KÜMELERİ TEMİZLE")
                print("⚠️ Bu işlem tüm kümeleri, yüz verilerini ve modelleri siler!")
                confirm = input("Tüm kümeleri silmek istediğinizden EMİN misiniz? (EVET yazın): ")
                
                if confirm == "EVET":
                    try:
                        # Küme dosyalarını sil
                        if os.path.exists(system.clusters_file):
                            os.remove(system.clusters_file)
                        
                        # Yüz ve model klasörlerini sil
                        for directory in [system.faces_dir, system.models_dir]:
                            if os.path.exists(directory):
                                shutil.rmtree(directory)
                        
                        # Sistem verilerini temizle
                        system.clusters = {}
                        system.all_faces = []
                        system.image_face_map = {}
                        system.stats = {
                            'total_images': 0,
                            'images_with_faces': 0,
                            'total_faces': 0,
                            'total_clusters': 0,
                            'named_clusters': 0
                        }
                        
                        # Klasörleri yeniden oluştur
                        system.ensure_directories()
                        
                        print("✅ Tüm kümeler ve modeller temizlendi!")
                        print("💡 Artık yeniden tarama yapabilirsiniz")
                        
                    except Exception as e:
                        print(f"❌ Temizleme hatası: {e}")
                else:
                    print("❌ İşlem iptal edildi")
            
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