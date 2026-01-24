"""
Script to download Mistral-7B-Instruct-v0.3 model from Hugging Face
"""

from huggingface_hub import snapshot_download
from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def download_mistral_model():
    """Download Mistral-7B-Instruct-v0.3 model files"""
    
    # Set model path in user's home directory
    mistral_models_path = Path.home().joinpath('mistral_models', '7B-Instruct-v0.3')
    mistral_models_path.mkdir(parents=True, exist_ok=True)
    
    print(f"📥 Downloading Mistral-7B-Instruct-v0.3 to: {mistral_models_path}")
    print("This may take a while depending on your internet connection...")
    
    try:
        # Download full model for transformers compatibility
        # This includes config.json, tokenizer files, and model weights
        logger.info("Downloading full model (this includes config.json and all required files)...")
        snapshot_download(
            repo_id="mistralai/Mistral-7B-Instruct-v0.3",
            local_dir=mistral_models_path,
            ignore_patterns=["*.md", "*.txt"]  # Skip documentation files
        )
        
        print(f"✅ Model downloaded successfully to: {mistral_models_path}")
        print(f"\nModel files:")
        for file in mistral_models_path.rglob("*"):
            if file.is_file():
                size_mb = file.stat().st_size / (1024 * 1024)
                print(f"  - {file.name}: {size_mb:.2f} MB")
        
        return str(mistral_models_path)
        
    except Exception as e:
        print(f"❌ Error downloading model: {e}")
        raise


if __name__ == "__main__":
    download_mistral_model()


