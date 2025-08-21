import os
import socket
import time
import tkinter as tk
from tkinter import filedialog
from functools import partial

# 1️⃣ Unreal 소켓 클라이언트
class UnrealSocketClient:
    def __init__(self, ip='127.0.0.1', ports=[9999, 9998]):
        self.server_ip = ip
        self.ports = ports  # [PIE, EDITOR]
        self.sock = None
        self.current_port = None

    def close(self):
        if self.sock:
            try:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self.sock.close()
            finally:
                self.sock = None
                self.current_port = None

    def connect(self, port=None):
        """명시 포트가 없으면 기본으로 에디터 포트(9998)"""
        target_port = port or self.ports[1]
        self.close()
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(1.0)
            self.sock.connect((self.server_ip, target_port))
            self.current_port = target_port
            print(f"✅ 연결 {self.server_ip}:{target_port}")
            return True
        except Exception as e:
            print(f"❌ 연결 실패 {target_port}: {e}")
            self.sock = None
            self.current_port = None
            return False

    def _recv_until(self, timeout_sec=2.0):
        """\n 도착하거나 timeout이면 종료 (GUI 프리징 방지)"""
        end = time.time() + timeout_sec
        chunks = []
        while time.time() < end:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
                if b'\n' in data:
                    break
            except socket.timeout:
                continue
            except Exception as e:
                return f"❌ 수신 오류: {e}"
        if not chunks:
            return ""
        try:
            return b"".join(chunks).decode("utf-8", "ignore")
        except Exception:
            return "(binary)"

    def _send_and_get(self, payload: str):
        self.sock.sendall((payload.strip() + "\n").encode("utf-8"))
        return self._recv_until(2.0)

    def _auto_switch_if_needed(self, resp: str):
        """서버 신호를 받으면 자동 재연결"""
        if not resp:
            return False
        if "SWITCH:PIE" in resp:
            self.connect(self.ports[0])  # 9999
            return True
        if "SWITCH:EDITOR" in resp:
            self.connect(self.ports[1])  # 9998
            return True
        return False

    def send_command(self, command: str):
        try:
            is_editor_command = command.startswith("py ") or \
                                command.startswith("SPAWN_ASSET") or \
                                command.startswith("IMPORT_FBX")

            # 1) 현재 명령에 맞는 포트로 우선 연결
            target = self.ports[1] if is_editor_command else self.ports[0]
            if self.current_port != target or not self.sock:
                if not self.connect(target):
                    # 반대 포트로라도 시도
                    other = self.ports[0] if target == self.ports[1] else self.ports[1]
                    if not self.connect(other):
                        return "❌ 연결 실패"

            # 2) 전송/수신
            resp = self._send_and_get(command)

            # 3) 서버가 전환 신호를 보내면 즉시 갈아타고 재전송
            if self._auto_switch_if_needed(resp):
                resp = self._send_and_get(command)

            # 4) 응답이 비면 반대 포트로 재시도 (서버가 소켓을 닫은 경우)
            if not resp:
                other = self.ports[0] if self.current_port == self.ports[1] else self.ports[1]
                if self.connect(other):
                    resp = self._send_and_get(command)

            return resp or "⏳ (no response)"

        except Exception as e:
            # 마지막 보루: 반대 포트 재시도
            try:
                other = self.ports[0] if self.current_port == self.ports[1] else self.ports[1]
                if self.connect(other):
                    return self._send_and_get(command)
            except Exception as e2:
                return f"❌ 통신 오류: {e2}"
            return f"❌ 통신 오류: {e}"


