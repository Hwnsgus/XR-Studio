import unreal
import argparse
import json
import os
import time

# ---------- 공통 유틸 ----------

def ensure_editor_world():
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        world = None
    if not world:
        unreal.log_warning("❌ 에디터 월드를 찾을 수 없거나 PIE 상태입니다. (Editor 모드에서 실행하세요)")
        raise SystemExit(1)
    return world

def project_saved_dir(*paths):
    base = unreal.Paths.project_saved_dir()
    return os.path.join(base, *paths)

def makedirs(path):
    os.makedirs(path, exist_ok=True)

def load_asset_with_retry(asset_path: str, attempts: int = 6, delay: float = 0.25):
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset:
        return asset
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    for _ in range(attempts):
        unreal.SystemLibrary.delay(None, delay)
        data = registry.get_asset_by_object_path(asset_path)
        if data and data.is_valid():
            asset = data.get_asset()
            if asset:
                return asset
    return None

# ---------- 프리셋 스키마 ----------
# v1 스키마 (StaticMeshActor 중심):
# {
#   "version": 1,
#   "name": "Foo",
#   "saved_at": "2025-08-20T04:24:00Z",
#   "actors": [
#     {
#       "label": "Wall01",
#       "class": "/Script/Engine.StaticMeshActor",
#       "location": [x,y,z],
#       "rotation": [pitch,yaw,roll],
#       "scale": [sx,sy,sz],
#       "static_mesh": "/Game/Path/Asset.Asset",
#       "materials": ["/Game/Mat/M1.M1", "/Game/Mat/M2.M2"],
#       "mobility": "Movable" | "Static" | "Stationary"
#     },
#     ...
#   ]
# }

def actor_to_entry(actor: unreal.Actor):
    # StaticMeshActor만 저장 (v1)
    if not isinstance(actor, unreal.StaticMeshActor):
        return None

    smc = actor.static_mesh_component
    if not smc:
        return None
    mesh = smc.get_editor_property("static_mesh")
    if not mesh:
        return None

    # 머티리얼 경로 목록
    mats = []
    for i in range(smc.get_num_materials()):
        mi = smc.get_material(i)
        if mi:
            mats.append(mi.get_path_name())
        else:
            mats.append("")

    t = actor.get_actor_transform()
    rot = actor.get_actor_rotation()  # Rotator (Pitch, Yaw, Roll)

    entry = {
        "label": actor.get_actor_label(),
        "class": actor.get_class().get_path_name(),
        "location": [t.translation.x, t.translation.y, t.translation.z],
        "rotation": [rot.pitch, rot.yaw, rot.roll],
        "scale": [t.scale3d.x, t.scale3d.y, t.scale3d.z],
        "static_mesh": mesh.get_path_name(),
        "materials": mats,
        "mobility": str(smc.get_editor_property("mobility").name)  # MOVABLE/STATIC/STATIONARY
    }
    return entry

def collect_static_mesh_actors(only_selected=False):
    world = ensure_editor_world()
    if only_selected:
        actors = unreal.EditorLevelLibrary.get_selected_level_actors()
    else:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()

    entries = []
    for a in actors:
        e = actor_to_entry(a)
        if e:
            entries.append(e)
    return entries

