import face_recognition
import cv2
import os

def load_known_faces(folder):
    known_encodings = []
    known_names = []

    # Klasördeki her resmi Engin'in bir örneği olarak ekle
    for filename in os.listdir(folder):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        path = os.path.join(folder, filename)
        image = face_recognition.load_image_file(path)
        encodings = face_recognition.face_encodings(image)
        if encodings:
            known_encodings.append(encodings[0])
            known_names.append("Engin")
            print(f"Eklendi: {filename}")
        else:
            print(f"Yüz bulunamadı: {filename}")

    return known_encodings, known_names

def tag_faces(known_encodings, known_names, input_folder, output_folder, tolerance=0.45):
    os.makedirs(output_folder, exist_ok=True)

    for filename in os.listdir(input_folder):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        path = os.path.join(input_folder, filename)
        image = cv2.imread(path)
        if image is None:
            print(f"Okunamadı: {filename}")
            continue

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb)
        encodings = face_recognition.face_encodings(rgb, locations)

        for (top, right, bottom, left), face_encoding in zip(locations, encodings):
            matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=tolerance)
            name = "Unknown"

            # Eşleşme varsa Engin olarak etiketle
            if True in matches:
                name = "Engin"

            # Dikdörtgen ve isim çiz
            cv2.rectangle(image, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(image, name, (left, bottom + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        output_path = os.path.join(output_folder, filename)
        cv2.imwrite(output_path, image)
        print(f"Etiketlendi: {filename}")

if __name__ == "__main__":
    # Engin'in örnek fotoğrafları klasörü
    known_folder = input("Engin fotoğraflarının olduğu klasör yolunu girin: ").strip()
    known_encodings, known_names = load_known_faces(known_folder)

    # Etiketlenecek fotoğrafların olduğu klasör
    photos_folder = input("Kontrol edilecek fotoğraf klasörü yolunu girin: ").strip()
    output_folder = "tagged_photos"

    tag_faces(known_encodings, known_names, photos_folder, output_folder)
    print(f"\nİşlem tamamlandı. Etiketlenmiş fotoğraflar '{output_folder}' klasöründe.")
