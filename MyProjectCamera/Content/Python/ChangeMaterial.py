import os
import socket
import time
import tkinter as tk
from tkinter import filedialog
from functools import partial

# ─────────────────────────────────────────────────────
# 저지연 소켓 클라이언트
class UnrealSocketClient:
    def __init__(self, ip='127.0.0.1', ports=[9999, 9998]):
        self.server_ip = ip
        self.ports = ports  # [PIE, EDITOR]
        self.sock = None
        self.current_port = None
        self.connect_timeout = 0.15
        self.recv_timeout    = 0.40
        self.mode_hint = "EDITOR"

    def close(self):
        if self.sock:
            try:
                try: self.sock.shutdown(socket.SHUT_RDWR)
                except Exception: pass
                self.sock.close()
            finally:
                self.sock = None
                self.current_port = None

    def _new_socket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.settimeout(self.connect_timeout)
        return s

    def connect(self, port):
        if self.sock and self.current_port == port:
            return True
        self.close()
        try:
            s = self._new_socket()
            s.connect((self.server_ip, port))
            s.settimeout(self.recv_timeout)
            self.sock = s
            self.current_port = port
            self.mode_hint = "PIE" if port == self.ports[0] else "EDITOR"
            print(f"✅ 연결 {self.server_ip}:{port} (mode={self.mode_hint})")
            return True
        except Exception as e:
            print(f"❌ 연결 실패 {port}: {e}")
            self.sock = None
            self.current_port = None
            return False

    def _quick_probe(self):
        order = [self.ports[1], self.ports[0]] if self.mode_hint == "EDITOR" else [self.ports[0], self.ports[1]]
        for p in order:
            if self.connect(p): return True
        return False

    def _recv_until_newline(self):
        end = time.time() + self.recv_timeout
        chunks = []
        while time.time() < end:
            try:
                data = self.sock.recv(4096)
                if not data: break
                chunks.append(data)
                if b'\n' in data: break
            except socket.timeout:
                break
            except Exception as e:
                return f"❌ 수신 오류: {e}"
        if not chunks: return ""
        try:
            return b"".join(chunks).decode("utf-8", "ignore")
        except Exception:
            return "(binary)"

    def _send_and_get(self, payload: str):
        self.sock.sendall((payload.strip() + "\n").encode("utf-8"))
        return self._recv_until_newline()

    def _auto_switch_if_needed(self, resp: str):
        if not resp: return False
        if "SWITCH:PIE" in resp or "ERR PIE" in resp:
            if self.connect(self.ports[0]): self.mode_hint = "PIE"; return True
        if "SWITCH:EDITOR" in resp:
            if self.connect(self.ports[1]): self.mode_hint = "EDITOR"; return True
        return False

    def send_command(self, command: str):
        try:
            is_editor_command = command.startswith("py ") or \
                                command.startswith("SPAWN_ASSET") or \
                                command.startswith("IMPORT_FBX")

            if not self.sock:
                self.mode_hint = "EDITOR" if is_editor_command else self.mode_hint
                if not self._quick_probe(): return "❌ 연결 실패"

            resp = self._send_and_get(command)
            if self._auto_switch_if_needed(resp):
                resp = self._send_and_get(command)
            if not resp:
                other = self.ports[0] if self.current_port == self.ports[1] else self.ports[1]
                if self.connect(other): resp = self._send_and_get(command)
            return resp or "⏳ (no response)"
        except Exception as e:
            try:
                other = self.ports[0] if self.current_port == self.ports[1] else self.ports[1]
                if self.connect(other): return self._send_and_get(command)
            except Exception as e2:
                return f"❌ 통신 오류: {e2}"
            return f"❌ 통신 오류: {e}"


# 경로 변환
def convert_to_unreal_path(filepath):
    path = filepath.replace("D:/git/XR-Studio/MyProjectCamera/Content", "/Game")
    path = path.replace("\\", "/")
    path = path.replace(".uasset", "")
    return path


