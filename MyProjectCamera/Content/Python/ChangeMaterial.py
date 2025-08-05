import socket
import tkinter as tk
from tkinter import filedialog
from functools import partial

# 1️⃣ Unreal 소켓 클라이언트
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
            print(f"❌ 서버 연결 실패: {e}")

    def send_command(self, command: str):
        try:
            self.sock.sendall((command.strip() + "\n").encode('utf-8'))
            print(f"📤 명령 전송: {command}")
            return self.sock.recv(4096).decode('utf-8')
        except Exception as e:
            return f"❌ 통신 오류: {e}"

    def close(self):
        self.sock.close()


# 2️⃣ 경로 변환 (윈도우 → 언리얼 경로)
def convert_to_unreal_path(filepath):
    path = filepath.replace("D:/git/XR-Studio/MyProjectCamera/Content", "/Game")
    path = path.replace("\\", "/")
    path = path.replace(".uasset", "")
    print(f"[DEBUG] Unreal Path: {path}")
    return path


# 3️⃣ UI 클래스
class UnifiedUnrealEditorUI:
    def __init__(self):
        self.client = UnrealSocketClient()
        self.client.connect()

        self.root = tk.Tk()
        self.root.title("🎮 Unreal Editor Control")

        self.selected_actor = None
        self.selected_slot = None
        self.position = {"X": 0, "Y": 0, "Z": 0}

        self.build_gui()

    # ✅ GUI 구성
    def build_gui(self):
        # 액터 목록
        tk.Button(self.root, text="📡 액터 목록 불러오기", command=self.load_actor_list).pack()
        self.actor_listbox = tk.Listbox(self.root, height=10, width=40)
        self.actor_listbox.pack()
        self.actor_listbox.bind("<<ListboxSelect>>", self.on_actor_selected)

        # 액터 이동
        tk.Label(self.root, text="🧭 액터 위치 이동").pack()
        slider_frame = tk.Frame(self.root)
        slider_frame.pack()

        self.scale_x = tk.Scale(slider_frame, from_=-1, to=1, resolution=1,
                                orient=tk.HORIZONTAL, label="X",
                                command=lambda v: self.on_slider_change("X", int(v)))
        self.scale_x.set(0)
        self.scale_x.pack(side=tk.LEFT)

        self.scale_y = tk.Scale(slider_frame, from_=-1, to=1, resolution=1,
                                orient=tk.HORIZONTAL, label="Y",
                                command=lambda v: self.on_slider_change("Y", int(v)))
        self.scale_y.set(0)
        self.scale_y.pack(side=tk.LEFT)

        self.scale_z = tk.Scale(slider_frame, from_=-1, to=1, resolution=1,
                                orient=tk.HORIZONTAL, label="Z",
                                command=lambda v: self.on_slider_change("Z", int(v)))
        self.scale_z.set(0)
        self.scale_z.pack(side=tk.LEFT)

        # 머티리얼/텍스처 정보
        tk.Label(self.root, text="🎨 텍스처/머티리얼 정보").pack()
        self.texture_info = tk.Text(self.root, height=15, width=60)
        self.texture_info.pack()

        tk.Button(self.root, text="🆕 액터 Spawn", command=self.spawn_actor).pack(pady=5)
        tk.Button(self.root, text="📦 FBX 임포트 + 배치", command=self.import_and_place_fbx).pack(pady=5)


        # 슬롯 버튼 영역
        self.slot_frame = tk.Frame(self.root)
        self.slot_frame.pack(pady=5)



    # ✅ 액터 목록 조회
    def load_actor_list(self):
        result = self.client.send_command("LIST")
        actors = result.strip().splitlines()
        self.actor_listbox.delete(0, tk.END)
        for actor in actors:
            self.actor_listbox.insert(tk.END, actor)

    # ✅ 액터 선택 시 처리
    def on_actor_selected(self, event):
        selection = self.actor_listbox.curselection()
        if not selection:
            return

        self.selected_actor = self.actor_listbox.get(selection[0])
        self.position = {"X": 0, "Y": 0, "Z": 0}

        result = self.client.send_command(f"GET_TEXTURES {self.selected_actor}")
        self.texture_info.delete("1.0", tk.END)
        self.texture_info.insert(tk.END, result)

        # 슬롯 수 확인 후 버튼 렌더링
        slot_lines = [line for line in result.splitlines() if line.startswith("Material Slot")]
        self.render_slot_buttons(len(slot_lines))

    # ✅ 머티리얼 슬롯 버튼 생성
    def render_slot_buttons(self, count):
        for widget in self.slot_frame.winfo_children():
            widget.destroy()

        for idx in range(count):
            btn = tk.Button(self.slot_frame, text=f"Slot {idx}",
                            command=partial(self.on_slot_selected, idx),
                            width=12)
            row, col = divmod(idx, 2)
            btn.grid(row=row, column=col, padx=5, pady=5)

    # ✅ 머티리얼 변경 요청
    def on_slot_selected(self, slot_index):
        self.selected_slot = slot_index
        filepath = filedialog.askopenfilename(
            title="교체할 머티리얼 선택",
            initialdir="D:/git/XR-Studio/MyProjectCamera/Content/Textures",
            filetypes=[("머티리얼 파일", "*.uasset")]
        )

        if not filepath:
            return

        unreal_path = convert_to_unreal_path(filepath)
        command = f"SET_MATERIAL {self.selected_actor} {slot_index} {unreal_path}"
        result = self.client.send_command(command)
        self.texture_info.insert(tk.END, f"\n{result}\n")

    # ✅ 액터 이동 명령 전송
    def send_move(self):
        if not self.selected_actor:
            print("❌ 액터가 선택되지 않았습니다.")
            return

        x, y, z = self.position["X"], self.position["Y"], self.position["Z"]
        command = f"MOVE {self.selected_actor} {x} {y} {z}"
        result = self.client.send_command(command)
        self.texture_info.insert(tk.END, f"\n{result}\n")

    # ✅ 슬라이더 이동 처리 (누적 위치)
    def on_slider_change(self, axis, value):
        if value == 0:
            return

        self.position[axis] += value
        print(f"🧭 {axis} 이동: 누적 위치 = {self.position[axis]}")

        # 슬라이더 원위치로 리셋
        if axis == "X":
            self.scale_x.set(0)
        elif axis == "Y":
            self.scale_y.set(0)
        elif axis == "Z":
            self.scale_z.set(0)

        self.send_move()

    def import_and_place_fbx(self):
        filepath = filedialog.askopenfilename(
            title="FBX 파일 선택",
            filetypes=[("FBX 파일", "*.fbx")]
        )
        if not filepath:
            return
        # FBX 전체 경로를 Unreal로 전송
        command = f'IMPORT_FBX "{filepath}"'
        result = self.client.send_command(command)
        self.texture_info.insert(tk.END, f"\n{result}\n")


    def load_blueprint_list(self, path="/Game/SimBlank/Blueprints"):
        cmd = f"GET_BLUEPRINTS {path}"
        result = self.client.send_command(cmd)
        blueprint_paths = result.strip().splitlines()

        # 출력 또는 리스트박스에 표시
        for path in blueprint_paths:
            print("🔹", path)
                # 예: 자동 선택해서 Spawn 명령 보내기
        if blueprint_paths:
            chosen = blueprint_paths[0]  # 예: 첫 번째 블루프린트
            spawn_cmd = f"SPAWN {chosen} 0 0 100"
            spawn_result = self.client.send_command(spawn_cmd)
            print("Spawn 결과:", spawn_result)

    def spawn_actor(self):
        filepath = filedialog.askopenfilename(
            title="Spawn할 블루프린트 선택",
            initialdir="D:/git/XR-Studio/MyProjectCamera/Content/Blueprints",
            filetypes=[("블루프린트", "*.uasset")]
        )
        if not filepath:
            return

        # Unreal 경로로 변환
        unreal_path = convert_to_unreal_path(filepath)
        if not unreal_path.endswith("_C"):
            unreal_path += "_C"  # 컴파일된 BP 클래스

        # 간단하게 위치 하드코딩 or 개선 시 TextEntry 등 UI 추가 가능
        x, y, z = 0, 0, 100  # Spawn 위치 기본값
        cmd = f"SPAWN {unreal_path} {x} {y} {z}"
        result = self.client.send_command(cmd)
        self.texture_info.insert(tk.END, f"\n{result}\n")

        # 액터 목록 갱신
        self.load_actor_list()


    # ✅ GUI 실행
    def run(self):
        self.root.mainloop()
        self.client.close()


# 실행
if __name__ == "__main__":
    ui = UnifiedUnrealEditorUI()
    ui.run()
