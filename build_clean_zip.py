import os
import zipfile
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def create_pipo_zip():
    root_dir = os.path.abspath("d:/AI/Restaurant")
    zip_path = os.path.join(root_dir, "Pipo.zip")

    # Xóa file zip cũ nếu có
    if os.path.exists(zip_path):
        os.remove(zip_path)

    # Danh sách các tệp và thư mục cốt lõi
    include_items = [
        "app",
        "Dockerfile",
        "Procfile",
        "requirements.txt",
        "run_server.py",
        "pipo_garden.db"
    ]

    print(f"[*] Dang tao file nén chuân: {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        added_arcs = set()
        for item in include_items:
            full_path = os.path.join(root_dir, item)
            if os.path.isfile(full_path):
                arcname = item.replace("\\", "/")
                if arcname not in added_arcs:
                    zf.write(full_path, arcname)
                    added_arcs.add(arcname)
                    print(f"  + [FILE] {arcname}")
            elif os.path.isdir(full_path):
                for root, dirs, files in os.walk(full_path):
                    # Loại bỏ hoàn toàn pycache và các thư mục rác
                    dirs[:] = [d for d in dirs if d not in ("__pycache__", "data", ".git", ".idea")]
                    for f in files:
                        if f.endswith((".pyc", ".pyo", ".git", ".DS_Store")):
                            continue
                        fp = os.path.join(root, f)
                        rel = os.path.relpath(fp, root_dir)
                        arcname = rel.replace("\\", "/")
                        if arcname not in added_arcs:
                            zf.write(fp, arcname)
                            added_arcs.add(arcname)

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"\n[OK] Đã tạo thành công Pipo.zip ({size_mb:.2f} MB) với {len(added_arcs)} tệp tin, 0 tệp trùng lặp!")

if __name__ == "__main__":
    create_pipo_zip()
