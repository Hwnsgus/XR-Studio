# import_fbx_and_create_bp.py

import unreal

def import_fbx(fbx_path, destination_path="/Game/Imported", bp_name="AutoActor"):
    print(f"📂 FBX 임포트 시작: {fbx_path}")

    # FBX 임포트 태스크 설정
    task = unreal.AssetImportTask()
    task.filename = fbx_path
    task.destination_path = destination_path
    task.automated = True
    task.replace_existing = True
    task.save = True

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    # StaticMesh 자산 확인
    assets = unreal.EditorAssetLibrary.list_assets(destination_path, recursive=True)
    mesh_asset_path = next((a for a in assets if a.endswith("_SM") or "SM_" in a), None)

    if not mesh_asset_path:
        unreal.log_error("❌ StaticMesh가 생성되지 않았습니다.")
        return None

    static_mesh = unreal.load_asset(mesh_asset_path)

    # 블루프린트 생성
    bp_factory = unreal.BlueprintFactory()
    bp_factory.set_editor_property("ParentClass", unreal.Actor)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(bp_name, destination_path, None, bp_factory)

    if not bp:
        unreal.log_error("❌ 블루프린트 생성 실패")
        return None

    # StaticMeshComponent 추가 및 메쉬 할당
    sm_component = unreal.EditorUtilities.add_component(bp, "StaticMeshComponent", False)
    sm_component.set_editor_property("static_mesh", static_mesh)

    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    print(f"✅ 블루프린트 생성 완료: {bp.get_path_name()}")

    return bp.get_path_name() + "_C"

# 예제 실행
fbx_path = r"D:\git\XR-Studio\MyProjectCamera\Content\Scripts\ExportedFBX\house.fbx"
import_fbx(fbx_path)
