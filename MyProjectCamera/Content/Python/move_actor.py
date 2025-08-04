import unreal

def move_actor_by_name(actor_name, x, y, z):
    actors = unreal.EditorLevelLibrary.get_all_level_actors()

    for actor in actors:
        if actor.get_name().startswith(actor_name):
            location = unreal.Vector(x, y, z)
            actor.set_actor_location(location, False)
            unreal.log("✅ {} 이동 완료: {}".format(actor_name, location))
            return

    unreal.log_warning("❌ '{}' 이름의 액터를 찾을 수 없음".format(actor_name))

# 예시 실행
move_actor_by_name("Cube", 0, 0, 500)
