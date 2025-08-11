# editor_spawn_actor.py
# 사용 예:
#   py "D:/git/XR-Studio/MyProjectCamera/Content/Python/editor_spawn_actor.py" --fbx "D:/path/model.fbx" --dest "/Game/Imported" --spawn
#   py "D:/git/XR-Studio/MyProjectCamera/Content/Python/editor_spawn_actor.py" --asset "/Game/Imported/ModelName" --spawn

import unreal
import sys
import os
import argparse
import time

def ensure_editor_world():
    # Editor 전용 실행 보장 (PIE/Sim 중단)
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        world = None
    if not world:
        unreal.log_warning("❌ 에디터 월드를 찾을 수 없거나 PIE 상태입니다. (Editor 모드에서 실행하세요)")
        sys.exit(1)
    return world

def import_fbx(fbx_path: str, dest_path: str) -> str:
    if not os.path.isfile(fbx_path):
        unreal.log_warning(f"❌ FBX 파일 없음: {fbx_path}")
        return ""

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

    filename = os.path.splitext(os.path.basename(fbx_path))[0]

    task = unreal.AssetImportTask()
    task.filename = fbx_path
    task.destination_path = dest_path
    task.automated = True
    task.save = True
    task.replace_existing = True

    # (옵션 필요 시) task.options = ...
    asset_tools.import_asset_tasks([task])

    asset_path = f"{dest_path}/{filename}"
    unreal.log(f"📦 임포트 완료 후보: {asset_path}")

    # 로드 재시도 (레지스트리 백업)
    mesh = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not mesh:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        time.sleep(0.5)
        data = registry.get_asset_by_object_path(asset_path)
        if data and data.is_valid():
            mesh = data.get_asset()

    if not mesh:
        unreal.log_warning("❌ 임포트된 에셋 로드 실패")
        return ""

    unreal.log(f"✅ 임포트 성공: {asset_path}")
    return asset_path

def spawn_asset(asset_path: str, location=(0,0,100), rotation=(0,0,0)):
    world = ensure_editor_world()

    # 에셋 로드
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not asset:
        unreal.log_warning(f"❌ 에셋 로드 실패: {asset_path}")
        return None

    # EditorActorSubsystem 우선 사용
    actor_sys = None
    try:
        actor_sys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    except Exception:
        actor_sys = None

    loc = unreal.Vector(*location)
    rot = unreal.Rotator(*rotation)

    actor = None
    if actor_sys and hasattr(actor_sys, "spawn_actor_from_object"):
        actor = actor_sys.spawn_actor_from_object(asset, loc, rot)
    else:
        # 구버전 호환
        actor = unreal.EditorLevelLibrary.spawn_actor_from_object(asset, loc, rot)

    if actor:
        unreal.log(f"✅ Spawned: {actor.get_name()}")
    else:
        unreal.log_warning("❌ 스폰 실패")

    return actor

def main():
    ensure_editor_world()

    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", type=str, default="")
    parser.add_argument("--asset", type=str, default="")
    parser.add_argument("--dest", type=str, default="/Game/Imported")
    parser.add_argument("--spawn", action="store_true")
    parser.add_argument("--x", type=float, default=0)
    parser.add_argument("--y", type=float, default=0)
    parser.add_argument("--z", type=float, default=100)
    args = parser.parse_args()

    asset_path = args.asset

    # FBX 임포트가 요청되면 먼저 임포트
    if args.fbx:
        asset_path = import_fbx(args.fbx, args.dest)
        if not asset_path:
            unreal.log_warning("❌ FBX 임포트 실패. 종료합니다.")
            return

    # 스폰 요청 처리
    if args.spawn:
        if not asset_path:
            unreal.log_warning("⚠️ 스폰할 에셋 경로가 없습니다. --asset 또는 --fbx를 제공하세요.")
            return
        spawn_asset(asset_path, (args.x, args.y, args.z), (0,0,0))

if __name__ == "__main__":
    main()
