import os
import sys
import datetime
import zipfile

def create_backup():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backup_dir = os.path.join(root_dir, 'backup')
    os.makedirs(backup_dir, exist_ok=True)

    now_str = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    zip_filename = f'backup_{now_str}.zip'
    zip_path = os.path.join(backup_dir, zip_filename)

    exclude_dirs = {'.git', 'backup', '__pycache__', 'venv', '.venv', 'scratch', '.idea', '.vscode'}
    exclude_exts = {'.zip', '.tar.gz', '.pyc'}

    file_count = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for cur_root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                if any(file.endswith(ext) for ext in exclude_exts):
                    continue
                full_path = os.path.join(cur_root, file)
                arcname = os.path.relpath(full_path, root_dir)
                zipf.write(full_path, arcname)
                file_count += 1

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"[BACKUP SUCCESS] File: backup/{zip_filename} ({size_mb:.2f} MB, {file_count} files)")
    return zip_path

if __name__ == '__main__':
    create_backup()
