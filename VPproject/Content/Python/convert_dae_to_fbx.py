import bpy
import sys
import os

# 파일 경로 입력
script_dir = os.path.dirname(os.path.abspath(__file__))
dae_path = os.path.join(script_dir,"D:/UnrealProject/MyProjectCamera/Content/Scripts/ExportedFBX/house.dae")
fbx_path = os.path.join(script_dir,"D:/UnrealProject/MyProjectCamera/Content/Scripts/ExportedFBX/house.fbx")


# Blender 초기화 (기본 설정, 빈 씬)
bpy.ops.wm.read_factory_settings(use_empty=True)

# COLLADA (.dae) 가져오기 및 FBX로 내보내기
try:
    print(f"📂 Importing DAE: {dae_path}")
    bpy.ops.wm.collada_import(filepath=dae_path)

    print(f"💾 Exporting FBX to: {fbx_path}")
    bpy.ops.export_scene.fbx(filepath=fbx_path, use_selection=False)

    print("✅ FBX export completed successfully!")

except Exception as e:
    print("❌ Error during DAE to FBX conversion:")
    print(e)