import os
import subprocess
import shutil
from PIL import Image
import torch
import json
import sys

def find_exiftool():
    """Find ExifTool executable in common locations"""
    common_paths = [
        r'C:\Program Files\ExifTool\exiftool.exe',
        r'C:\Program Files (x86)\ExifTool\exiftool.exe',
        r'C:\ExifTool\exiftool.exe',
        'exiftool.exe',
        'exiftool'
    ]
    
    for path in common_paths:
        if shutil.which(path) or os.path.exists(path):
            return path
    return None

def test_exiftool(exiftool_path):
    """Test if ExifTool works"""
    try:
        result = subprocess.run([exiftool_path, '-ver'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"ExifTool bulundu, versiyon: {result.stdout.strip()}")
            return True
    except Exception as e:
        print(f"ExifTool test hatası: {e}")
    return False

def get_existing_tags(file_path, exiftool_path):
    """Get existing XMP:Subject tags"""
    try:
        cmd = [exiftool_path, '-XMP:Subject', '-json', file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data and len(data) > 0:
                subject = data[0].get('Subject', [])
                if isinstance(subject, str):
                    return [tag.strip() for tag in subject.split(',')]
                elif isinstance(subject, list):
                    return [str(tag).strip() for tag in subject]
        return []
    except Exception as e:
        print(f"Mevcut etiketler okunamadı: {e}")
        return []

def write_metadata_with_subprocess(file_path, tags, exiftool_path):
    """Write metadata using subprocess"""
    try:
        existing_tags = get_existing_tags(file_path, exiftool_path)
        all_tags = list(set(existing_tags + tags))
        all_tags = [tag for tag in all_tags if tag and len(tag.strip()) > 0]
        
        if not all_tags:
            return False
            
        tag_string = ','.join(all_tags)
        cmd = [exiftool_path, f'-XMP:Subject={tag_string}', '-overwrite_original', file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        return result.returncode == 0
    except Exception as e:
        print(f"Metadata yazma hatası: {e}")
        return False

def load_florence_model():
    """Load Florence-2 model with multiple fallback strategies"""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    
    print(f"Cihaz: {device}")
    print("Florence-2 modeli yükleniyor...")
    
    # Try different loading strategies
    loading_strategies = [
        {
            "name": "Strategy 1: Eager attention + manual device",
            "config": {
                "trust_remote_code": True,
                "torch_dtype": dtype,
                "attn_implementation": "eager",
                "device_map": None
            }
        },
        {
            "name": "Strategy 2: Auto device mapping",
            "config": {
                "trust_remote_code": True,
                "torch_dtype": dtype,
                "device_map": "auto" if device == "cuda" else None
            }
        },
        {
            "name": "Strategy 3: Basic loading",
            "config": {
                "trust_remote_code": True,
                "torch_dtype": torch.float32,  # Force float32
            }
        },
        {
            "name": "Strategy 4: Minimal config",
            "config": {
                "trust_remote_code": True,
            }
        }
    ]
    
    for strategy in loading_strategies:
        try:
            print(f"Deneniyor: {strategy['name']}")
            
            from transformers import AutoProcessor, AutoModelForCausalLM
            
            # Clear cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            model = AutoModelForCausalLM.from_pretrained(
                "microsoft/Florence-2-base",
                **strategy['config']
            )
            
            # Move to device if not handled by device_map
            if strategy['config'].get('device_map') is None:
                model = model.to(device)
            
            processor = AutoProcessor.from_pretrained(
                "microsoft/Florence-2-base", 
                trust_remote_code=True
            )
            
            print(f"✓ Model başarıyla yüklendi: {strategy['name']}")
            return model, processor, device, dtype
            
        except Exception as e:
            print(f"✗ {strategy['name']} başarısız: {str(e)[:100]}...")
            continue
    
    return None, None, None, None

def run_florence_task(model, processor, image, task_prompt, device, dtype, max_retries=2):
    """Run Florence-2 task with error handling"""
    for attempt in range(max_retries):
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            inputs = processor(text=task_prompt, images=image, return_tensors="pt")
            
            if device == "cuda":
                inputs = {k: v.to(device) if isinstance(v, torch.Tensor) else v 
                         for k, v in inputs.items()}
            
            with torch.no_grad():
                generated_ids = model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=128,
                    do_sample=False,
                    pad_token_id=processor.tokenizer.pad_token_id if hasattr(processor.tokenizer, 'pad_token_id') else None,
                    use_cache=False
                )
            
            generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            return generated_text
            
        except Exception as e:
            print(f"    Deneme {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
    
    return None

# Main execution
def main():
    # Find ExifTool
    exiftool_path = find_exiftool()
    if not exiftool_path or not test_exiftool(exiftool_path):
        print("HATA: ExifTool bulunamadı veya çalışmıyor!")
        return
    
    # Load model
    model, processor, device, dtype = load_florence_model()
    if model is None:
        print("HATA: Florence-2 modeli yüklenemedi!")
        print("\nÖnerilen çözümler:")
        print("1. pip install --upgrade transformers torch")
        print("2. pip install transformers==4.37.0 torch")
        print("3. Yeniden başlatın ve tekrar deneyin")
        return
    
    # Find folder
    folder_path = r"P:\Automatic Upload\Samsung SM-A528B"
    if not os.path.exists(folder_path):
        folder_path = os.getcwd()
        print(f"pCloud klasörü bulunamadı, mevcut klasör kullanılıyor: {folder_path}")
    
    # Process images
    extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp')
    image_files = [f for f in os.listdir(folder_path) if f.lower().endswith(extensions)]
    
    if not image_files:
        print(f"Resim dosyası bulunamadı: {folder_path}")
        return
    
    print(f"\n{len(image_files)} resim dosyası bulundu.")
    
    # No translation needed - keep everything in English
    
    successful = 0
    failed = 0
    
    for i, filename in enumerate(image_files, 1):
        print(f"\n[{i}/{len(image_files)}] {filename}")
        file_path = os.path.join(folder_path, filename)
        
        try:
            # Load image
            with Image.open(file_path) as img:
                img = img.convert('RGB')
                if max(img.size) > 1024:
                    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            
            all_tags = []
            
            # Generate caption and split into individual words
            print("  Caption üretiliyor...")
            caption_result = run_florence_task(
                model, processor, img, "<MORE_DETAILED_CAPTION>", device, dtype
            )
            
            if caption_result:
                caption = caption_result.replace("<MORE_DETAILED_CAPTION>", "").strip()
                if caption and len(caption) > 5:
                    # Split caption into individual words and clean them
                    import re
                    # Remove punctuation and split into words
                    words = re.findall(r'\b[a-zA-Z]+\b', caption.lower())
                    # Filter out very short words and common stop words
                    filtered_words = [word for word in words if len(word) > 2 and 
                                    word not in ['the', 'and', 'are', 'was', 'were', 'has', 'have', 
                                               'had', 'will', 'would', 'could', 'should', 'may', 'might',
                                               'can', 'this', 'that', 'with', 'from', 'they', 'them',
                                               'their', 'there', 'where', 'when', 'what', 'who', 'how',
                                               'but', 'for', 'not', 'you', 'your', 'his', 'her', 'him']]
                    all_tags.extend(filtered_words)
                    print(f"  Caption words: {', '.join(filtered_words[:10])}...")
            
            # Object detection - add detected objects
            print("  Nesne algılama...")
            detection_result = run_florence_task(
                model, processor, img, "<OD>", device, dtype
            )
            
            if detection_result:
                det_text = detection_result.replace("<OD>", "").strip()
                if det_text:
                    import re
                    # Remove location tags
                    cleaned_text = re.sub(r'<loc_\d+>', ' ', det_text)
                    # Extract object names
                    objects = [obj.strip().lower() for obj in cleaned_text.split() 
                              if obj.strip() and len(obj.strip()) > 2]
                    # Remove duplicates and add to tags
                    unique_objects = list(set(objects))
                    all_tags.extend(unique_objects)
                    if unique_objects:
                        print(f"  Detected objects: {', '.join(unique_objects)}")
            
            # Remove duplicates while preserving order
            final_tags = []
            seen = set()
            for tag in all_tags:
                if tag.lower() not in seen and len(tag) > 2:
                    final_tags.append(tag.lower())
                    seen.add(tag.lower())
            
            # Write metadata
            if final_tags:
                if write_metadata_with_subprocess(file_path, final_tags, exiftool_path):
                    print(f"  ✓ {len(final_tags)} tags written")
                    print(f"    Tags: {', '.join(final_tags[:15])}...")  # Show first 15 tags
                    successful += 1
                else:
                    print(f"  ✗ Metadata yazılamadı")
                    failed += 1
            else:
                print(f"  - No tags found")
                failed += 1
        
        except Exception as e:
            print(f"  ✗ Hata: {e}")
            failed += 1
        
        # Cleanup every 3 files
        if i % 3 == 0 and torch.cuda.is_available():
            torch.cuda.empty_cache()
    
    print(f"\n{'='*50}")
    print(f"İşlem tamamlandı!")
    print(f"Başarılı: {successful}, Başarısız: {failed}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()