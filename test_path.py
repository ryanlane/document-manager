import os
import sys

file_path = "/home/ryan/projects/document-manager/backend/src/api/main.py"
abspath = os.path.abspath(file_path)
print(f"abspath: {abspath}")
dir1 = os.path.dirname(abspath)
dir2 = os.path.dirname(dir1)
dir3 = os.path.dirname(dir2)
print(f"dir3: {dir3}")
shared = os.path.join(dir3, "shared")
print(f"shared: {shared}")
print(f"exists: {os.path.exists(shared)}")
