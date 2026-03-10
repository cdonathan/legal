#!/usr/bin/env python3

def simulate_learn_then_apply():
    """Simulate the learn-then-apply approach based on actual data"""
    
    print("=== LEARN-THEN-APPLY SIMULATION ===")
    print("Based on actual Exhibit.mhtml analysis:")
    print()
    
    # From the actual log output, these are the flagged words per page:
    flagged_words_by_page = {
        2: ["Tupperware", "Declarant", "TBC"],
        3: ["Greenberg", "Tupperware", "Traurig"], 
        12: ["Tupperware", "TBC", "Osceola"],
        15: ["Greenberg", "Traurig", "Fidelity"],
        18: ["Centerview", "SDP", "Greenwald", "Osceola"],
        23: ["Blossom", "Tupperware", "Osceola", "Gatorland"],
        27: ["Ivey", "Tupperware", "Osceola", "Wickes", "SFWMD", "Lowe"],
        28: ["Greenberg", "Sheppard", "Traurig", "Roehlk", "Deerfield"],
        45: ["DEERFIELD", "CONNOR", "Tupperware", "Roehlk", "Sheehan", "DART", "TUPPERWARE", "Connor"],
        46: ["DEERFIELD", "CONNOR", "tupperware", "Tupperware", "Osceola", "OSCEOLA", "TUPPERWARE"],
        47: ["DEERFIELD", "CONNOR", "Rapallo", "Brightview", "Blossom", "Terre", "SSN", "Deerfield", "Kissimmee", "OSCEOLA", "Trailside", "Cinque", "Crosslands"],
        48: ["SSN", "Lakeside", "Toho", "Centerview", "Greenwald", "SBA", "TOD", "Cinque", "Crosslands", "DEERFIELD", "Rapallo", "Terre", "Solitude", "Venezia", "Miranda", "Parkway", "CONNOR", "TBCOM", "Mgmt", "Osceola"]
    }
    
    # Track first occurrences
    seen_words = set()
    first_occurrence_pages = []
    pattern_match_pages = []
    
    for page_num in sorted(flagged_words_by_page.keys()):
        words = flagged_words_by_page[page_num]
        has_new_words = False
        
        for word in words:
            word_lower = word.lower()
            if word_lower not in seen_words:
                has_new_words = True
                seen_words.add(word_lower)
        
        if has_new_words:
            first_occurrence_pages.append(page_num)
        else:
            pattern_match_pages.append(page_num)
    
    print(f"Current approach:")
    print(f"  Pages sent to AI: {len(flagged_words_by_page)} pages")
    print(f"  Time: 7.35 minutes (actual measurement)")
    print(f"  AI time per page: {7.35/len(flagged_words_by_page):.2f} minutes")
    print()
    
    print(f"Learn-then-apply approach:")
    print(f"  First occurrence pages (AI): {first_occurrence_pages}")
    print(f"  Pattern match pages: {pattern_match_pages}")
    print(f"  Pages sent to AI: {len(first_occurrence_pages)} pages")
    print(f"  Pages pattern matched: {len(pattern_match_pages)} pages")
    print()
    
    # Calculate time savings
    ai_time_per_page = 7.35 / len(flagged_words_by_page)  # minutes per page
    pattern_time_per_page = 0.01  # 0.6 seconds per page for pattern matching
    
    new_ai_time = len(first_occurrence_pages) * ai_time_per_page
    pattern_time = len(pattern_match_pages) * pattern_time_per_page
    total_new_time = new_ai_time + pattern_time
    
    print(f"Time calculation:")
    print(f"  AI time: {len(first_occurrence_pages)} pages × {ai_time_per_page:.2f} min = {new_ai_time:.2f} minutes")
    print(f"  Pattern time: {len(pattern_match_pages)} pages × {pattern_time_per_page:.2f} min = {pattern_time:.2f} minutes")
    print(f"  Total time: {total_new_time:.2f} minutes")
    print()
    
    speedup = 7.35 / total_new_time
    ai_reduction = (len(flagged_words_by_page) - len(first_occurrence_pages)) / len(flagged_words_by_page) * 100
    
    print(f"Improvement:")
    print(f"  Speedup: {speedup:.2f}x faster")
    print(f"  Time saved: {7.35 - total_new_time:.2f} minutes")
    print(f"  AI reduction: {ai_reduction:.1f}% fewer AI calls")
    
    # Show which words would be learned
    print(f"\nLearned PII terms ({len(seen_words)} total):")
    word_list = sorted(list(seen_words))
    for i in range(0, len(word_list), 8):
        print(f"  {', '.join(word_list[i:i+8])}")
    
    # Save results
    with open('/mnt/c/seedJura/approach_simulation.txt', 'w') as f:
        f.write("LEARN-THEN-APPLY SIMULATION RESULTS\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Document: Exhibit.mhtml (49 pages, 14 flagged)\n\n")
        f.write(f"Current Approach:\n")
        f.write(f"  Pages sent to AI: {len(flagged_words_by_page)}\n")
        f.write(f"  Time: 7.35 minutes\n\n")
        f.write(f"Learn-then-Apply Approach:\n")
        f.write(f"  First occurrence pages: {first_occurrence_pages}\n")
        f.write(f"  Pattern match pages: {pattern_match_pages}\n")
        f.write(f"  Pages sent to AI: {len(first_occurrence_pages)}\n")
        f.write(f"  Pages pattern matched: {len(pattern_match_pages)}\n")
        f.write(f"  Total time: {total_new_time:.2f} minutes\n\n")
        f.write(f"Improvement:\n")
        f.write(f"  Speedup: {speedup:.2f}x faster\n")
        f.write(f"  Time saved: {7.35 - total_new_time:.2f} minutes\n")
        f.write(f"  AI reduction: {ai_reduction:.1f}% fewer AI calls\n\n")
        f.write(f"Learned PII terms: {', '.join(sorted(seen_words))}\n")
    
    print(f"\nResults saved to: C:\\seedJura\\approach_simulation.txt")

if __name__ == "__main__":
    simulate_learn_then_apply()