def save_preset(name: str, only_selected=False):
    ensure_editor_world()
    entries = collect_static_mesh_actors(only_selected=only_selected)
    if not entries:
        unreal.log_warning("⚠️ 저장할 StaticMeshActor가 없습니다.")
        return ""

    data = {
        "version": 1,
        "name": name,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actors": entries
    }

    out_dir = project_saved_dir("ScenePresets")
    makedirs(out_dir)
    out_path = os.path.join(out_dir, f"{name}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    unreal.log(f"✅ 프리셋 저장 완료: {out_path} (Actors: {len(entries)})")
    return out_path

def apply_materials(smc: unreal.StaticMeshComponent, material_paths):
    for idx, mpath in enumerate(material_paths or []):
        if not mpath:
            continue
        mi = load_asset_with_retry(mpath)
        if mi:
            smc.set_material(idx, mi)

def mobility_from_name(name: str):
    name = (name or "").upper()
    if name == "MOVABLE":
        return unreal.ComponentMobility.MOVABLE
    if name == "STATIONARY":
        return unreal.ComponentMobility.STATIONARY
    return unreal.ComponentMobility.STATIC

def spawn_static_mesh(entry, offset=(0,0,0)):
    ensure_editor_world()
    mesh = load_asset_with_retry(entry["static_mesh"])
    if not mesh:
        unreal.log_warning(f"❌ 메쉬 로드 실패: {entry['static_mesh']}")
        return None

    # 위치/회전/스케일
    lx, ly, lz = entry["location"]
    ox, oy, oz = offset
    loc = unreal.Vector(lx + ox, ly + oy, lz + oz)
    pitch, yaw, roll = entry["rotation"]
    rot = unreal.Rotator(pitch, yaw, roll)
    sx, sy, sz = entry["scale"]

    # 스폰
    actor_sub = None
    try:
        actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    except Exception:
        pass

    if actor_sub and hasattr(actor_sub, "spawn_actor_from_object"):
        actor = actor_sub.spawn_actor_from_object(mesh, loc, rot)
    else:
        # fallback
        actor = unreal.EditorLevelLibrary.spawn_actor_from_object(mesh, loc, rot)

    if not actor:
        unreal.log_warning("❌ 스폰 실패")
        return None

    # 스케일/라벨/모빌리티/머티리얼
    try:
        actor.set_actor_scale3d(unreal.Vector(sx, sy, sz))
    except Exception:
        pass

    try:
        if entry.get("label"):
            actor.set_actor_label(entry["label"])
    except Exception:
        pass

    try:
        smc = actor.get_components_by_class(unreal.StaticMeshComponent)
        for c in smc:
            c.set_editor_property("mobility", mobility_from_name(entry.get("mobility")))
            apply_materials(c, entry.get("materials"))
    except Exception as e:
        unreal.log_warning(f"⚠️ 속성 적용 경고: {e}")

    unreal.log(f"✅ Spawned from preset: {actor.get_name()}")
    return actor

def load_preset(name: str, offset=(0,0,0)):
    ensure_editor_world()
    in_path = os.path.join(project_saved_dir("ScenePresets"), f"{name}.json")
    if not os.path.isfile(in_path):
        unreal.log_warning(f"❌ 프리셋 파일을 찾을 수 없음: {in_path}")
        return

    with open(in_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("version") != 1:
        unreal.log_warning("⚠️ 지원하지 않는 프리셋 버전")
        return

    count = 0
    for e in data.get("actors", []):
        if e.get("class", "").endswith("StaticMeshActor"):
            spawn_static_mesh(e, offset=offset)
            count += 1

    unreal.log(f"✅ 프리셋 로드 완료: {name} (Spawned: {count})")

# ---------- 엔트리 ----------
def main():
    ensure_editor_world()
    p = argparse.ArgumentParser()
    p.add_argument("--save-preset", action="store_true")
    p.add_argument("--load-preset", action="store_true")
    p.add_argument("--name", type=str, default="Preset")
    p.add_argument("--only-selected", action="store_true", help="선택된 액터만 저장")
    p.add_argument("--offset-x", type=float, default=0)
    p.add_argument("--offset-y", type=float, default=0)
    p.add_argument("--offset-z", type=float, default=0)
    args = p.parse_args()

    if args.save_preset:
        save_preset(args.name, only_selected=args.only_selected)
    elif args.load_preset:
        load_preset(args.name, offset=(args.offset_x, args.offset_y, args.offset_z))
    else:
        unreal.log_warning("⚠️ --save-preset 또는 --load-preset 중 하나를 지정하세요.")

if __name__ == "__main__":
    main()
