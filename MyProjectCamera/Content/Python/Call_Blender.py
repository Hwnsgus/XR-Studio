# Call_Blender.py
import subprocess
import os

# ✅ 방법 1: raw string
blender_path = r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
script_path = r"D:\git\XR-Studio\MyProjectCamera\Content\Python\convert_dae_to_fbx.py"

subprocess.run([
    blender_path,
    "--background",
    "--python", script_path
], shell=True)
