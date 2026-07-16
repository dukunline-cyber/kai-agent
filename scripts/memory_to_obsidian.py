#!/usr/bin/env python3
"""Convert Kai memory.json to Obsidian vault format with graph links."""

import json
import os
import re
from pathlib import Path
from datetime import datetime

MEMORY_PATH = Path.home() / "ai-agent/data/memory.json"
VAULT_PATH = Path.home() / "ai-agent/obsidian_vault/kai_memory"

def sanitize_filename(text):
    """Convert text to safe filename."""
    return re.sub(r'[^\w\s-]', '', text).strip().replace(' ', '_')[:50]

def extract_links(text, all_keys):
    """Find mentions of other keys and create [[wikilinks]]."""
    if not isinstance(text, str):
        return text
    
    for key in all_keys:
        # Case-insensitive match for key mentions
        pattern = r'\b' + re.escape(key.replace('_', ' ')) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            text = re.sub(pattern, f'[[{sanitize_filename(key)}]]', text, flags=re.IGNORECASE)
    
    return text

def format_value(value, all_keys, indent=0):
    """Format value as markdown with links."""
    if isinstance(value, str):
        return extract_links(value, all_keys)
    elif isinstance(value, list):
        items = []
        for item in value:
            if isinstance(item, str):
                items.append(f"- {extract_links(item, all_keys)}")
            elif isinstance(item, dict):
                items.append(format_dict(item, all_keys, indent + 1))
            else:
                items.append(f"- {item}")
        return "\n".join(items)
    elif isinstance(value, dict):
        return format_dict(value, all_keys, indent + 1)
    else:
        return str(value)

def format_dict(d, all_keys, indent=0):
    """Format dict as markdown."""
    lines = []
    for k, v in d.items():
        formatted = format_value(v, all_keys, indent)
        if isinstance(v, list) or isinstance(v, dict):
            lines.append(f"**{k}:**\n{formatted}")
        else:
            lines.append(f"**{k}:** {formatted}")
    return "\n\n".join(lines)

def main():
    print("Loading memory.json...")
    with open(MEMORY_PATH) as f:
        memory = json.load(f)
    
    all_keys = list(memory.keys())
    
    # Clear existing vault
    for f in VAULT_PATH.glob("*.md"):
        f.unlink()
    
    print(f"Converting {len(all_keys)} memory entries to Obsidian format...")
    
    # Create index file
    index_content = f"# Kai Memory Graph\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n## All Nodes\n\n"
    for key in sorted(all_keys):
        index_content += f"- [[{sanitize_filename(key)}]]\n"
    
    (VAULT_PATH / "_index.md").write_text(index_content)
    print(f"Created _index.md")
    
    # Create node files
    for key, value in memory.items():
        filename = sanitize_filename(key) + ".md"
        filepath = VAULT_PATH / filename
        
        content = f"# {key}\n\n"
        content += format_value(value, all_keys)
        content += f"\n\n---\n*Source: memory.json key `{key}`*"
        
        filepath.write_text(content)
        print(f"Created {filename}")
    
    print(f"\nDone! Open in Obsidian: {VAULT_PATH}")
    print(f"Total files: {len(list(VAULT_PATH.glob('*.md')))}")

if __name__ == "__main__":
    main()
