import bpy
import sys
import os

# 경로 설정 (FBX가 입력, DAE가 출력)
fbx_path = "C:/git/XR-Studio/MyProjectCamera/Content/Scripts/ExportedFBX/wall.fbx"
dae_path = "C:/git/XR-Studio/MyProjectCamera/Content/Scripts/ExportedFBX/wall_converted.dae"

# 1. 새 씬으로 초기화 (빈 상태로 시작)
bpy.ops.wm.read_factory_settings(use_empty=True)

try:
    print(f"📂 Importing FBX: {fbx_path}")
    
    # [변경점 1] FBX 불러오기 함수 사용
    
    bpy.ops.import_scene.fbx(filepath=fbx_path)

    # 메시 오브젝트 찾기
    imported_objs = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    print(f"✅ Imported {len(imported_objs)} mesh objects.")

    if not imported_objs:
        raise RuntimeError("No mesh objects found in FBX.")

    # [선택 사항] 오브젝트 합치기 (기존 코드 로직 유지)
    # 여러 파츠로 나뉜 FBX를 하나의 DAE 메쉬로 만들고 싶을 때 유효합니다.
    bpy.ops.object.select_all(action='DESELECT')
    for obj in imported_objs:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj  # 하나를 active로 설정

    if len(imported_objs) > 1:
        bpy.ops.object.join()
        print("🔗 Objects joined into one mesh.")
    
    joined_obj = bpy.context.view_layer.objects.active
    joined_obj.name = "ConvertedMesh"

    print(f"💾 Exporting DAE (Collada) to: {dae_path}")

    # [변경점 2] Collada 내보내기 함수 사용
    # check_existing=False: 덮어쓰기 허용
    bpy.ops.wm.collada_export(
        filepath=dae_path, 
        check_existing=False, 
        selected=True  # 현재 선택된(합쳐진) 오브젝트만 내보내기
    )

    print("✅ DAE export completed successfully!")

except Exception as e:
    print("❌ Error:")
    print(e)