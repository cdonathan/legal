#!/usr/bin/env python3
import re

# Read the counties file and process
with open('/mnt/c/seedJura/Counties.txt', 'r') as f:
    lines = f.readlines()

county_entries = []

# State mapping based on known patterns and order in file
current_state = None
state_patterns = {
    'county': 'standard',
    'borough': 'alaska', 
    'census area': 'alaska',
    'municipality': 'alaska',
    'city and borough': 'alaska',
    'parish': 'louisiana'
}

# Process each line
for line in lines[1:]:  # Skip header
    line = line.strip()
    if ':' in line:
        county_name = line.split(':')[0].strip()
        county_lower = county_name.lower()
        
        # Determine state based on position and patterns
        # This is a simplified approach - we'll add the county name as-is
        # and let the user specify state context when needed
        
        county_entries.append(county_lower)

# Write to whitelist addition file
with open('/home/cliff/redact/county_additions.txt', 'w') as f:
    f.write("# US Counties, Boroughs, Parishes, and Census Areas\n")
    f.write("# Generated from Counties.txt - county names only\n")
    for entry in sorted(set(county_entries)):
        f.write(entry + "\n")

print(f"Generated {len(set(county_entries))} county entries")
print("Sample entries:")
for entry in sorted(set(county_entries))[:10]:
    print(f"  {entry}")

# Now append to main whitelist
with open('/home/cliff/redact/redaction_whitelist.txt', 'a') as f:
    f.write("\n# US Counties, Boroughs, Parishes (generated)\n")
    for entry in sorted(set(county_entries)):
        f.write(entry + "\n")

print(f"\nAdded {len(set(county_entries))} entries to redaction_whitelist.txt")
