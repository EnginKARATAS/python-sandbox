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
    """Write metadata using subprocess - direct update without backup"""
    try:
        # Don't get existing tags since we already checked they don't exist
        # This function is only called for files without existing tags
        if not tags:
            return False
            
        tag_string = ','.join(tags)
        
        # Direct update without creating backup files
        cmd = [
            exiftool_path, 
            f'-XMP:Subject={tag_string}', 
            '-overwrite_original',  # This prevents (2).jpg files
            '-P',                   # Preserve file modification date
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return True
        else:
            print(f"    ExifTool hatası: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"    Metadata yazma hatası: {e}")
        return False

def load_florence_model():
    """Load Florence-2 model with GPU optimization"""
    # Check GPU availability and memory
    if torch.cuda.is_available():
        print(f"GPU bulundu: {torch.cuda.get_device_name(0)}")
        print(f"GPU bellek: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        
        # Choose device and dtype based on GPU memory
        if gpu_memory_gb >= 8:  # 8GB or more
            device = "cuda"
            dtype = torch.float16
            print("GPU modu: float16 (8GB+ GPU)")
        elif gpu_memory_gb >= 4:  # 4-8GB
            device = "cuda" 
            dtype = torch.float32
            print("GPU modu: float32 (4-8GB GPU)")
        else:  # Less than 4GB
            device = "cpu"
            dtype = torch.float32
            print("GPU yetersiz, CPU kullanılıyor")
    else:
        device = "cpu"
        dtype = torch.float32
        print("GPU bulunamadı, CPU kullanılıyor")
    
    print(f"Cihaz: {device}, Tip: {dtype}")
    print("Florence-2 modeli yükleniyor...")
    
    # Try different loading strategies optimized for GPU
    loading_strategies = [
        {
            "name": "Strategy 1: GPU Optimized with Flash Attention",
            "config": {
                "trust_remote_code": True,
                "torch_dtype": dtype,
                "device_map": device if device == "cuda" else None,
                "low_cpu_mem_usage": True,
            }
        },
        {
            "name": "Strategy 2: GPU with Eager Attention",
            "config": {
                "trust_remote_code": True,
                "torch_dtype": dtype,
                "attn_implementation": "eager",
                "device_map": device if device == "cuda" else None,
                "low_cpu_mem_usage": True,
            }
        },
        {
            "name": "Strategy 3: Manual GPU placement",
            "config": {
                "trust_remote_code": True,
                "torch_dtype": dtype,
                "attn_implementation": "eager",
                "device_map": None,
                "low_cpu_mem_usage": True,
            }
        },
        {
            "name": "Strategy 4: CPU Fallback",
            "config": {
                "trust_remote_code": True,
                "torch_dtype": torch.float32,
                "device_map": None,
            }
        }
    ]
    
    for strategy in loading_strategies:
        try:
            print(f"Deneniyor: {strategy['name']}")
            
            from transformers import AutoProcessor, AutoModelForCausalLM
            
            # Clear GPU cache before each attempt
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            # Load model
            model = AutoModelForCausalLM.from_pretrained(
                "microsoft/Florence-2-base",
                **strategy['config']
            )
            
            # Handle device placement
            current_device = device if device == "cuda" else "cpu"
            if strategy['config'].get('device_map') is None:
                print(f"  Manuel olarak {current_device}'ye taşınıyor...")
                model = model.to(current_device, dtype=dtype)
            
            # Load processor
            processor = AutoProcessor.from_pretrained(
                "microsoft/Florence-2-base", 
                trust_remote_code=True
            )
            
            # Test the model with a dummy input to ensure it works
            print(f"  Model test ediliyor...")
            dummy_image = Image.new('RGB', (224, 224), color='red')
            test_inputs = processor(text="<OD>", images=dummy_image, return_tensors="pt")
            
            if current_device == "cuda":
                test_inputs = {k: v.to(current_device) if isinstance(v, torch.Tensor) else v 
                             for k, v in test_inputs.items()}
            
            with torch.no_grad():
                _ = model.generate(
                    input_ids=test_inputs["input_ids"],
                    pixel_values=test_inputs["pixel_values"], 
                    max_new_tokens=10,
                    do_sample=False,
                    use_cache=False
                )
            
            print(f"✓ Model başarıyla yüklendi: {strategy['name']}")
            print(f"  Aktif cihaz: {next(model.parameters()).device}")
            return model, processor, current_device, dtype
            
        except Exception as e:
            print(f"✗ {strategy['name']} başarısız: {str(e)[:100]}...")
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            # Force CPU for last strategy
            if "CPU Fallback" in strategy['name']:
                current_device = "cpu"
                dtype = torch.float32
            continue
    
    return None, None, None, None

def run_florence_task(model, processor, image, task_prompt, device, dtype, max_retries=2):
    """Run Florence-2 task with GPU optimization"""
    for attempt in range(max_retries):
        try:
            # Clear GPU cache before each attempt
            if device == "cuda":
                torch.cuda.empty_cache()
            
            # Process inputs
            inputs = processor(text=task_prompt, images=image, return_tensors="pt")
            
            # Move inputs to device
            if device == "cuda":
                inputs = {k: v.to(device) if isinstance(v, torch.Tensor) else v 
                         for k, v in inputs.items()}
                
                # Ensure pixel_values are in correct dtype
                if 'pixel_values' in inputs:
                    inputs['pixel_values'] = inputs['pixel_values'].to(dtype)
            
            # Generate with optimized settings for GPU
            generation_config = {
                "input_ids": inputs["input_ids"],
                "pixel_values": inputs["pixel_values"],
                "max_new_tokens": 128 if device == "cuda" else 64,  # More tokens on GPU
                "do_sample": False,
                "use_cache": False,
                "pad_token_id": processor.tokenizer.pad_token_id if hasattr(processor.tokenizer, 'pad_token_id') else None,
            }
            
            # Add GPU-specific optimizations
            if device == "cuda":
                generation_config.update({
                    "num_beams": 1,  # Beam search can be memory intensive
                    "early_stopping": True,
                })
            
            with torch.no_grad():
                if device == "cuda":
                    with torch.cuda.amp.autocast(enabled=(dtype == torch.float16)):
                        generated_ids = model.generate(**generation_config)
                else:
                    generated_ids = model.generate(**generation_config)
            
            # Decode result
            generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            # Clear cache after successful generation
            if device == "cuda":
                torch.cuda.empty_cache()
                
            return generated_text
            
        except torch.cuda.OutOfMemoryError as e:
            print(f"    GPU bellek hatası (deneme {attempt + 1}/{max_retries}): Temizleniyor...")
            if device == "cuda":
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            if attempt < max_retries - 1:
                continue
            else:
                print("    GPU bellek sorunu, CPU'ya geçiş öneriliyor")
                return None
        except Exception as e:
            print(f"    Deneme {attempt + 1}/{max_retries}: {str(e)[:50]}...")
            if attempt < max_retries - 1 and device == "cuda":
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
            # Check if image already has tags - skip if it does
            existing_tags = get_existing_tags(file_path, exiftool_path)
            if existing_tags and len(existing_tags) > 0:
                print(f"  ⏭️  Zaten {len(existing_tags)} tag var, atlanıyor")
                print(f"      Mevcut taglar: {', '.join(existing_tags[:5])}...")
                successful += 1  # Count as successful since it's already tagged
                continue
            
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
                                               'but', 'for', 'not', 'you', 'your', 'his', 'her', 'him', 'close', 'shows', 'image']]
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
            
            # Write metadata (existing_tags will be empty since we checked above)
            if final_tags:
                if write_metadata_with_subprocess(file_path, final_tags, exiftool_path):
                    print(f"  ✓ {len(final_tags)} yeni tag yazıldı")
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
        
        # Cleanup every 3 files or immediately if GPU memory is low
        if i % 3 == 0 or (device == "cuda" and i % 2 == 0):
            if device == "cuda":
                torch.cuda.empty_cache()
                # Check GPU memory usage
                if torch.cuda.is_available():
                    memory_used = torch.cuda.memory_allocated() / 1024**3
                    memory_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                    print(f"    GPU bellek: {memory_used:.1f}/{memory_total:.1f} GB")
    
    print(f"\n{'='*50}")
    print(f"İşlem tamamlandı!")
    print(f"Başarılı: {successful}, Başarısız: {failed}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()