# 2️⃣ 경로 변환 (윈도우 → 언리얼 경로, uasset 전용)
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
        self.client.connect()  # 기본: 에디터 포트(9998)

        self.root = tk.Tk()
        self.root.title("🎮 Unreal Editor Control")

        self.selected_actor = None
        self.selected_slot = None
        self.position = {"X": 0, "Y": 0, "Z": 0}

        # Preset UI 변수
        self.preset_name_var = tk.StringVar(value="MyPreset")
        self.only_selected_var = tk.BooleanVar(value=False)
        self.offset_x_var = tk.DoubleVar(value=0.0)
        self.offset_y_var = tk.DoubleVar(value=0.0)
        self.offset_z_var = tk.DoubleVar(value=0.0)

        self.build_gui()

    # ✅ GUI 구성
    def build_gui(self):
        tk.Button(self.root, text="📡 액터 목록 불러오기", command=self.load_actor_list).pack()
        self.actor_listbox = tk.Listbox(self.root, height=10, width=40)
        self.actor_listbox.pack()
        self.actor_listbox.bind("<<ListboxSelect>>", self.on_actor_selected)

        tk.Label(self.root, text="🧭 액터 위치 이동").pack()
        slider_frame = tk.Frame(self.root); slider_frame.pack()

        self.scale_x = tk.Scale(slider_frame, from_=-500, to=500, resolution=10,
                                orient=tk.HORIZONTAL, label="X",
                                command=lambda v: self.on_slider_change("X", int(v)))
        self.scale_x.set(0); self.scale_x.pack(side=tk.LEFT)

        self.scale_y = tk.Scale(slider_frame, from_=-50, to=50, resolution=10,
                                orient=tk.HORIZONTAL, label="Y",
                                command=lambda v: self.on_slider_change("Y", int(v)))
        self.scale_y.set(0); self.scale_y.pack(side=tk.LEFT)

        self.scale_z = tk.Scale(slider_frame, from_=-50, to=50, resolution=10,
                                orient=tk.HORIZONTAL, label="Z",
                                command=lambda v: self.on_slider_change("Z", int(v)))
        self.scale_z.set(0); self.scale_z.pack(side=tk.LEFT)

        tk.Label(self.root, text="🎨 텍스처/머티리얼 정보").pack()
        self.texture_info = tk.Text(self.root, height=15, width=60)
        self.texture_info.pack()

        # 에셋/프리셋/교체 버튼들
        btn_frame = tk.Frame(self.root); btn_frame.pack(pady=6)
        tk.Button(btn_frame, text="🧱 에셋 스폰(에디터)",
                  command=lambda: self.spawn_existing_asset("/Game/Scripts/ExportedFBX/house")).grid(row=0, column=0, padx=4)

        tk.Button(btn_frame, text="🗽 Replace Mesh (FBX)", command=self.replace_mesh_with_fbx).grid(row=0, column=1, padx=4)

        # 🔹 Preset 영역
        preset_frame = tk.LabelFrame(self.root, text="📦 Scene Preset")
        preset_frame.pack(fill="x", padx=4, pady=6)

        row = 0
        tk.Label(preset_frame, text="Name").grid(row=row, column=0, sticky="e", padx=4, pady=2)
        tk.Entry(preset_frame, textvariable=self.preset_name_var, width=24).grid(row=row, column=1, sticky="w", padx=4, pady=2)
        tk.Checkbutton(preset_frame, text="Only Selected", variable=self.only_selected_var).grid(row=row, column=2, sticky="w", padx=4)

        row += 1
        tk.Label(preset_frame, text="Offset X/Y/Z").grid(row=row, column=0, sticky="e", padx=4, pady=2)
        tk.Entry(preset_frame, textvariable=self.offset_x_var, width=6).grid(row=row, column=1, sticky="w", padx=(4,0))
        tk.Entry(preset_frame, textvariable=self.offset_y_var, width=6).grid(row=row, column=1, sticky="w", padx=(64,0))
        tk.Entry(preset_frame, textvariable=self.offset_z_var, width=6).grid(row=row, column=1, sticky="w", padx=(124,0))

        row += 1
        tk.Button(preset_frame, text="💾 Save Preset", command=self.save_preset_btn).grid(row=row, column=0, padx=4, pady=6, sticky="we")
        tk.Button(preset_frame, text="📥 Load Preset", command=self.load_preset_btn).grid(row=row, column=1, padx=4, pady=6, sticky="we")

        self.slot_frame = tk.Frame(self.root); self.slot_frame.pack(pady=5)

    # ✅ 액터 목록 조회 (가능하면 9999에 붙어서)
    def load_actor_list(self):
        # 가능하면 PIE 포트(9999)에 접속
        if self.client.current_port != self.client.ports[0] or not self.client.sock:
            if not self.client.connect(self.client.ports[0]):  # 9999
                self.texture_info.insert(tk.END, "\n❌ PIE(9999) 연결 실패\n")
                return

        result = self.client.send_command("LIST_STATIC")  # 서버가 LIST_STATIC 지원 시 StaticMeshActor만
        if not result.strip():
            result = self.client.send_command("LIST")

        actors = [a for a in result.strip().splitlines() if a]
        self.actor_listbox.delete(0, tk.END)
        for actor in actors:
            self.actor_listbox.insert(tk.END, actor)

    # ✅ 액터 선택 시 처리 (위치 동기화 + 텍스처 정보)
    def on_actor_selected(self, event):
        selection = self.actor_listbox.curselection()
        if not selection:
            return
        self.selected_actor = self.actor_listbox.get(selection[0])

        # 위치 동기화: GET_LOCATION (서버 구현 필요)
        result = self.client.send_command(f"GET_LOCATION {self.selected_actor}")
        try:
            parts = result.strip().split()
            if len(parts) == 4 and parts[0] == "Location:":
                self.position["X"] = float(parts[1])
                self.position["Y"] = float(parts[2])
                self.position["Z"] = float(parts[3])
        except Exception as e:
            print(f"⚠️ 위치 파싱 실패: {e}")

        # 머티리얼/텍스처 정보
        tex_info = self.client.send_command(f"GET_TEXTURES {self.selected_actor}")
        self.texture_info.delete("1.0", tk.END)
        self.texture_info.insert(tk.END, tex_info)

        slot_lines = [line for line in tex_info.splitlines() if line.startswith("Material Slot")]
        self.render_slot_buttons(len(slot_lines))

    # ✅ 머티리얼 슬롯 버튼 생성
    def render_slot_buttons(self, count):
        for w in self.slot_frame.winfo_children():
            w.destroy()
        for idx in range(count):
            btn = tk.Button(self.slot_frame, text=f"Slot {idx}",
                            command=partial(self.on_slot_selected, idx), width=12)
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

        unreal_path = convert_to_unreal_path(filepath).strip()
        if not unreal_path:
            self.texture_info.insert(tk.END, "\n❌ 경로 변환 실패\n")
            return

        command = f'SET_MATERIAL {self.selected_actor} {self.selected_slot} "{unreal_path}"'
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
        if axis == "X": self.scale_x.set(0)
        elif axis == "Y": self.scale_y.set(0)
        elif axis == "Z": self.scale_z.set(0)
        self.send_move()

    def send_editor_command(self, command: str):
        """에디터(9998)로 강제 전송. 먼저 끊지 않고 포트만 맞춰 재연결."""
        if self.client.current_port != self.client.ports[1] or not self.client.sock:
            if not self.client.connect(self.client.ports[1]):  # 9998
                return "❌ Unreal Editor와 연결되지 않았습니다."
        return self.client.send_command(command)

    # ✅ 기존 에셋 경로로 에디터에서 스폰 (파이썬을 통해 좌표 지정)
    def spawn_existing_asset(self, unreal_asset_path: str):
        if self.client.current_port != self.client.ports[1] or not self.client.sock:
            if not self.client.connect(self.client.ports[1]):  # 9998
                self.texture_info.insert(tk.END, "\n❌ Unreal Editor와 연결되지 않았습니다.\n")
                return
        script_path = "D:/git/XR-Studio/MyProjectCamera/Content/Python/editor_spawn_actor.py"
        cmd = f'py "{script_path}" --asset "{unreal_asset_path}" --spawn --x 1700 --y 0 --z 10'
        result = self.client.send_command(cmd)
        self.texture_info.insert(tk.END, f"\n{result}\n")
        print(result)

    # ✅ Preset 저장 버튼
    def save_preset_btn(self):
        name = (self.preset_name_var.get() or "Preset").strip()
        script_path = "D:/git/XR-Studio/MyProjectCamera/Content/Python/editor_scene_preset.py"

        # PIE면 런타임 커맨드, 아니면 에디터 py
        if self.client.connect(self.client.ports[0]):  # 9999
            resp = self.client.send_command(f"SAVE_PRESET {name}")
        else:
            cmd = f'py "{script_path}" --save-preset --name "{name}"'
            if self.only_selected_var.get():
                cmd += " --only-selected"
            resp = self.send_editor_command(cmd)  # 9998
        self.texture_info.insert(tk.END, f"\n{resp}\n")

    # ✅ Preset 로드 버튼 (파일 탐색기)
    def load_preset_btn(self):
        preset_dir = r"D:\git\XR-Studio\MyProjectCamera\Saved\ScenePresets"
        filepath = filedialog.askopenfilename(
            title="로드할 프리셋(.json) 선택",
            initialdir=preset_dir,
            filetypes=[("Scene Preset JSON", "*.json")]
        )
        if not filepath:
            return

        name = os.path.splitext(os.path.basename(filepath))[0]
        ox = self.offset_x_var.get() or 0.0
        oy = self.offset_y_var.get() or 0.0
        oz = self.offset_z_var.get() or 0.0

        script_path = "D:/git/XR-Studio/MyProjectCamera/Content/Python/editor_scene_preset.py"

        if self.client.connect(self.client.ports[0]):  # 9999
            resp = self.client.send_command(f"LOAD_PRESET {name} {ox} {oy} {oz}")
        else:
            cmd = f'py "{script_path}" --load-preset --name "{name}" --offset-x {ox} --offset-y {oy} --offset-z {oz}'
            resp = self.send_editor_command(cmd)  # 9998
        self.texture_info.insert(tk.END, f"\n{resp}\n")

    # ✅ Replace Mesh( FBX import → SET_STATIC_MESH )
    def replace_mesh_with_fbx(self):
        if not self.selected_actor:
            self.texture_info.insert(tk.END, "\n❌ 먼저 액터를 선택하세요.\n")
            return

        fbx = filedialog.askopenfilename(
            title="교체할 FBX 선택",
            filetypes=[("FBX 파일", "*.fbx")]
        )
        if not fbx:
            return

        # 1) 에디터에 임포트 (스폰 없이)
        script_path = "D:/git/XR-Studio/MyProjectCamera/Content/Python/editor_spawn_actor.py"
        dest = "/Game/Scripts/ExportedFBX"
        cmd_import = f'py "{script_path}" --fbx "{fbx}" --dest "{dest}"'
        resp = self.send_editor_command(cmd_import)  # 9998
        self.texture_info.insert(tk.END, f"\n{resp}\n")

        # 2) 에셋 경로 산출 (/Game/.../<name>)
        name = os.path.splitext(os.path.basename(fbx))[0]
        unreal_asset_short = f"{dest}/{name}"  # 점 없는 경로 (서버가 자동 보정하도록 구현)

        # 3) SET_STATIC_MESH 전송: PIE 우선, 실패 시 에디터로
        cmd_set = f'SET_STATIC_MESH {self.selected_actor} "{unreal_asset_short}"'
        if self.client.connect(self.client.ports[0]):  # 9999
            resp2 = self.client.send_command(cmd_set)
        else:
            # 에디터에서도 동일 명령 지원
            resp2 = self.send_editor_command(cmd_set)
        self.texture_info.insert(tk.END, f"\n{resp2}\n")

    # ✅ GUI 실행
    def run(self):
        self.root.mainloop()
        self.client.close()


# 실행
if __name__ == "__main__":
    ui = UnifiedUnrealEditorUI()
    ui.run()
