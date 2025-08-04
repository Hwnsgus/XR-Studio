import bpy
import sys
import os

# 로그 저장
log_path = "D:/UnrealProject/MyProjectCamera/Content/Python/fbx_convert_log.txt"
sys.stdout = open(log_path, 'w')
sys.stderr = sys.stdout

dae_path = "D:/UnrealProject/MyProjectCamera/Content/Scripts/ExportedFBX/house.dae"
fbx_path = "D:/UnrealProject/MyProjectCamera/Content/Scripts/ExportedFBX/house.fbx"

# 새 씬으로 초기화
bpy.ops.wm.read_factory_settings(use_empty=True)

try:
    print(f"📂 Importing DAE: {dae_path}")
    bpy.ops.wm.collada_import(filepath=dae_path)

    # 메시 오브젝트 찾기
    imported_objs = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    print(f"✅ Imported {len(imported_objs)} mesh objects.")

    if not imported_objs:
        raise RuntimeError("No mesh objects found.")

    # 전부 선택해서 하나로 합치기
    bpy.ops.object.select_all(action='DESELECT')
    for obj in imported_objs:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj  # 하나를 active로 만들어야 join 가능

    bpy.ops.object.join()
    joined_obj = bpy.context.view_layer.objects.active
    joined_obj.name = "JoinedWall"

    print(f"💾 Exporting FBX to: {fbx_path}")
    bpy.ops.export_scene.fbx(filepath=fbx_path, use_selection=True)

    print("✅ FBX export completed successfully!")

except Exception as e:
    print("❌ Error:")
    print(e)
