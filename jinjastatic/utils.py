import os

__all__ = [
    'is_updated',
]

def is_updated(old_file, new_file):
    return not os.path.exists(new_file) or \
        os.stat(old_file).st_mtime > os.stat(new_file).st_mtime