# ─────────────────────────────────────────────────────
# UI
class UnifiedUnrealEditorUI:
    def __init__(self):
        self.client = UnrealSocketClient()
        self.client.mode_hint = "EDITOR"
        self.client._quick_probe()

        self.root = tk.Tk()
        self.root.title("🎮 Unreal Editor Control (Labels)")

        # 리스트 항목: [(label, name), ...]
        self.actor_entries = []
        self.selected_actor_name = None  # 명령에 사용할 내부 Name
        self.selected_actor_label = None

        self.position = {"X": 0.0, "Y": 0.0, "Z": 0.0}
        self.scale    = {"X": 1.0, "Y": 1.0, "Z": 1.0}

        self._move_after  = None
        self._scale_after = None
        self._tick_ms     = 10  # 30Hz

        self.preset_name_var = tk.StringVar(value="MyPreset")
        self.only_selected_var = tk.BooleanVar(value=False)
        self.offset_x_var = tk.DoubleVar(value=0.0)
        self.offset_y_var = tk.DoubleVar(value=0.0)
        self.offset_z_var = tk.DoubleVar(value=0.0)

        self.build_gui()
        self.client.send_command("LOG_VERBOSE 0")

    def build_gui(self):
        tk.Button(self.root, text="📡 액터 목록 불러오기", command=self.load_actor_list).pack()
        self.actor_listbox = tk.Listbox(self.root, height=10, width=40)
        self.actor_listbox.pack()
        self.actor_listbox.bind("<<ListboxSelect>>", self.on_actor_selected)

        # 위치 이동
        tk.Label(self.root, text="🧭 액터 위치 이동").pack()
        pos_frame = tk.Frame(self.root); pos_frame.pack()

        self.pos_x = tk.Scale(pos_frame, from_=-100, to=100, resolution=10,
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

        for w in (self.pos_x, self.pos_y, self.pos_z):
            w.bind("<ButtonRelease-1>", self.on_pos_release)

        # 스케일
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

        for w in (self.scl_x, self.scl_y, self.scl_z):
            w.bind("<ButtonRelease-1>", self.on_scale_release)

        # 텍스처/머티리얼
        tk.Label(self.root, text="🎨 머티리얼/텍스처 정보").pack()
        # 상단: 텍스처/머티리얼 정보
        self.texture_info = tk.Text(self.root, height=12, width=60)
        self.texture_info.pack()


        # 하단: 로그/결과 출력
        tk.Label(self.root, text="📄 명령 로그").pack()
        self.log_output = tk.Text(self.root, height=10, width=60, fg="gray10", bg="#f0f0f0")
        self.log_output.pack()

        tk.Button(self.root, text="📂 에셋 선택 후 스폰", command=self.spawn_asset_via_file).pack(pady=4)


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

        self.slot_frame = tk.Frame(self.root)
        self.slot_frame.pack(pady=5)


    # 액터 목록: "Label|Name" 포맷 지원
    def load_actor_list(self):
        result = self.client.send_command("LIST_STATIC")
        if not result.strip():
            result = self.client.send_command("LIST")
        self.actor_entries = []
        self.actor_listbox.delete(0, tk.END)
        for line in result.strip().splitlines():
            if not line: continue
            if "|" in line:
                label, name = line.split("|", 1)
            else:
                label = name = line
            label = label.strip(); name = name.strip()
            self.actor_entries.append((label, name))
            self.actor_listbox.insert(tk.END, label)  # UI엔 Label만

    # 액터 선택 → 내부 Name으로 명령 실행
    def on_actor_selected(self, _evt):
        sel = self.actor_listbox.curselection()
        if not sel: return
        idx = sel[0]
        self.selected_actor_label, self.selected_actor_name = self.actor_entries[idx]

        # 위치/스케일 동기화
        loc = self.client.send_command(f"GET_LOCATION {self.selected_actor_name}")
        p = loc.strip().split()
        if len(p) == 4 and p[0] == "Location:":
            self.position["X"] = float(p[1]); self.position["Y"] = float(p[2]); self.position["Z"] = float(p[3])

        sres = self.client.send_command(f"GET_SCALE {self.selected_actor_name}")
        sp = sres.strip().split()
        if len(sp) == 4 and sp[0] == "Scale:":
            self.scale["X"] = float(sp[1]); self.scale["Y"] = float(sp[2]); self.scale["Z"] = float(sp[3])
            self.scl_x.set(self.scale["X"]); self.scl_y.set(self.scale["Y"]); self.scl_z.set(self.scale["Z"])

        # 슬롯만(가벼운 모드)
        slots = self.client.send_command(f"GET_MATERIAL_SLOTS {self.selected_actor_name}")
        self.texture_info.delete("1.0", tk.END)
        self.texture_info.insert(tk.END, slots)

        lines = [line for line in slots.splitlines() if line.startswith("Material Slot")]
        self.render_slot_buttons(len(lines))

    # 슬롯 버튼(교체 + 상세)
    def render_slot_buttons(self, count):
        for w in self.slot_frame.winfo_children():
            w.destroy()
        for idx in range(count):
            fr = tk.Frame(self.slot_frame)
            fr.grid(row=idx, column=0, sticky="w", padx=4, pady=2)
            tk.Button(fr, text=f"Slot {idx} 바꾸기", width=16,
                      command=partial(self.on_slot_selected, idx)).pack(side=tk.LEFT)
            tk.Button(fr, text="🔎", width=3,
                      command=partial(self.show_slot_textures, idx)).pack(side=tk.LEFT, padx=4)

    def show_slot_textures(self, idx):
        if not self.selected_actor_name: return
        out = self.client.send_command(f"GET_TEXTURES_SLOT {self.selected_actor_name} {idx}")
        self.texture_info.insert(tk.END, "\n" + out + "\n")

    def on_slot_selected(self, slot_index):
        if not self.selected_actor_name: return
        filepath = filedialog.askopenfilename(
            title="교체할 머티리얼 선택",
            initialdir="D:/git/XR-Studio/MyProjectCamera/Content/Textures",
            filetypes=[("머티리얼 파일", "*.uasset")]
        )
        if not filepath: return
        upath = convert_to_unreal_path(filepath).strip()
        if not upath:
            self.texture_info.insert(tk.END, "\n❌ 경로 변환 실패\n")
            return
        cmd = f'SET_MATERIAL {self.selected_actor_name} {slot_index} "{upath}"'
        resp = self.client.send_command(cmd)
        self.log_output.insert(tk.END, f"\n{resp}\n")

    # 위치/스케일 (디바운스 + 커밋 로그)
    def on_pos_slider_change(self, axis, value):
        if not self.selected_actor_name:
            return
        try:
            speed_multiplier = 0.1  # ← 여기서 속도 조절
            delta = float(value) * speed_multiplier
            self.position[axis] += delta
            getattr(self, f"pos_{axis.lower()}").set(0)
            if self._move_after:
                self.root.after_cancel(self._move_after)
            self._move_after = self.root.after(self._tick_ms, self._flush_move)
        except Exception as e:
            print(f"❌ 이동 오류: {e}")


    def _flush_move(self):
        self._move_after = None
        if not self.selected_actor_name: return
        x, y, z = self.position["X"], self.position["Y"], self.position["Z"]
        self.client.send_command(f"MOVE {self.selected_actor_name} {x} {y} {z}")

    def on_pos_release(self, _evt):
        if not self.selected_actor_name: return
        x, y, z = self.position["X"], self.position["Y"], self.position["Z"]
        resp = self.client.send_command(f"MOVE_COMMIT {self.selected_actor_name} {x} {y} {z}")
        if resp:
            self.log_output.insert(tk.END, f"\n{resp.strip()}\n")



    def on_scale_slider_change(self, axis, value):
        if not self.selected_actor_name: return
        self.scale[axis] = float(value)
        if self._scale_after: self.root.after_cancel(self._scale_after)
        self._scale_after = self.root.after(self._tick_ms, self._flush_scale)

    def _flush_scale(self):
        self._scale_after = None
        if not self.selected_actor_name: return
        sx, sy, sz = self.scale["X"], self.scale["Y"], self.scale["Z"]
        self.client.send_command(f"SCALE {self.selected_actor_name} {sx} {sy} {sz}")

    def on_scale_release(self, _evt):
        if not self.selected_actor_name: return
        sx, sy, sz = self.scale["X"], self.scale["Y"], self.scale["Z"]
        resp = self.client.send_command(f"SCALE_COMMIT {self.selected_actor_name} {sx} {sy} {sz}")
        if resp:
            self.log_output.insert(tk.END, f"\n{resp.strip()}\n")
    

    # 에디터 명령
    def send_editor_command(self, command: str):
        if not self.client.connect(self.client.ports[1]):  # 9998
            return "❌ Unreal Editor와 연결되지 않았습니다."
        return self.client.send_command(command)

    # 예시 스폰
    def spawn_asset_via_file(self):
        filepath = filedialog.askopenfilename(
            title="스폰할 에셋 선택 (.uasset)",
            initialdir="D:/git/XR-Studio/MyProjectCamera/Content/Scripts/ExportedFBX",
            filetypes=[("Unreal Asset", "*.uasset")]
        )
        if not filepath:
            return

        unreal_path = convert_to_unreal_path(filepath)
        label = os.path.splitext(os.path.basename(filepath))[0]

        if not self.client.connect(self.client.ports[1]):  # Editor port
            self.log_output.insert(tk.END, "\n❌ Unreal Editor와 연결되지 않았습니다.\n")
            return

        # 선택한 에셋 경로로 스폰
        script_path = "D:/git/XR-Studio/MyProjectCamera/Content/Python/editor_spawn_actor.py"
        cmd = f'py "{script_path}" --asset "{unreal_path}" --spawn --x 1700 --y 0 --z 10 --label "{label}"'
        resp = self.client.send_command(cmd)
        self.log_output.insert(tk.END, f"\n{resp}\n")


    # 프리셋
    def save_preset_btn(self):
        name = (self.preset_name_var.get() or "Preset").strip()
        script_path = "D:/git/XR-Studio/MyProjectCamera/Content/Python/editor_scene_preset.py"
        if self.client.connect(self.client.ports[0]):  # 9999
            resp = self.client.send_command(f"SAVE_PRESET {name}")
        else:
            cmd = f'py "{script_path}" --save-preset --name "{name}"'
            if self.only_selected_var.get(): cmd += " --only-selected"
            resp = self.send_editor_command(cmd)
        self.log_output.insert(tk.END, f"\n{resp}\n")

    def load_preset_btn(self):
        preset_dir = r"D:\git\XR-Studio\MyProjectCamera\Saved\ScenePresets"
        filepath = filedialog.askopenfilename(
            title="로드할 프리셋(.json) 선택",
            initialdir=preset_dir,
            filetypes=[("Scene Preset JSON", "*.json")]
        )
        if not filepath: return
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
        self.log_output.insert(tk.END, f"\n{resp}\n")

    def run(self):
        self.root.mainloop()
        self.client.close()


if __name__ == "__main__":
    ui = UnifiedUnrealEditorUI()
    ui.run()
