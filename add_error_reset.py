#!/usr/bin/env python3
"""
Add error reset mechanism to code_guardian_agent.py
"""
import re

file_path = 'agents/code_guardian_agent.py'

with open(file_path, 'r') as f:
    content = f.read()

# Check if import already exists
if 'from services.startup_failure_tracker import clear_startup_failures' not in content:
    # Find the first import line and add our import after other local imports
    lines = content.split('\n')
    import_added = False
    for i, line in enumerate(lines):
        if line.startswith('from services.') and not import_added:
            # Add after this line
            lines.insert(i + 1, 'from services.startup_failure_tracker import clear_startup_failures')
            import_added = True
            break
        elif line.startswith('from ') and i > 5 and not import_added:
            # Add after first relative import
            if '.' in line or 'services' in line:
                lines.insert(i + 1, 'from services.startup_failure_tracker import clear_startup_failures')
                import_added = True
                break
    
    content = '\n'.join(lines)

# Find the analyze method and add clear_startup_failures() after f.write() calls
# Pattern: find "f.write(fixed_code)" and add clear_startup_failures after the write
pattern = r'(\s+f\.write\(fixed_code\))'
replacement = r'\1\n\n                # Reset error counters for this agent after successful fix\n                clear_startup_failures(agent_name)'

content = re.sub(pattern, replacement, content)

with open(file_path, 'w') as f:
    f.write(content)

print("✅ Successfully added error reset mechanism to code_guardian_agent.py")
print("   - Added import: from services.startup_failure_tracker import clear_startup_failures")
print("   - Added clear_startup_failures(agent_name) after code fixes")
