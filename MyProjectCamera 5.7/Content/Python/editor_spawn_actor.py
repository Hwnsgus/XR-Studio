
import unreal
import argparse
import os
import sys
import time

# -------- 기본 유틸 --------

def ensure_editor_world():
    # Editor 전용 실행 보장 (PIE/Sim 차단)
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        world = None
    if not world:
        unreal.log_warning("❌ 에디터 월드를 찾을 수 없거나 PIE 상태입니다. (Editor 모드에서 실행하세요)")
        sys.exit(1)
    return world
# (editor_spawn_actor.py 기반):contentReference[oaicite:4]{index=4}

def load_asset_with_retry(asset_path: str, attempts: int = 6, delay: float = 0.25):
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset:
        return asset
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    for i in range(attempts):
        time.sleep(delay)
        data = registry.get_asset_by_object_path(asset_path)
        if data and data.is_valid():
            asset = data.get_asset()
            if asset:
                return asset
    return None
# (editor_spawn_actor.py / TempFbxImportScript.py 방식 차용):contentReference[oaicite:5]{index=5}:contentReference[oaicite:6]{index=6}

# -------- 임포트 / BP 생성 / 스폰 --------

def import_fbx(fbx_path: str, dest_path: str, replace_existing=True, save=True) -> str:
    if not os.path.isfile(fbx_path):
        unreal.log_warning(f"❌ FBX 파일 없음: {fbx_path}")
        return ""
    filename = os.path.splitext(os.path.basename(fbx_path))[0]

    task = unreal.AssetImportTask()
    task.filename = fbx_path
    task.destination_path = dest_path
    task.destination_name = filename
    task.automated = True
    task.replace_existing = bool(replace_existing)
    task.save = bool(save)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    asset_path = f"{dest_path}/{filename}"
    unreal.log(f"📦 임포트 완료 후보: {asset_path}")

    mesh = load_asset_with_retry(asset_path)
    if not mesh:
        unreal.log_warning("❌ 임포트된 에셋 로드 실패")
        return ""

    unreal.log(f"✅ 임포트 성공: {asset_path}")
    return asset_path
# (editor_spawn_actor.py / ImportStaticMesh.py 통합):contentReference[oaicite:7]{index=7}:contentReference[oaicite:8]{index=8}

def create_blueprint_with_static_mesh(static_mesh_asset_path: str, dest_path: str, bp_name: str) -> str:
    # StaticMesh 로드
    mesh = load_asset_with_retry(static_mesh_asset_path)
    if not mesh:
        unreal.log_error(f"❌ StaticMesh 로드 실패: {static_mesh_asset_path}")
        return ""

    # 블루프린트 생성 (ParentClass = Actor)
    bp_factory = unreal.BlueprintFactory()
    bp_factory.set_editor_property("ParentClass", unreal.Actor)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = asset_tools.create_asset(bp_name, dest_path, None, bp_factory)
    if not bp:
        unreal.log_error("❌ 블루프린트 생성 실패")
        return ""

    # StaticMeshComponent 추가 및 메쉬 할당
    try:
        sm_component = unreal.EditorUtilities.add_component(bp, "StaticMeshComponent", False)
        sm_component.set_editor_property("static_mesh", mesh)
    except Exception as e:
        unreal.log_error(f"❌ 컴포넌트 추가 실패: {e}")
        return ""

    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    bp_class_path = bp.get_path_name() + "_C"
    unreal.log(f"✅ 블루프린트 생성 완료: {bp.get_path_name()} (클래스: {bp_class_path})")
    return bp_class_path
# (import_fbx_and_create_bp.py 방식을 통합):contentReference[oaicite:9]{index=9}

