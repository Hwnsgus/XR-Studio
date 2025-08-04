import unreal

# 1. FBX 임포트 설정
fbx_import_options = unreal.FbxImportUI()
fbx_import_options.import_as_skeletal = False
fbx_import_options.import_mesh = True
fbx_import_options.create_physics_asset = False
fbx_import_options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH

# 메시 임포트 관련 세부 설정
fbx_import_options.static_mesh_import_data.combine_meshes = True  # ✅ 개별 오브젝트 유지 여부
fbx_import_options.static_mesh_import_data.auto_generate_collision = True
fbx_import_options.automated_import_should_detect_type = True

# 2. 임포트 파라미터
fbx_path = "D:/UnrealProject/MyProjectCamera/Content/Scripts/ExportedFBX/wall.fbx"
destination_path = "/Game/Scripts/ImportAssets"  # 콘텐츠 브라우저 경로

# 3. 에셋 툴 사용
task = unreal.AssetImportTask()
task.filename = fbx_path
task.destination_path = destination_path
task.options = fbx_import_options
task.automated = True
task.save = True

unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

# 4. 임포트 완료 후 액터 스폰
#    → FBX 안에 여러 메시가 있을 수 있으므로 모두 불러오기

imported_assets = unreal.EditorAssetLibrary.list_assets(destination_path, recursive=False)
print("📦 임포트된 에셋 목록:")
print(imported_assets)

# 첫 메시만 가져와서 레벨에 스폰 (필요하면 루프 돌려서 전부 스폰 가능)
spawned = False
for asset_path in imported_assets:
    if asset_path.endswith("_BuiltData"):  # 필요 없는 것 제외
        continue
    mesh = unreal.load_asset(asset_path)
    if isinstance(mesh, unreal.StaticMesh):
        unreal.EditorLevelLibrary.spawn_actor_from_object(mesh, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        print(f"✅ Spawned: {asset_path}")
        spawned = True
        break

if not spawned:
    print("❌ StaticMesh 없음 또는 스폰 실패.")
