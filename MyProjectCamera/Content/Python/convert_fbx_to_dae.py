import bpy
import sys
import os

# ==========================================
# 설정 (경로 확인 필수)
# ==========================================
fbx_path = "C:/git/XR-Studio/MyProjectCamera/Content/Scripts/ExportedFBX/wall.fbx"
dae_path = "C:/git/XR-Studio/MyProjectCamera/Content/Scripts/ExportedFBX/wall_converted.dae"

def sanitize_uvs(objects):
    """
    모든 오브젝트의 첫 번째 UV 맵 이름을 'UVMap'으로 통일합니다.
    이렇게 해야 join() 할 때 UV 레이어가 수십 개로 늘어나는 것을 방지할 수 있습니다.
    """
    print("🔧 Sanitizing UV Maps...")
    for obj in objects:
        if obj.type == 'MESH' and obj.data.uv_layers:
            # 첫 번째 UV 레이어 이름을 강제로 변경
            obj.data.uv_layers[0].name = "UVMap"
            # 만약 2개 이상이라면 나머지는 삭제 (선택 사항, 에러 방지용)
            while len(obj.data.uv_layers) > 1:
                obj.data.uv_layers.remove(obj.data.uv_layers[-1])

# ==========================================
# 실행 로직
# ==========================================
# 1. 초기화
bpy.ops.wm.read_factory_settings(use_empty=True)

try:
    print(f"📂 Importing FBX: {fbx_path}")
    if not os.path.exists(fbx_path):
        raise FileNotFoundError(f"File not found: {fbx_path}")

    # FBX 불러오기
    bpy.ops.import_scene.fbx(filepath=fbx_path)

    # 메시 오브젝트 찾기
    imported_objs = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    print(f"✅ Imported {len(imported_objs)} mesh objects.")

    if not imported_objs:
        raise RuntimeError("No mesh objects found.")

    # 2. [중요] UV 이름 통일 (에러 방지)
    sanitize_uvs(imported_objs)

    # 3. 오브젝트 하나로 합치기
    bpy.ops.object.select_all(action='DESELECT')
    for obj in imported_objs:
        obj.select_set(True)
    
    # 활성 오브젝트 설정 (기준점)
    bpy.context.view_layer.objects.active = imported_objs[0]

    if len(imported_objs) > 1:
        print("🔗 Joining objects...")
        bpy.ops.object.join()
    
    # 4. DAE 내보내기
    print(f"💾 Exporting DAE to: {dae_path}")
    
    # Blender 버전에 따라 내보내기 명령 시도
    if hasattr(bpy.ops.wm, "collada_export"):
        bpy.ops.wm.collada_export(filepath=dae_path, check_existing=False, selected=True)
    elif hasattr(bpy.ops.export_scene, "dae"):
        bpy.ops.export_scene.dae(filepath=dae_path, check_existing=False, selected=True)
    else:
        # 5.0 버전 등에서 명령어를 못 찾을 경우 강제 시도 (Legacy context)
        print("⚠️ Standard Collada operator not found. Trying context override...")
        try:
             bpy.ops.wm.collada_export(filepath=dae_path, check_existing=False, selected=True)
        except AttributeError:
             print("❌ CRITICAL: This Blender version does not support Collada Export via Python.")
             print("   Please use Blender 3.6 LTS or 4.2 LTS.")
             raise

    print("✅ DAE export completed successfully!")

except Exception as e:
    print("❌ Error:")
    import traceback
    traceback.print_exc()