import unreal

def get_assets_in_path(path: str, class_filter=None):
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    if class_filter:
        return registry.get_assets_by_path(path, recursive=True, include_only_on_disk_assets=False)
    return registry.get_assets_by_path(path, recursive=True)

def extract_material_textures(static_mesh):
    materials = static_mesh.static_materials
    result = []

    for mat_slot in materials:
        material = mat_slot.material_interface
        textures = {}

        # Material Graph를 파싱하는 방식으로 연결된 텍스처를 확인
        if material:
            expressions = material.get_editor_property("expressions")
            for expr in expressions:
                if isinstance(expr, unreal.MaterialExpressionTextureSample):
                    param_name = expr.get_editor_property("parameter_name")
                    tex = expr.get_editor_property("texture")
                    if param_name and tex:
                        textures[str(param_name)] = tex.get_name()
        
        result.append({
            "material_name": material.get_name() if material else "None",
            "textures": textures
        })

    return result

def scan_folder_and_print_tree(folder_path="D:/UnrealProject/MyProjectCamera/Content/Scripts/ExportedFBX"):
    assets = get_assets_in_path(folder_path)
    for asset in assets:
        if asset.asset_class == "StaticMesh":
            mesh = unreal.load_asset(asset.object_path)
            print(f"📦 {mesh.get_name()}")
            materials_info = extract_material_textures(mesh)
            for idx, mat_info in enumerate(materials_info):
                print(f"  └─ Material Slot {idx}: {mat_info['material_name']}")
                for tex_type, tex_name in mat_info["textures"].items():
                    print(f"       └ {tex_type}: {tex_name}")



### 2. 언리얼 TCP 서버와 연결 (소켓 통신) ###
class UnrealSocketClient:
    def __init__(self, ip='127.0.0.1', port=9999):
        self.server_ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self):
        try:
            self.sock.connect((self.server_ip, self.port))
            print(f"✅ Unreal 서버 연결 완료: {self.server_ip}:{self.port}")
        except Exception as e:
            print(f"❌ 연결 실패: {e}")

    def send_command(self, command: str):
        try:
            self.sock.sendall(command.encode('utf-8'))
            print(f"📤 명령 전송: {command}")

            data = self.sock.recv(4096)
            print(f"📥 응답 수신: {data.decode('utf-8')}")
        except Exception as e:
            print(f"❌ 통신 오류: {e}")

    def close(self):
        self.sock.close()
        print("🔌 연결 종료됨")


### 3. 예시 실행 ###
if __name__ == "__main__":
    # 1. Unreal 에디터에서 FBX 머티리얼 검사
    scan_folder_and_print_tree("/Game/Scripts/ExportedFBX")

    # 2. Unreal TCP 서버에 명령 전송
    client = UnrealSocketClient()
    client.connect()

    # 예: 액터 목록 요청
    client.send_command("LIST")

    # 예: 액터 이동
    # client.send_command("MOVE MyCube 100 0 50")

    client.close()