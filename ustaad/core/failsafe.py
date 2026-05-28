"""
USTAAD Failsafe Parser & Materializer — v1.2

Automatically parses and writes files from agent text outputs if the agent
fails to invoke the write_file/patch_file tools natively (e.g. due to Ollama/LiteLLM tool-calling limits).
"""

import os
import re
from pathlib import Path
from rich.console import Console

console = Console()


def extract_and_materialize_files(text: str, workspace: str) -> list[str]:
    """
    Parses files from LLM output when the agent fails to invoke the tool natively.
    Returns a list of successfully written absolute file paths.
    """
    if not text:
        return []

    # Clean the text from carriage returns
    text = text.replace('\r\n', '\n')

    # Whitelist of common programming extensions to prevent false positive files
    ALLOWED_EXTENSIONS = {
        '.html', '.htm', '.css', '.js', '.jsx', '.ts', '.tsx', 
        '.py', '.json', '.yaml', '.yml', '.md', '.sh', '.bat', 
        '.ps1', '.txt', '.c', '.cpp', '.h', '.cs', '.go', '.rs', 
        '.java', '.kt', '.rb', '.php', '.svg'
    }

    # 1. Find all file path declarations in the text
    # Matches patterns like:
    # - "CREATING: E:\work\New folder (3)\index.html"
    # - "1. E:\work\New folder (3)\index.html"
    # - "File: styles.css"
    path_patterns = [
        r'(?:CREATING|MODIFYING|WRITING|File|Path|FILE|PATH|Create|Modify|Write):\s*\*?`?([a-zA-Z]:\\[^\n`*]+|[\w\-./\\]+\.[\w]+)`?\*?',
        r'(?:\d+\.\s+)\*?`?([a-zA-Z]:\\[^\n`*]+|[\w\-./\\]+\.[\w]+)`?\*?'
    ]
    
    declared_paths = []
    for pattern in path_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            m_clean = m.strip().strip("'\"`* ")
            ext = Path(m_clean).suffix.lower()
            if ext in ALLOWED_EXTENSIONS:
                # Check for false positives like digits in basename (e.g., 1.2em)
                basename = os.path.basename(m_clean)
                if re.match(r'^\d', basename) and ext not in ('.js', '.ts', '.py'):
                    continue
                # Convert to absolute path if relative
                if not os.path.isabs(m_clean):
                    abs_path = os.path.abspath(os.path.join(workspace, m_clean))
                else:
                    abs_path = os.path.abspath(m_clean)
                
                if abs_path not in declared_paths:
                    declared_paths.append(abs_path)

    # 2. Parse code blocks using a robust self-correcting line-by-line parser
    lines = text.split('\n')
    parsed_blocks = []
    inside_block = False
    current_block_content = []
    current_block_lang = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if inside_block:
                if stripped == "```":
                    # Correctly encountered a closing fence
                    content = "\n".join(current_block_content)
                    parsed_blocks.append((current_block_lang, content))
                    inside_block = False
                    current_block_content = []
                    current_block_lang = ""
                else:
                    # Encountered another opening fence (e.g. ```css) inside a block.
                    # The previous block was never closed! Auto-close it and start the new one.
                    content = "\n".join(current_block_content)
                    parsed_blocks.append((current_block_lang, content))
                    
                    current_block_lang = stripped[3:].strip()
                    current_block_content = []
                    inside_block = True
            else:
                # Start a new block
                inside_block = True
                current_block_lang = stripped[3:].strip()
                current_block_content = []
        else:
            if inside_block:
                current_block_content.append(line)

    # Handle the trailing block if LLM output was cut off before closing the fence
    if inside_block and current_block_content:
        content = "\n".join(current_block_content)
        parsed_blocks.append((current_block_lang, content))

    # 3. Filter the code blocks to ignore empty or meta list-of-paths blocks
    filtered_blocks = []
    for lang, content in parsed_blocks:
        content_stripped = content.strip()
        if not content_stripped or len(content_stripped) <= 10:
            continue
            
        # Ignore blocks that just list file creations/modifications
        lines = content_stripped.split('\n')
        if len(lines) <= 10 and all(
            re.search(r'(?:CREATING|MODIFYING|WRITING|File|Path|FILE|PATH):', line, re.I) or not line.strip() 
            for line in lines
        ):
            continue
            
        filtered_blocks.append((lang, content))

    written_files = []

    # Strategy A: Precise matching by order
    # If the count of declared paths matches the count of code blocks exactly
    if len(declared_paths) == len(filtered_blocks) and len(filtered_blocks) > 0:
        for path, (lang, content) in zip(declared_paths, filtered_blocks):
            if os.path.basename(path).lower() in ('ustaad_output.md', 'prompt_telemetry.json'):
                continue
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                console.print(f"[bold green]   + [FAILSAFE] Materialized file: {path}[/bold green]")
                written_files.append(path)
            except Exception as e:
                console.print(f"[red]   - [FAILSAFE] Failed to write {path}: {e}[/red]")
        return written_files

    # Strategy B: Contextual Heuristic Matching
    # (Preceding context heuristics remain active as a robust fallback)
    # Since we don't have block start indices directly in a line-by-line loop, 
    # we can rebuild block positions or simply fall back to parsing the text.
    # To be extremely clean, we can find block occurrences by simple index matching or exact text match.
    for lang, content in filtered_blocks:
        # Find position of this block's content in the original text
        pos = text.find(content)
        if pos == -1:
            continue
            
        search_start = max(0, pos - 1000)
        preceding_text = text[search_start:pos]
        
        path_candidates = re.findall(r'(?:[a-zA-Z]:\\[^\s`*]+|[\w\-./\\]+\.[\w]+)', preceding_text)
        
        if path_candidates:
            filtered_candidates = []
            for c in path_candidates:
                c_clean = c.strip().strip("'\"`* ")
                ext = Path(c_clean).suffix.lower()
                if ext in ALLOWED_EXTENSIONS:
                    basename = os.path.basename(c_clean)
                    if re.match(r'^\d', basename) and ext not in ('.js', '.ts', '.py'):
                        continue
                    if c_clean.lower() not in (
                        'write_file', 'patch_file', 'read_file', 'append_file',
                        'delete_file', 'ustaad_output.md', 'prompt_telemetry.json'
                    ):
                        filtered_candidates.append(c_clean)
            
            if not filtered_candidates:
                continue
                
            candidate = filtered_candidates[-1]
            
            if not os.path.isabs(candidate):
                path = os.path.abspath(os.path.join(workspace, candidate))
            else:
                path = os.path.abspath(candidate)
                
            if os.path.basename(path).lower() in ('ustaad_output.md', 'prompt_telemetry.json'):
                continue
                
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                console.print(f"[bold green]   + [FAILSAFE] Materialized file (heuristic): {path}[/bold green]")
                if path not in written_files:
                    written_files.append(path)
            except Exception as e:
                console.print(f"[red]   - [FAILSAFE] Failed to write {path}: {e}[/red]")
                
    return written_files
