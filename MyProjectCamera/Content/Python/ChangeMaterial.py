import os
import socket
import time
import tkinter as tk
from tkinter import filedialog
from functools import partial

# 1️⃣ Unreal 소켓 클라이언트 (저지연 + 똑똑한 라우팅)
class UnrealSocketClient:
    def __init__(self, ip='127.0.0.1', ports=[9999, 9998]):
        self.server_ip = ip
        self.ports = ports  # [PIE, EDITOR]
        self.sock = None
        self.current_port = None
        self.connect_timeout = 0.15   # ⏱️ 연결 타임아웃 크게 축소
        self.recv_timeout    = 0.40   # ⏱️ 응답 수신 타임아웃 축소
        self.mode_hint = "EDITOR"     # 기본은 에디터로 가정 (9998 우선)

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

    def _new_socket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # ✅ Nagle 비활성화 → 지연 최소화
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.settimeout(self.connect_timeout)
        return s

    def connect(self, port):
        # 같은 포트로 이미 붙어 있으면 유지
        if self.sock and self.current_port == port:
            return True
        self.close()
        try:
            s = self._new_socket()
            s.connect((self.server_ip, port))
            s.settimeout(self.recv_timeout)
            self.sock = s
            self.current_port = port
            # 힌트 갱신
            self.mode_hint = "PIE" if port == self.ports[0] else "EDITOR"
            print(f"✅ 연결 {self.server_ip}:{port} (mode={self.mode_hint})")
            return True
        except Exception as e:
            # 연결 실패
            self.sock = None
            self.current_port = None
            print(f"❌ 연결 실패 {port}: {e}")
            return False

    def _quick_probe(self):
        """현재 모드 힌트에 맞춰 빠르게 연결 시도 (에디터 우선 기본)"""
        order = [self.ports[1], self.ports[0]] if self.mode_hint == "EDITOR" else [self.ports[0], self.ports[1]]
        for p in order:
            if self.connect(p):
                return True
        return False

    def _recv_until_newline(self):
        """개행('\n') 하나만 받으면 즉시 반환 → 지연 최소화
           서버는 명령마다 최소 1줄 OK/ERR을 보내도록 가정"""
        end = time.time() + self.recv_timeout
        chunks = []
        while time.time() < end:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
                # 한 줄만 도착해도 바로 반환 (빠른 응답)
                if b'\n' in data:
                    break
            except socket.timeout:
                break
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
        return self._recv_until_newline()

    def _auto_switch_if_needed(self, resp: str):
        """서버 모드 신호/에러를 보고 즉시 전환"""
        if not resp:
            return False
        if "SWITCH:PIE" in resp or "ERR PIE" in resp:
            if self.connect(self.ports[0]):  # 9999
                self.mode_hint = "PIE"
                return True
        if "SWITCH:EDITOR" in resp:
            if self.connect(self.ports[1]):  # 9998
                self.mode_hint = "EDITOR"
                return True
        return False

    def send_command(self, command: str):
        try:
            # 🎯 기존처럼 'py/IMPORT/SPA WN'만 에디터 강제 라우팅
            is_editor_command = command.startswith("py ") or \
                                command.startswith("SPAWN_ASSET") or \
                                command.startswith("IMPORT_FBX")

            # 1) 연결 없으면 모드 힌트 기반 빠른 연결
            if not self.sock:
                # 에디터 명령이면 에디터 우선
                self.mode_hint = "EDITOR" if is_editor_command else self.mode_hint
                if not self._quick_probe():
                    return "❌ 연결 실패"

            # 2) 현재 연결로 먼저 보냄 (불필요한 재접속 제거)
            resp = self._send_and_get(command)

            # 3) 서버가 전환 신호/PIE 에러 주면 즉시 갈아타고 재전송
            if self._auto_switch_if_needed(resp):
                resp = self._send_and_get(command)

            # 4) 응답이 비면 반대 포트로 한 번 더 시도
            if not resp:
                other = self.ports[0] if self.current_port == self.ports[1] else self.ports[1]
                if self.connect(other):
                    resp = self._send_and_get(command)

            return resp or "⏳ (no response)"
        except Exception as e:
            # 반대 포트로 폴백
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
    return path


