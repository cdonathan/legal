#!/usr/bin/env python3
"""
Batch Test All 5 Samples - Sequential Processing
"""

import subprocess
import time
import os

def run_sample_test(sample_name, sample_path):
    """Run test on a single sample and capture results"""
    print(f"\n{'='*60}")
    print(f"🔄 TESTING {sample_name}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        # Run the smart attorney system
        result = subprocess.run([
            'python3', 
            '/home/cliff/redact/redline_project/code/smart_attorney_system.py',
            sample_path
        ], capture_output=True, text=True, cwd='/home/cliff/redact/redline_project/code')
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(result.stdout)
        if result.stderr:
            print(f"STDERR: {result.stderr}")
        
        print(f"\n⏱️ {sample_name} TOTAL TIME: {total_time:.2f} seconds")
        print(f"✅ {sample_name} COMPLETED")
        
        return {
            'sample': sample_name,
            'total_time': total_time,
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
        
    except Exception as e:
        print(f"❌ {sample_name} FAILED: {e}")
        return {
            'sample': sample_name,
            'total_time': 0,
            'success': False,
            'error': str(e)
        }

def main():
    """Test all 5 samples sequentially"""
    
    samples = [
        ("SAMPLE 1", "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Conf_Agr_Sample1-pre-redline.docx"),
        ("SAMPLE 2", "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE_Confidentiality Agreement_Sample_2_pre_redline.docx"),
        ("SAMPLE 3", "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE - NDA -  Sample3_pre_redline.docx"),
        ("SAMPLE 4", "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE - NDA_Sample_4_pre_redline.docx"),
        ("SAMPLE 6", "/home/cliff/redact/OneDrive_1_3-5-2026/REDLINE - NDA_Sample_6_pre_redline.docx")
    ]
    
    print("🚀 STARTING BATCH TEST OF ALL 5 SAMPLES")
    print(f"📅 Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    batch_start = time.time()
    results = []
    
    for sample_name, sample_path in samples:
        # Check if file exists
        if not os.path.exists(sample_path):
            print(f"❌ {sample_name} FILE NOT FOUND: {sample_path}")
            results.append({
                'sample': sample_name,
                'total_time': 0,
                'success': False,
                'error': 'File not found'
            })
            continue
        
        result = run_sample_test(sample_name, sample_path)
        results.append(result)
        
        # Brief pause between samples
        time.sleep(2)
    
    batch_end = time.time()
    batch_total = batch_end - batch_start
    
    # Summary Report
    print(f"\n{'='*60}")
    print("📊 BATCH TEST SUMMARY REPORT")
    print(f"{'='*60}")
    print(f"📅 Completed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️ Total Batch Time: {batch_total:.2f} seconds")
    print(f"📈 Average Time per NDA: {batch_total/len(samples):.2f} seconds")
    
    successful = sum(1 for r in results if r['success'])
    print(f"✅ Successful: {successful}/{len(samples)}")
    print(f"❌ Failed: {len(samples) - successful}/{len(samples)}")
    
    print(f"\n📋 INDIVIDUAL RESULTS:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        time_str = f"{result['total_time']:.2f}s" if result['total_time'] > 0 else "N/A"
        print(f"{status} {result['sample']}: {time_str}")
    
    # API timing analysis
    api_times = []
    for result in results:
        if result['success'] and 'API call duration:' in result['stdout']:
            try:
                # Extract API time from stdout
                lines = result['stdout'].split('\n')
                for line in lines:
                    if 'API call duration:' in line:
                        api_time = float(line.split('API call duration: ')[1].split(' seconds')[0])
                        api_times.append(api_time)
                        break
            except:
                pass
    
    if api_times:
        avg_api_time = sum(api_times) / len(api_times)
        print(f"\n🤖 OPENAI API ANALYSIS:")
        print(f"📊 API calls completed: {len(api_times)}")
        print(f"⏱️ Average API time: {avg_api_time:.2f} seconds")
        print(f"⚡ Fastest API call: {min(api_times):.2f} seconds")
        print(f"🐌 Slowest API call: {max(api_times):.2f} seconds")
    
    print(f"\n🎯 BATCH TEST COMPLETE!")

if __name__ == "__main__":
    main()
