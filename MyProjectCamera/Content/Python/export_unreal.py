import unreal
import os

# 1. 실행 디렉토리 설정 (맨 위에서!)
target_dir = "D:/UnrealProject/MyProjectCamera/Content/Python/Scripts"
os.chdir(target_dir)

# 2. FBX 임포트 설정
fbx_import_options = unreal.FbxImportUI()
fbx_import_options.import_as_skeletal = False
fbx_import_options.import_mesh = True

# 3. FBX 파일 실제 위치 (디스크 경로)
fbx_path = "D:/UnrealProject/MyProjectCamera/Content/Scripts/ExportedFBX/house.fbx"

# 4. 임포트할 위치 (언리얼 에셋 경로! 반드시 /Game/... 형식)
destination_path = "/Game/Scripts/ImportAssets"

# 5. FBX 임포트 Task 생성
task = unreal.AssetImportTask()
task.filename = fbx_path
task.destination_path = destination_path
task.options = fbx_import_options
task.automated = True
task.save = True

unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

# 6. 임포트된 에셋 로드 (언리얼 경로 기준)
asset_path = "/Game/Scripts/ImportAssets/house.house"
static_mesh = unreal.load_asset(asset_path)

# 7. 액터 배치
if static_mesh:
    editor_level_lib = unreal.EditorLevelLibrary

    positions = [
        unreal.Vector(0, 0, 0),
        unreal.Vector(0, 500, 0),
        unreal.Vector(0, 250, 300)
    ]

    rotations = [
        unreal.Rotator(0, 0, 0),
        unreal.Rotator(0, 90, 0),
        unreal.Rotator(0, 180, 0)
    ]

    for pos, rot in zip(positions, rotations):
        actor = editor_level_lib.spawn_actor_from_object(static_mesh, pos, rot)
        actor.set_actor_label("WallSegment")
