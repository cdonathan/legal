#!/usr/bin/env python3
import subprocess
import time
import sys
from datetime import datetime

def run_with_logging():
    """Run batch process with detailed logging and timing"""
    
    # Create log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"/mnt/c/seedJura/batch_process_log_{timestamp}.txt"
    
    print(f"Starting batch process with logging to: {log_file}")
    
    # Start timing
    start_time = time.time()
    start_datetime = datetime.now()
    
    # Prepare log content
    log_content = []
    log_content.append(f"=== BATCH PROCESS LOG ===")
    log_content.append(f"Start time: {start_datetime}")
    log_content.append(f"Model: phi3.5")
    log_content.append(f"Command: python3 batch_process.py /mnt/c/seedJura/contracts")
    log_content.append("=" * 50)
    log_content.append("")
    
    try:
        # Run the batch process and capture output
        print("Running batch process...")
        result = subprocess.run(
            ['python3', 'batch_process.py', '/mnt/c/seedJura/contracts'],
            cwd='/home/cliff/redact',
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        # Calculate timing
        end_time = time.time()
        end_datetime = datetime.now()
        total_time = end_time - start_time
        
        # Add output to log
        log_content.append("STDOUT:")
        log_content.append(result.stdout)
        log_content.append("")
        
        if result.stderr:
            log_content.append("STDERR:")
            log_content.append(result.stderr)
            log_content.append("")
        
        # Add timing info
        log_content.append("=" * 50)
        log_content.append(f"End time: {end_datetime}")
        log_content.append(f"Total runtime: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
        log_content.append(f"Exit code: {result.returncode}")
        
        # Write log file
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_content))
        
        print(f"\nBatch process completed!")
        print(f"Runtime: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
        print(f"Exit code: {result.returncode}")
        print(f"Log saved to: {log_file}")
        
        # Also print the output
        print("\nProcess output:")
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
            
    except subprocess.TimeoutExpired:
        end_time = time.time()
        total_time = end_time - start_time
        
        log_content.append("PROCESS TIMED OUT AFTER 1 HOUR")
        log_content.append(f"Runtime before timeout: {total_time:.2f} seconds")
        
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_content))
        
        print(f"Process timed out after {total_time:.2f} seconds")
        print(f"Log saved to: {log_file}")
        
    except Exception as e:
        end_time = time.time()
        total_time = end_time - start_time
        
        log_content.append(f"ERROR: {str(e)}")
        log_content.append(f"Runtime before error: {total_time:.2f} seconds")
        
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_content))
        
        print(f"Error occurred: {e}")
        print(f"Log saved to: {log_file}")

if __name__ == "__main__":
    run_with_logging()
