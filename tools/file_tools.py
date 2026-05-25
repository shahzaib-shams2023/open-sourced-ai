from pathlib import Path

def read_file(path):

    return Path(path).read_text()

def write_file(path, content):

    Path(path).write_text(content)

    return f"Written to {path}"

def append_file(path, content):

    with open(path, "a") as f:
        f.write(content)

    return f"Appended to {path}"
