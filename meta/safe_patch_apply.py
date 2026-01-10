import re
from pathlib import Path
from typing import List, Tuple

PROTECTED_PREFIXES = (
    ".github/",
    "infra/",
    "secrets/",
    "trading/",
    "allocation/",
    "tools/",
    "auth/",
    "payment/",
)

class PatchError(Exception):
    pass

def parse_unified_diff(patch_text: str) -> List[Tuple[str, str]]:
    file_patches = []
    current_file = None
    current_content = []
    
    lines = patch_text.strip().split('\n')
    
    for line in lines:
        if line.startswith('--- '):
            if current_file and current_content:
                file_patches.append((current_file, '\n'.join(current_content)))
            current_content = [line]
            match = re.match(r'^--- a/(.+)$', line)
            if match:
                current_file = match.group(1)
            else:
                match = re.match(r'^--- (.+)$', line)
                if match:
                    current_file = match.group(1).lstrip('a/')
        elif current_file:
            current_content.append(line)
    
    if current_file and current_content:
        file_patches.append((current_file, '\n'.join(current_content)))
    
    return file_patches

def validate_path(file_path: str, allowed_root: str) -> None:
    normalized = file_path.replace('\\', '/')
    
    if '..' in normalized:
        raise PatchError(f"Path traversal detected: {file_path}")
    
    if not normalized.startswith(allowed_root):
        raise PatchError(f"File outside allowed root '{allowed_root}': {file_path}")
    
    for prefix in PROTECTED_PREFIXES:
        if normalized.startswith(prefix):
            raise PatchError(f"Protected path: {file_path}")

def count_changed_lines(patch_content: str) -> int:
    count = 0
    for line in patch_content.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            count += 1
        elif line.startswith('-') and not line.startswith('---'):
            count += 1
    return count

def apply_unified_diff(file_path: str, patch_content: str) -> None:
    path = Path(file_path)
    
    if not path.exists():
        raise PatchError(f"File does not exist: {file_path}")
    
    original_content = path.read_text()
    original_lines = original_content.split('\n')
    
    new_lines = []
    patch_lines = patch_content.split('\n')
    
    current_line = 0
    i = 0
    
    while i < len(patch_lines):
        line = patch_lines[i]
        
        if line.startswith('@@'):
            match = re.match(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            if match:
                old_start = int(match.group(1)) - 1
                
                while current_line < old_start:
                    if current_line < len(original_lines):
                        new_lines.append(original_lines[current_line])
                    current_line += 1
                
                i += 1
                continue
        
        if line.startswith('-') and not line.startswith('---'):
            current_line += 1
        elif line.startswith('+') and not line.startswith('+++'):
            new_lines.append(line[1:])
        elif line.startswith(' '):
            if current_line < len(original_lines):
                new_lines.append(original_lines[current_line])
            current_line += 1
        elif not line.startswith('---') and not line.startswith('+++'):
            pass
        
        i += 1
    
    while current_line < len(original_lines):
        new_lines.append(original_lines[current_line])
        current_line += 1
    
    path.write_text('\n'.join(new_lines))

def apply_patch(
    patch_text: str,
    max_files: int,
    max_lines: int,
    allowed_root: str = "agents/"
) -> None:
    if not patch_text or not patch_text.strip():
        raise PatchError("Empty patch")
    
    file_patches = parse_unified_diff(patch_text)
    
    if not file_patches:
        raise PatchError("No valid file patches found in diff")
    
    if len(file_patches) > max_files:
        raise PatchError(f"Too many files changed: {len(file_patches)} > {max_files}")
    
    total_lines = 0
    for file_path, patch_content in file_patches:
        validate_path(file_path, allowed_root)
        total_lines += count_changed_lines(patch_content)
    
    if total_lines > max_lines:
        raise PatchError(f"Too many lines changed: {total_lines} > {max_lines}")
    
    applied = []
    try:
        for file_path, patch_content in file_patches:
            apply_unified_diff(file_path, patch_content)
            applied.append(file_path)
    except Exception as e:
        raise PatchError(f"Patch application failed: {e}")
    
    return applied
