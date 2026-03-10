#!/usr/bin/env python3
import os
import shutil
from pathlib import Path

def phase6_cleanup_and_output():
    """Phase 6: Copy final files to output and cleanup"""
    
    print("=== PHASE 6: OUTPUT AND CLEANUP ===")
    
    # Create output directory
    output_dir = Path('/mnt/c/seedJura/output')
    output_dir.mkdir(exist_ok=True)
    
    # Copy all final files to output
    phase4_dir = Path('/mnt/c/seedJura/contracts/phase4')
    phase5_dir = Path('/mnt/c/seedJura/contracts/phase5')
    files_copied = 0
    
    # Copy from phase4 (REDACTED files)
    for file_path in phase4_dir.glob('*_REDACTED.*'):
        dest_path = output_dir / file_path.name
        shutil.copy2(file_path, dest_path)
        files_copied += 1
        print(f"  Copied: {file_path.name}")
    
    # Copy from phase5 (FORMATTED files - both txt and pdf)
    for file_path in phase5_dir.glob('*_FORMATTED*'):
        dest_path = output_dir / file_path.name
        shutil.copy2(file_path, dest_path)
        files_copied += 1
        print(f"  Copied: {file_path.name}")
    
    print(f"Copied {files_copied} final files to output directory")
    
    # Clean up temporary files
    phase2_dir = Path('/mnt/c/seedJura/contracts/phase2')
    phase3_dir = Path('/mnt/c/seedJura/contracts/phase3')
    
    files_removed = 0
    
    # Clean phase2 chunks
    for file_path in phase2_dir.glob('page_*.txt'):
        file_path.unlink()
        files_removed += 1
    
    # Clean phase2 mappings
    for file_path in phase2_dir.glob('*_mapping.json'):
        file_path.unlink()
        files_removed += 1
    
    # Clean phase3 processed chunks
    for file_path in phase3_dir.glob('page_*.txt'):
        file_path.unlink()
        files_removed += 1
    
    # Clean phase3 mappings
    for file_path in phase3_dir.glob('*_mapping.json'):
        file_path.unlink()
        files_removed += 1
    
    print(f"Cleaned up {files_removed} temporary files")
    print(f"Phase 6 complete - final files available in: C:\\seedJura\\output")

if __name__ == "__main__":
    phase6_cleanup_and_output()