def spawn_asset(asset_path: str, location=(0,0,100), rotation=(0,0,0), label: str = ""):
    ensure_editor_world()

    asset = load_asset_with_retry(asset_path)
    if not asset:
        unreal.log_warning(f"❌ 에셋 로드 실패: {asset_path}")
        return None

    loc = unreal.Vector(*location)
    rot = unreal.Rotator(*rotation)

    # EditorActorSubsystem 우선 (가능하면)
    actor_sys = None
    try:
        actor_sys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    except Exception:
        actor_sys = None

    actor = None
    if actor_sys and hasattr(actor_sys, "spawn_actor_from_object"):
        actor = actor_sys.spawn_actor_from_object(asset, loc, rot)
    else:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_object(asset, loc, rot)

    if actor:
        # ✅ 스폰 직후 컴포넌트 Mobility를 Movable로 강제
        try:
            # StaticMeshActor 또는 BP 등 다양한 경우를 커버
            sm_comps = actor.get_components_by_class(unreal.StaticMeshComponent)
            for c in sm_comps:
                c.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)

            # (선택) 다른 프리미티브 컴포넌트에도 적용하고 싶다면:
            # prim_comps = actor.get_components_by_class(unreal.PrimitiveComponent)
            # for c in prim_comps:
            #     c.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        except Exception as e:
            unreal.log_warning(f"⚠️ Mobility 설정 실패: {e}")

        if not label:
            label = os.path.splitext(os.path.basename(asset_path))[0]
        
        try:
            actor.set_actor_label(label)
        except Exception:
            pass

        unreal.log(f"✅ Spawned: {actor.get_name()} (Movable)")
    else:
        unreal.log_warning("❌ 스폰 실패")
    return actor

# (editor_spawn_actor.py 방식):contentReference[oaicite:10]{index=10}

# -------- 엔트리 포인트 --------

def main():
    ensure_editor_world()

    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", type=str, default="", help="임포트할 FBX 절대 경로")
    parser.add_argument("--asset", type=str, default="", help="기존 /Game/... 에셋 경로 (StaticMesh 또는 BP 클래스)")
    parser.add_argument("--dest", type=str, default="/Game/Scripts/ExportedFBX", help="임포트/생성 대상 경로")
    parser.add_argument("--spawn", action="store_true", help="에셋 스폰 여부")
    parser.add_argument("--create-bp", action="store_true", help="임포트한 StaticMesh로 BP 생성")
    parser.add_argument("--bp-name", type=str, default="AutoActor", help="생성할 블루프린트 이름")
    parser.add_argument("--replace-existing", action="store_true", help="임포트 시 동일 이름 덮어쓰기")
    parser.add_argument("--no-save", action="store_true", help="임포트 시 즉시 저장하지 않음")
    parser.add_argument("--x", type=float, default=0)
    parser.add_argument("--y", type=float, default=0)
    parser.add_argument("--z", type=float, default=100)
    parser.add_argument("--yaw", type=float, default=0)
    parser.add_argument("--pitch", type=float, default=0)
    parser.add_argument("--roll", type=float, default=0)
    parser.add_argument("--label", type=str, default="", help="스폰된 액터 라벨")
    args = parser.parse_args()

    # 1) 에셋 결정: --fbx 우선 → --asset
    final_asset_path = args.asset

    if args.fbx:
        final_asset_path = import_fbx(
            fbx_path=args.fbx,
            dest_path=args.dest,
            replace_existing=args.replace_existing,
            save=(not args.no_save),
        )
        if not final_asset_path:
            unreal.log_warning("❌ FBX 임포트 실패. 종료")
            return

    if not final_asset_path and not args.create_bp:
        unreal.log_warning("⚠️ 처리할 에셋이 없습니다. --fbx 또는 --asset 또는 --create-bp 옵션 확인")
        return

    # 2) (옵션) 블루프린트 생성
    if args.create_bp:
        # final_asset_path가 StaticMesh면 BP 생성, 아니면 --fbx를 통해 방금 임포트한 Mesh 기준
        mesh_source = final_asset_path
        if not mesh_source and args.fbx:
            # 임포트 결과를 바로 사용
            mesh_source = final_asset_path
        if not mesh_source:
            unreal.log_warning("⚠️ BP를 생성하려면 --fbx 또는 --asset(StaticMesh) 중 하나가 필요합니다.")
            return

        bp_class = create_blueprint_with_static_mesh(mesh_source, args.dest, args.bp_name)
        if not bp_class:
            unreal.log_warning("❌ BP 생성 실패")
            return
        # BP를 스폰 대상으로 바꿔치기 (BP 클래스 path)
        final_asset_path = bp_class

    # 3) (옵션) 스폰
    if args.spawn:
        spawn_asset(
            final_asset_path,
            location=(args.x, args.y, args.z),
            rotation=(args.pitch, args.yaw, args.roll),  # Rotator(Pitch, Yaw, Roll)
            label=args.label
        )

if __name__ == "__main__":
    main()