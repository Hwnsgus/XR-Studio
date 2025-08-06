import unreal
import os

# ✅ 1. 설정
fbx_path = r"D:/git/XR-Studio/MyProjectCamera/Content/Scripts/ExportedFBX/house.fbx"
destination_path = "/Game/Imported"
filename = os.path.splitext(os.path.basename(fbx_path))[0]
asset_name = filename

# ✅ 2. 임포트 작업 생성
task = unreal.AssetImportTask()
task.filename = fbx_path
task.destination_path = destination_path
task.destination_name = asset_name
task.replace_existing = True
task.automated = True
task.save = True

# ✅ 3. 임포트 실행
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
asset_tools.import_asset_tasks([task])

# ✅ 4. StaticMesh로 로드
mesh_path = f"{destination_path}/{asset_name}"
mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)

# ✅ 5. 에디터에 스폰
if mesh:
    location = unreal.Vector(0, 0, 100)
    rotation = unreal.Rotator(0, 0, 0)
    actor = unreal.EditorLevelLibrary.spawn_actor_from_object(mesh, location, rotation)
    print(f"✅ FBX 임포트 및 스폰 완료: {actor.get_name()}")
else:
    print(f"❌ StaticMesh 로드 실패: {mesh_path}")