# 3️⃣ UI 클래스
class UnifiedUnrealEditorUI:
    def __init__(self):
        self.client = UnrealSocketClient()
        # 첫 연결은 에디터(9998) 힌트
        self.client.mode_hint = "EDITOR"
        self.client._quick_probe()

        self.root = tk.Tk()
        self.root.title("🎮 Unreal Editor Control (Low-Latency)")

        self.selected_actor = None
        self.selected_slot = None

        # 상태값
        self.position = {"X": 0.0, "Y": 0.0, "Z": 0.0}
        self.scale    = {"X": 1.0, "Y": 1.0, "Z": 1.0}

        # 디바운서 핸들
        self._move_after  = None
        self._scale_after = None
        self._tick_ms     = 33  # 30Hz

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

        # 위치 이동
        tk.Label(self.root, text="🧭 액터 위치 이동").pack()
        pos_frame = tk.Frame(self.root); pos_frame.pack()

        self.pos_x = tk.Scale(pos_frame, from_=-500, to=500, resolution=10,
                              orient=tk.HORIZONTAL, label="X",
                              command=lambda v: self.on_pos_slider_change("X", int(v)))
        self.pos_x.set(0); self.pos_x.pack(side=tk.LEFT)

        self.pos_y = tk.Scale(pos_frame, from_=-50, to=50, resolution=10,
                              orient=tk.HORIZONTAL, label="Y",
                              command=lambda v: self.on_pos_slider_change("Y", int(v)))
        self.pos_y.set(0); self.pos_y.pack(side=tk.LEFT)

        self.pos_z = tk.Scale(pos_frame, from_=-50, to=50, resolution=10,
                              orient=tk.HORIZONTAL, label="Z",
                              command=lambda v: self.on_pos_slider_change("Z", int(v)))
        self.pos_z.set(0); self.pos_z.pack(side=tk.LEFT)

        # 스케일 조절 (바로 아래)
        tk.Label(self.root, text="📏 액터 스케일 조절").pack()
        scl_frame = tk.Frame(self.root); scl_frame.pack()

        self.scl_x = tk.Scale(scl_frame, from_=0.1, to=5.0, resolution=0.1,
                              orient=tk.HORIZONTAL, label="SX",
                              command=lambda v: self.on_scale_slider_change("X", float(v)))
        self.scl_x.set(1.0); self.scl_x.pack(side=tk.LEFT)

        self.scl_y = tk.Scale(scl_frame, from_=0.1, to=5.0, resolution=0.1,
                              orient=tk.HORIZONTAL, label="SY",
                              command=lambda v: self.on_scale_slider_change("Y", float(v)))
        self.scl_y.set(1.0); self.scl_y.pack(side=tk.LEFT)

        self.scl_z = tk.Scale(scl_frame, from_=0.1, to=5.0, resolution=0.1,
                              orient=tk.HORIZONTAL, label="SZ",
                              command=lambda v: self.on_scale_slider_change("Z", float(v)))
        self.scl_z.set(1.0); self.scl_z.pack(side=tk.LEFT)

        # 텍스처/머티리얼
        tk.Label(self.root, text="🎨 텍스처/머티리얼 정보").pack()
        self.texture_info = tk.Text(self.root, height=15, width=60)
        self.texture_info.pack()

        # 예시 스폰 버튼
        tk.Button(self.root, text="🧱 에셋 스폰(에디터)",
                  command=lambda: self.spawn_existing_asset("/Game/Scripts/ExportedFBX/house")).pack(pady=4)

        # Preset
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

    # ✅ 액터 목록
    def load_actor_list(self):
        result = self.client.send_command("LIST_STATIC")  # 지원 안 하면 서버에서 LIST로 폴백하도록 구현해둠
        if not result.strip():
            result = self.client.send_command("LIST")
        actors = [a for a in result.strip().splitlines() if a]
        self.actor_listbox.delete(0, tk.END)
        for actor in actors:
            self.actor_listbox.insert(tk.END, actor)

    # ✅ 액터 선택 시: 위치/스케일/머티리얼 갱신
    def on_actor_selected(self, event):
        sel = self.actor_listbox.curselection()
        if not sel:
            return
        self.selected_actor = self.actor_listbox.get(sel[0])

        # 위치
        loc = self.client.send_command(f"GET_LOCATION {self.selected_actor}")
        p = loc.strip().split()
        if len(p) == 4 and p[0] == "Location:":
            self.position["X"] = float(p[1]); self.position["Y"] = float(p[2]); self.position["Z"] = float(p[3])

        # 스케일
        sres = self.client.send_command(f"GET_SCALE {self.selected_actor}")
        sp = sres.strip().split()
        if len(sp) == 4 and sp[0] == "Scale:":
            self.scale["X"] = float(sp[1]); self.scale["Y"] = float(sp[2]); self.scale["Z"] = float(sp[3])
            self.scl_x.set(self.scale["X"]); self.scl_y.set(self.scale["Y"]); self.scl_z.set(self.scale["Z"])

        # 머티리얼/텍스처
        tex = self.client.send_command(f"GET_TEXTURES {self.selected_actor}")
        self.texture_info.delete("1.0", tk.END)
        self.texture_info.insert(tk.END, tex)

        slot_lines = [line for line in tex.splitlines() if line.startswith("Material Slot")]
        self.render_slot_buttons(len(slot_lines))

    # ✅ 머티리얼 슬롯 버튼
    def render_slot_buttons(self, count):
        for w in self.slot_frame.winfo_children():
            w.destroy()
        for idx in range(count):
            btn = tk.Button(self.slot_frame, text=f"Slot {idx}",
                            command=partial(self.on_slot_selected, idx), width=12)
            row, col = divmod(idx, 2)
            btn.grid(row=row, column=col, padx=5, pady=5)

    # ✅ 머티리얼 변경
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
        cmd = f'SET_MATERIAL {self.selected_actor} {self.selected_slot} "{unreal_path}"'
        resp = self.client.send_command(cmd)
        self.texture_info.insert(tk.END, f"\n{resp}\n")

    # ✅ 이동: 디바운스(30Hz)
    def on_pos_slider_change(self, axis, value):
        if value == 0:
            return
        self.position[axis] += value
        # 증분 슬라이더는 0으로 복귀
        if axis == "X": self.pos_x.set(0)
        elif axis == "Y": self.pos_y.set(0)
        elif axis == "Z": self.pos_z.set(0)
        # 디바운스 스케줄
        if self._move_after:
            self.root.after_cancel(self._move_after)
        self._move_after = self.root.after(self._tick_ms, self._flush_move)

    def _flush_move(self):
        self._move_after = None
        if not self.selected_actor:
            return
        x, y, z = self.position["X"], self.position["Y"], self.position["Z"]
        resp = self.client.send_command(f"MOVE {self.selected_actor} {x} {y} {z}")
        if resp:
            self.texture_info.insert(tk.END, f"\n{resp.strip()}\n")

    # ✅ 스케일: 디바운스(30Hz, 절대값)
    def on_scale_slider_change(self, axis, value):
        self.scale[axis] = float(value)
        if self._scale_after:
            self.root.after_cancel(self._scale_after)
        self._scale_after = self.root.after(self._tick_ms, self._flush_scale)

    def _flush_scale(self):
        self._scale_after = None
        if not self.selected_actor:
            return
        sx, sy, sz = self.scale["X"], self.scale["Y"], self.scale["Z"]
        resp = self.client.send_command(f"SCALE {self.selected_actor} {sx} {sy} {sz}")
        if resp:
            self.texture_info.insert(tk.END, f"\n{resp.strip()}\n")

    # ✅ 에디터 파이썬 실행 강제 (필요 시)
    def send_editor_command(self, command: str):
        if not self.client.connect(self.client.ports[1]):  # 9998
            return "❌ Unreal Editor와 연결되지 않았습니다."
        return self.client.send_command(command)

    # ✅ 예시 스폰
    def spawn_existing_asset(self, unreal_asset_path: str):
        if not self.client.connect(self.client.ports[1]):  # 9998
            self.texture_info.insert(tk.END, "\n❌ Unreal Editor와 연결되지 않았습니다.\n")
            return
        script_path = "D:/git/XR-Studio/MyProjectCamera/Content/Python/editor_spawn_actor.py"
        cmd = f'py "{script_path}" --asset "{unreal_asset_path}" --spawn --x 1700 --y 0 --z 10'
        resp = self.client.send_command(cmd)
        self.texture_info.insert(tk.END, f"\n{resp}\n")

    # ✅ Preset 저장/로드
    def save_preset_btn(self):
        name = (self.preset_name_var.get() or "Preset").strip()
        script_path = "D:/git/XR-Studio/MyProjectCamera/Content/Python/editor_scene_preset.py"
        # PIE면 런타임, 아니면 에디터 py
        if self.client.connect(self.client.ports[0]):  # 9999
            resp = self.client.send_command(f"SAVE_PRESET {name}")
        else:
            cmd = f'py "{script_path}" --save-preset --name "{name}"'
            if self.only_selected_var.get():
                cmd += " --only-selected"
            resp = self.send_editor_command(cmd)
        self.texture_info.insert(tk.END, f"\n{resp}\n")

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
            resp = self.send_editor_command(cmd)
        self.texture_info.insert(tk.END, f"\n{resp}\n")

    # ✅ GUI 실행
    def run(self):
        self.root.mainloop()
        self.client.close()


# 실행
if __name__ == "__main__":
    ui = UnifiedUnrealEditorUI()
    ui.run()
