import os
import socket
import time
import glob
import tkinter as tk
from tkinter import filedialog, messagebox
from functools import partial

# ===============================
# Project paths (edit if needed)
# ===============================
# Unreal "Saved/ScenePresets" absolute directory on your machine
PRESET_DIR = r"D:\git\XR-Studio\MyProjectCamera\Saved\ScenePresets"
# Default content roots for conven ience
DEFAULT_ASSET_PICKER_DIR = r"D:\git\XR-Studio\MyProjectCamera\Content"
DEFAULT_TEXTURE_DIR      = r"D:\git\XR-Studio\MyProjectCamera\Content\Textures"
DEFAULT_FBX_EXPORT_DIR   = r"D:\git\XR-Studio\MyProjectCamera\Content\Scripts\ExportedFBX"

# Python scripts inside Unreal project
EDITOR_SCRIPT_SPAWN  = r"D:\git\XR-Studio\MyProjectCamera\Content\Python\editor_spawn_actor.py"
EDITOR_SCRIPT_PRESET = r"D:\git\XR-Studio\MyProjectCamera\Content\Python\editor_scene_preset.py"

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
                                command.startswith("IMPORT_FBX") or \
                                command.startswith("LIST") or \
                                command.startswith("GET") or \
                                command.startswith("SET") or \
                                command.startswith("MOVE")

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
    path = filepath.replace(DEFAULT_ASSET_PICKER_DIR, "/Game")
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
        self.root.title("🎮 Unreal Editor Control (Multi-Select + Preset UX)")

        # 리스트 항목: [(label, name), ...]
        self.actor_entries = []
        self.selected_actor_names = []  # 여러 개

        self.position = {"X": 0.0, "Y": 0.0, "Z": 0.0}
        self.scale    = {"X": 1.0, "Y": 1.0, "Z": 1.0}

        self._move_after  = None
        self._scale_after = None
        self._tick_ms     = 10  # 30~60Hz 정도

        self.preset_name_var = tk.StringVar(value="MyPreset")
        self.only_selected_var = tk.BooleanVar(value=False)
        self.offset_x_var = tk.DoubleVar(value=0.0)
        self.offset_y_var = tk.DoubleVar(value=0.0)
        self.offset_z_var = tk.DoubleVar(value=0.0)

                # 드래그 제스처 상태
        self._drag_active = False
        self._drag_mode = None           # "move" | "scale"
        self._drag_last = (0, 0)

        # 누적량 (상대)
        self._move_accum = [0.0, 0.0]    # ΔX, ΔY (Z제외)
        self._scale_accum_factor = 1.0   # 누적 배율(기본 1.0)

        # 감도
        self._drag_speed_move_x = 1.0    # 픽셀당 월드 유닛 (X)
        self._drag_speed_move_y = 1.0    # 픽셀당 월드 유닛 (Y)
        self._drag_speed_scale  = 0.01   # 픽셀당 배율 변화량 (dx만 사용)

        # 선택 시점 기준값(멀티 지원)
        self._baseline_loc = {}          # {actor: (x,y,z)}
        self._baseline_scale = {}        # {actor: (sx,sy,sz)}


        self.build_gui()
        self.client.send_command("LOG_VERBOSE 0")

    # ---------- GUI ----------
    def build_gui(self):
    # ─────────────────────────────────────────────────────────
    # 두 칼럼 컨테이너
    # ─────────────────────────────────────────────────────────
        main = tk.Frame(self.root)
        main.pack(fill="both", expand=True)
        main.grid_columnconfigure(0, weight=3)   # 왼쪽(액터/컨트롤)
        main.grid_columnconfigure(1, weight=2)   # 오른쪽(Scene Preset)
        main.grid_rowconfigure(0, weight=1)

        # =========================
        # LEFT COLUMN (actors & ops)
        # =========================
        left = tk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(6,4), pady=6)
        left.grid_columnconfigure(0, weight=1)
        # 리스트, 텍스트, 로그 영역이 창 크기에 맞춰 늘어나도록
        left.grid_rowconfigure(1, weight=1)   # list_wrap
        left.grid_rowconfigure(8, weight=1)   # tex_wrap  (아래에서 row=8로 조정)
        left.grid_rowconfigure(13, weight=1)  # log_wrap  (아래에서 row=13로 조정)

        # 상단 바: 불러오기 + 검색
        topbar = tk.Frame(left)
        topbar.grid(row=0, column=0, sticky="ew")
        tk.Button(topbar, text="📡 액터 목록 불러오기", command=self.load_actor_list).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Label(topbar, text="검색:").pack(side=tk.LEFT, padx=(10,2))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.render_actor_list())
        tk.Entry(topbar, textvariable=self.search_var, width=18).pack(side=tk.LEFT)

        # 액터 리스트(+스크롤)
        list_wrap = tk.Frame(left)
        list_wrap.grid(row=1, column=0, sticky="nsew", pady=(4,6))
        list_wrap.grid_columnconfigure(0, weight=1)
        list_wrap.grid_rowconfigure(0, weight=1)
        self.actor_listbox = tk.Listbox(list_wrap, height=12, selectmode=tk.EXTENDED)
        self.actor_listbox.grid(row=0, column=0, sticky="nsew")
        sb_list = tk.Scrollbar(list_wrap, orient="vertical", command=self.actor_listbox.yview)
        sb_list.grid(row=0, column=1, sticky="ns")
        self.actor_listbox.config(yscrollcommand=sb_list.set)
        self.actor_listbox.bind("<<ListboxSelect>>", self.on_actor_selected)

        # 위치 이동
        tk.Label(left, text="🧭 액터 위치 이동 (여러 개 일괄 적용)").grid(row=2, column=0, sticky="w")
        pos_frame = tk.Frame(left); pos_frame.grid(row=3, column=0, sticky="ew")
        self.pos_x = tk.Scale(pos_frame, from_=-100, to=100, resolution=10,
                              orient=tk.HORIZONTAL, label="X",
                              command=lambda v: self.on_pos_slider_change("X", int(v)))
        self.pos_x.set(0); self.pos_x.pack(side=tk.LEFT, expand=True, fill="x")
        self.pos_y = tk.Scale(pos_frame, from_=-50, to=50, resolution=10,
                              orient=tk.HORIZONTAL, label="Y",
                              command=lambda v: self.on_pos_slider_change("Y", int(v)))
        self.pos_y.set(0); self.pos_y.pack(side=tk.LEFT, expand=True, fill="x")
        self.pos_z = tk.Scale(pos_frame, from_=-50, to=50, resolution=10,
                              orient=tk.HORIZONTAL, label="Z",
                              command=lambda v: self.on_pos_slider_change("Z", int(v)))
        self.pos_z.set(0); self.pos_z.pack(side=tk.LEFT, expand=True, fill="x")
        for w in (self.pos_x, self.pos_y, self.pos_z):
            w.bind("<ButtonRelease-1>", self.on_pos_release)

        # 스케일
        tk.Label(left, text="📏 액터 스케일 조절 (여러 개 일괄 적용)").grid(row=4, column=0, sticky="w", pady=(6,0))
        scl_frame = tk.Frame(left); scl_frame.grid(row=5, column=0, sticky="ew")
        self.scl_x = tk.Scale(scl_frame, from_=0.1, to=5.0, resolution=0.1,
                              orient=tk.HORIZONTAL, label="SX",
                              command=lambda v: self.on_scale_slider_change("X", float(v)))
        self.scl_x.set(1.0); self.scl_x.pack(side=tk.LEFT, expand=True, fill="x")
        self.scl_y = tk.Scale(scl_frame, from_=0.1, to=5.0, resolution=0.1,
                              orient=tk.HORIZONTAL, label="SY",
                              command=lambda v: self.on_scale_slider_change("Y", float(v)))
        self.scl_y.set(1.0); self.scl_y.pack(side=tk.LEFT, expand=True, fill="x")
        self.scl_z = tk.Scale(scl_frame, from_=0.1, to=5.0, resolution=0.1,
                              orient=tk.HORIZONTAL, label="SZ",
                              command=lambda v: self.on_scale_slider_change("Z", float(v)))
        self.scl_z.set(1.0); self.scl_z.pack(side=tk.LEFT, expand=True, fill="x")
        for w in (self.scl_x, self.scl_y, self.scl_z):
            w.bind("<ButtonRelease-1>", self.on_scale_release)

        # 🔽 여기(row=6)는 스케일 매크로 버튼만 배치
        macro_frame = tk.Frame(left)
        macro_frame.grid(row=6, column=0, sticky="w", pady=(4, 0))
        tk.Button(macro_frame, text="작게 (80%)",
                  command=lambda: self.apply_scale_macro("small")).pack(side=tk.LEFT, padx=(0,6))
        tk.Button(macro_frame, text="보통 (100%)",
                  command=lambda: self.apply_scale_macro("normal")).pack(side=tk.LEFT, padx=(0,6))
        tk.Button(macro_frame, text="크게 (120%)",
                  command=lambda: self.apply_scale_macro("large")).pack(side=tk.LEFT)

        # ✅ 머티리얼/텍스처 섹션은 row 번호를 한 칸씩 밀기 (7부터 시작)
        tk.Label(left, text="🎨 머티리얼/텍스처 정보 (첫 번째 선택 대상 기준)")\
          .grid(row=7, column=0, sticky="w", pady=(8,0))

        tex_wrap = tk.Frame(left); tex_wrap.grid(row=8, column=0, sticky="nsew")
        tex_wrap.grid_columnconfigure(0, weight=1); tex_wrap.grid_rowconfigure(0, weight=1)
        self.texture_info = tk.Text(tex_wrap, height=8, width=60)
        self.texture_info.grid(row=0, column=0, sticky="nsew")
        sb_tex = tk.Scrollbar(tex_wrap, orient="vertical", command=self.texture_info.yview)
        sb_tex.grid(row=0, column=1, sticky="ns")
        self.texture_info.config(yscrollcommand=sb_tex.set)

        # 슬롯 버튼 영역
        self.slot_frame = tk.Frame(left)
        self.slot_frame.grid(row=9, column=0, sticky="w", pady=6)

        # 일괄 머티리얼 교체 + 스폰 버튼
        tk.Button(left, text="🎯 선택된 액터들 → 슬롯 머티리얼 교체", command=self.bulk_replace_material)\
          .grid(row=10, column=0, sticky="ew", pady=(0,6))
        tk.Button(left, text="📂 에셋 선택 후 스폰 (Editor)", command=self.spawn_asset_via_file)\
          .grid(row=11, column=0, sticky="ew")

        # 로그(+스크롤) — 아래로 한 칸씩 밀기
        tk.Label(left, text="📄 명령 로그").grid(row=12, column=0, sticky="w", pady=(8,0))
        log_wrap = tk.Frame(left); log_wrap.grid(row=13, column=0, sticky="nsew")
        log_wrap.grid_columnconfigure(0, weight=1); log_wrap.grid_rowconfigure(0, weight=1)
        self.log_output = tk.Text(log_wrap, height=10, width=60, fg="gray10", bg="#f0f0f0")
        self.log_output.grid(row=0, column=0, sticky="nsew")
        sb_log = tk.Scrollbar(log_wrap, orient="vertical", command=self.log_output.yview)
        sb_log.grid(row=0, column=1, sticky="ns")
        self.log_output.config(yscrollcommand=sb_log.set)


        # =========================
        # RIGHT COLUMN (scene preset)
        # =========================
        right = tk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew", padx=(4,6), pady=6)
        right.grid_columnconfigure(0, weight=1)

        preset_frame = tk.LabelFrame(right, text="📦 Scene Preset (런타임 우선, Editor 대체)")
        preset_frame.grid(row=0, column=0, sticky="nsew")
        preset_frame.grid_columnconfigure(0, weight=1)
        preset_frame.grid_columnconfigure(1, weight=1)

        # 좌: 프리셋 목록
        left_p = tk.Frame(preset_frame); left_p.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        left_p.grid_columnconfigure(0, weight=1); left_p.grid_rowconfigure(1, weight=1)
        tk.Label(left_p, text="프리셋 목록").grid(row=0, column=0, sticky="w")
        self.preset_listbox = tk.Listbox(left_p, height=16)
        self.preset_listbox.grid(row=1, column=0, sticky="nsew")
        sb_preset = tk.Scrollbar(left_p, orient="vertical", command=self.preset_listbox.yview)
        sb_preset.grid(row=1, column=1, sticky="ns")
        self.preset_listbox.config(yscrollcommand=sb_preset.set)
        tk.Button(left_p, text="🔄 목록 새로고침", command=self.refresh_preset_list).grid(row=2, column=0, sticky="ew", pady=(4,0))

        # 우: 조작
        right_p = tk.Frame(preset_frame); right_p.grid(row=0, column=1, sticky="nsew", padx=8, pady=4)
        r = 0
        tk.Label(right_p, text="이름").grid(row=r, column=0, sticky="e", padx=4, pady=2)
        tk.Entry(right_p, textvariable=self.preset_name_var, width=24).grid(row=r, column=1, sticky="w", padx=4, pady=2)
        tk.Checkbutton(right_p, text="Only Selected(에디터 저장 시)", variable=self.only_selected_var)\
            .grid(row=r, column=2, sticky="w", padx=4)

        r += 1
        tk.Label(right_p, text="Offset X/Y/Z (로드)").grid(row=r, column=0, sticky="e", padx=4, pady=2)
        tk.Entry(right_p, textvariable=self.offset_x_var, width=6).grid(row=r, column=1, sticky="w", padx=(4,0))
        tk.Entry(right_p, textvariable=self.offset_y_var, width=6).grid(row=r, column=1, sticky="w", padx=(64,0))
        tk.Entry(right_p, textvariable=self.offset_z_var, width=6).grid(row=r, column=1, sticky="w", padx=(124,0))

        r += 1
        tk.Button(right_p, text="💾 Save Preset", command=self.save_preset_btn)\
            .grid(row=r, column=0, padx=4, pady=6, sticky="we")
        tk.Button(right_p, text="📥 Load Preset", command=self.load_preset_btn)\
            .grid(row=r, column=1, padx=4, pady=6, sticky="we")
        tk.Button(right_p, text="🧹 Delete Preset", command=self.delete_preset_btn)\
            .grid(row=r, column=2, padx=4, pady=6, sticky="we")
        
            # ── 드래그 제스처 패널들 ─────────────────────────────────
        gesture_wrap = tk.Frame(left)
        gesture_wrap.grid(row=7, column=0, sticky="ew", pady=(6, 6))  # row 번호는 레이아웃에 맞춰 조정 가능

        # Move 패드
        move_pad = tk.Canvas(gesture_wrap, width=180, height=60, bg="#ECECEC", highlightthickness=1, highlightbackground="#BBBBBB")
        move_pad.pack(side=tk.LEFT, padx=(0,10))
        move_pad.create_text(90, 30, text="🖱️ Drag to MOVE", fill="#333333")

        # Scale 패드
        scale_pad = tk.Canvas(gesture_wrap, width=180, height=60, bg="#ECECEC", highlightthickness=1, highlightbackground="#BBBBBB")
        scale_pad.pack(side=tk.LEFT)
        scale_pad.create_text(90, 30, text="🖱️ Drag to SCALE", fill="#333333")

        # 바인딩
        move_pad.bind("<Button-1>",     lambda e: self._drag_start(e, "move"))
        move_pad.bind("<B1-Motion>",    lambda e: self._drag_motion(e))
        move_pad.bind("<ButtonRelease-1>", lambda e: self._drag_end())

        scale_pad.bind("<Button-1>",     lambda e: self._drag_start(e, "scale"))
        scale_pad.bind("<B1-Motion>",    lambda e: self._drag_motion(e))
        scale_pad.bind("<ButtonRelease-1>", lambda e: self._drag_end())


        # 초기 목록 로드
        self.refresh_preset_list()

    # ---------- 액터 목록/선택 ----------
    def load_actor_list(self):
        result = self.client.send_command("LIST_STATIC")
        if not result.strip():
            result = self.client.send_command("LIST")
        self.actor_entries = []
        for line in result.strip().splitlines():
            if not line: continue
            if "|" in line:
                label, name = line.split("|", 1)
            else:
                label = name = line
            label = label.strip(); name = name.strip()
            self.actor_entries.append((label, name))
        self.render_actor_list()

    def render_actor_list(self):
        query = (self.search_var.get() or "").lower()
        self.actor_listbox.delete(0, tk.END)
        for label, _name in self.actor_entries:
            if not query or query in label.lower():
                self.actor_listbox.insert(tk.END, label)

    def resolve_selected_actor_names(self):
        # map visual index -> underlying entries with filter
        query = (self.search_var.get() or "").lower()
        filtered = [e for e in self.actor_entries if (not query or query in e[0].lower())]
        sel = self.actor_listbox.curselection()
        names = []
        for i in sel:
            if 0 <= i < len(filtered):
                names.append(filtered[i][1])  # internal Name
        return names
    
    def _server_supports_get_textures_slot(self) -> bool:
    # 가벼운 프로빙: 존재하지 않는 액터/슬롯으로 호출해보고
    # '알 수 없는 명령'이 오면 미지원으로 간주
        probe = self.client.send_command("GET_TEXTURES_SLOT __no__ 0")
        return "알 수 없는 명령" not in (probe or "")

    def on_actor_selected(self, _evt):
        self.selected_actor_names = self.resolve_selected_actor_names()
        if not self.selected_actor_names:
            return

        # 대표 한 개(첫 번째)만 상세 동기화
        first = self.selected_actor_names[0]

        # 위치/스케일 동기화
        loc = self.client.send_command(f"GET_LOCATION {first}")
        p = loc.strip().split()
        if len(p) == 4 and p[0] == "Location:":
            self.position["X"] = float(p[1]); self.position["Y"] = float(p[2]); self.position["Z"] = float(p[3])

        sres = self.client.send_command(f"GET_SCALE {first}")
        sp = sres.strip().split()
        if len(sp) == 4 and sp[0] == "Scale:":
            self.scale["X"] = float(sp[1]); self.scale["Y"] = float(sp[2]); self.scale["Z"] = float(sp[3])
            self.scl_x.set(self.scale["X"]); self.scl_y.set(self.scale["Y"]); self.scl_z.set(self.scale["Z"])

        # 슬롯만(가벼운 모드)
        slots = self.client.send_command(f"GET_MATERIAL_SLOTS {first}")
        self.texture_info.delete("1.0", tk.END)
        self.texture_info.insert(tk.END, slots)

        lines = [line for line in slots.splitlines() if line.startswith("Material Slot")]
        self.render_slot_buttons(len(lines))
        self._baseline_loc.clear()
        self._baseline_scale.clear()
        for name in self.selected_actor_names:
            # 위치
            loc = self.client.send_command(f"GET_LOCATION {name}").strip().split()
            if len(loc) == 4 and loc[0] == "Location:":
                bx, by, bz = float(loc[1]), float(loc[2]), float(loc[3])
            else:
                bx, by, bz = 0.0, 0.0, 0.0
            self._baseline_loc[name] = (bx, by, bz)
            # 스케일
            sc = self.client.send_command(f"GET_SCALE {name}").strip().split()
            if len(sc) == 4 and sc[0] == "Scale:":
                sx, sy, sz = float(sc[1]), float(sc[2]), float(sc[3])
            else:
                sx, sy, sz = 1.0, 1.0, 1.0
            self._baseline_scale[name] = (sx, sy, sz)

        # 드래그 누적 초기화
        self._move_accum = [0.0, 0.0]
        self._scale_accum_factor = 1.0

    # ---------- 위치/스케일 (디바운스 & 일괄) ----------
    def on_pos_slider_change(self, axis, value):
        if not self.selected_actor_names:
            return
        try:
            speed_multiplier = 0.1
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
        if not self.selected_actor_names: return
        x, y, z = self.position["X"], self.position["Y"], self.position["Z"]
        for name in self.selected_actor_names:
            self.client.send_command(f"MOVE {name} {x} {y} {z}")

    def on_pos_release(self, _evt):
        if not self.selected_actor_names: return
        x, y, z = self.position["X"], self.position["Y"], self.position["Z"]
        for name in self.selected_actor_names:
            resp = self.client.send_command(f"MOVE_COMMIT {name} {x} {y} {z}")
            if resp:
                self.log_output.insert(tk.END, f"\n{name}: {resp.strip()}\n")

    def on_scale_slider_change(self, axis, value):
        if not self.selected_actor_names: return
        self.scale[axis] = float(value)
        if self._scale_after: self.root.after_cancel(self._scale_after)
        self._scale_after = self.root.after(self._tick_ms, self._flush_scale)

    def _flush_scale(self):
        self._scale_after = None
        if not self.selected_actor_names: return
        sx, sy, sz = self.scale["X"], self.scale["Y"], self.scale["Z"]
        for name in self.selected_actor_names:
            self.client.send_command(f"SCALE {name} {sx} {sy} {sz}")

    def _flush_move_drag(self):
    # 누적 Δ를 베이스라인에 더해 미리보기(MOVE)
        dx, dy = self._move_accum
        for name in self.selected_actor_names:
            bx, by, bz = self._baseline_loc.get(name, (0.0,0.0,0.0))
            nx, ny, nz = bx + dx, by + dy, bz
            self.client.send_command(f"MOVE {name} {nx} {ny} {nz}")

    def _flush_scale_drag(self):
        # 누적 배율로 미리보기(SCALE)
        f = self._scale_accum_factor
        for name in self.selected_actor_names:
            sx, sy, sz = self._baseline_scale.get(name, (1.0,1.0,1.0))
            nsx, nsy, nsz = sx * f, sy * f, sz * f
            self.client.send_command(f"SCALE {name} {nsx} {nsy} {nsz}")
    
    
    def on_scale_release(self, _evt):
        # 서버에 SCALE_COMMIT이 없는 경우가 있으므로, 다시 한 번 SCALE 전송 + 로그만 남김
        if not self.selected_actor_names: return
        sx, sy, sz = self.scale["X"], self.scale["Y"], self.scale["Z"]
        for name in self.selected_actor_names:
            resp = self.client.send_command(f"SCALE {name} {sx} {sy} {sz}")
            if resp:
                self.log_output.insert(tk.END, f"\n{name}: {resp.strip()}\n")


    def _get_scale_of(self, actor_name):
        """서버에서 현재 스케일을 읽어 float(tuple)로 반환. 실패 시 None."""
        res = self.client.send_command(f"GET_SCALE {actor_name}") or ""
        parts = res.strip().split()
        if len(parts) == 4 and parts[0] == "Scale:":
            try:
                return (float(parts[1]), float(parts[2]), float(parts[3]))
            except Exception:
                return None
        return None

    def apply_scale_macro(self, mode: str):
        """
        mode:
          - 'small'  : 현재 스케일 * 0.8 (상대 변경)
          - 'normal' : (1.0, 1.0, 1.0)로 고정 (절대 설정)
          - 'large'  : 현재 스케일 * 1.2 (상대 변경)
        선택된 모든 액터에 적용.
        """
        if not self.selected_actor_names:
            self.log_output.insert(tk.END, "\n⚠️ 액터를 먼저 선택하세요.\n")
            return
    
        if mode == "small":
            mul = 0.8
        elif mode == "large":
            mul = 1.2
        else:
            mul = None  # normal
    
        for name in self.selected_actor_names:
            if mul is None:
                # 보통(100%): 절대 스케일 1.0
                sx, sy, sz = 1.0, 1.0, 1.0
            else:
                cur = self._get_scale_of(name) or (1.0, 1.0, 1.0)
                sx, sy, sz = cur[0] * mul, cur[1] * mul, cur[2] * mul
    
            # 서버에 적용
            resp = self.client.send_command(f"SCALE {name} {sx} {sy} {sz}")
            if resp:
                self.log_output.insert(tk.END, f"\n{name}: {resp.strip()}\n")
    
        # 첫 번째 선택 항목 기준으로 UI 슬라이더 동기화
        first = self.selected_actor_names[0]
        cur = self._get_scale_of(first)
        if cur:
            self.scale["X"], self.scale["Y"], self.scale["Z"] = cur
            self.scl_x.set(cur[0]); self.scl_y.set(cur[1]); self.scl_z.set(cur[2])
        
    def _drag_start(self, event, mode: str):
        if not self.selected_actor_names:
            self.log_output.insert(tk.END, "\n⚠️ 액터를 먼저 선택하세요.\n")
            return
        self._drag_active = True
        self._drag_mode = mode  # "move" or "scale"
        self._drag_last = (event.x, event.y)
        # 누적 초기화
        self._move_accum = [0.0, 0.0]
        self._scale_accum_factor = 1.0

    def _drag_motion(self, event):
        if not self._drag_active or not self._drag_mode:
            return
        x, y = event.x, event.y
        lx, ly = self._drag_last
        dx, dy = (x - lx), (y - ly)
        self._drag_last = (x, y)

        if self._drag_mode == "move":
            # 좌←→우 = X, 위↑↓아래 = Y (Tk에서 위로 이동하면 dy<0)
            self._move_accum[0] += dx * self._drag_speed_move_x       # ΔX
            self._move_accum[1] += (-dy) * self._drag_speed_move_y     # ΔY (위로 드래그 = +Y)
            # 디바운스 송신
            if self._move_after:
                self.root.after_cancel(self._move_after)
            self._move_after = self.root.after(self._tick_ms, self._flush_move_drag)

        else:  # scale (수평만 사용)
            factor_delta = 1.0 + (dx * self._drag_speed_scale)
            if factor_delta <= 0.0:
                return
            self._scale_accum_factor *= factor_delta
            # 디바운스 송신
            if self._scale_after:
                self.root.after_cancel(self._scale_after)
            self._scale_after = self.root.after(self._tick_ms, self._flush_scale_drag)

    def _drag_end(self):
        if not self._drag_active:
            return
        mode = self._drag_mode
        self._drag_active = False
        self._drag_mode = None

        if mode == "move":
            # 최종 커밋
            dx, dy = self._move_accum
            for name in self.selected_actor_names:
                bx, by, bz = self._baseline_loc.get(name, (0.0,0.0,0.0))
                nx, ny, nz = bx + dx, by + dy, bz
                resp = self.client.send_command(f"MOVE_COMMIT {name} {nx} {ny} {nz}")
                if resp:
                    self.log_output.insert(tk.END, f"\n{name}: {resp.strip()}\n")
            # 베이스라인 갱신
            for n in self.selected_actor_names:
                bx, by, bz = self._baseline_loc.get(n, (0,0,0))
                self._baseline_loc[n] = (bx + dx, by + dy, bz)
            self._move_accum = [0.0, 0.0]

        else:  # scale
            f = self._scale_accum_factor
            for name in self.selected_actor_names:
                sx, sy, sz = self._baseline_scale.get(name, (1,1,1))
                nsx, nsy, nsz = sx * f, sy * f, sz * f
                resp = self.client.send_command(f"SCALE {name} {nsx} {nsy} {nsz}")
                if resp:
                    self.log_output.insert(tk.END, f"\n{name}: {resp.strip()}\n")
            # 베이스라인 갱신 + UI 슬라이더 동기화(첫 번째 대상)
            for n in self.selected_actor_names:
                sx, sy, sz = self._baseline_scale.get(n, (1,1,1))
                self._baseline_scale[n] = (sx * f, sy * f, sz * f)
            first = self.selected_actor_names[0]
            fs = self._baseline_scale.get(first, (1,1,1))
            self.scale["X"], self.scale["Y"], self.scale["Z"] = fs
            self.scl_x.set(fs[0]); self.scl_y.set(fs[1]); self.scl_z.set(fs[2])
            self._scale_accum_factor = 1.0



            

    # ---------- 슬롯 버튼(교체 + 상세) ----------
    def render_slot_buttons(self, count):
        for w in self.slot_frame.winfo_children():
            w.destroy()
        for idx in range(count):
            fr = tk.Frame(self.slot_frame)
            fr.grid(row=idx, column=0, sticky="w", padx=4, pady=2)
            tk.Button(fr, text=f"Slot {idx} 바꾸기(일괄)", width=20,
                      command=partial(self.on_slot_selected_bulk, idx)).pack(side=tk.LEFT)
            tk.Button(fr, text="🔎", width=3,
                      command=partial(self.show_slot_textures, idx)).pack(side=tk.LEFT, padx=4)

    def show_slot_textures(self, idx):
        if not self.selected_actor_names:
            return
        first = self.selected_actor_names[0]

        # 서버가 지원하면 정확히 슬롯만, 아니면 전체 텍스처로 폴백
        out = None
        try:
            out = self.client.send_command(f"GET_TEXTURES_SLOT {first} {idx}")
            # 일부 서버는 빈 문자열을 줄 수 있으니 보강
            if not out or "알 수 없는 명령" in out:
                out = self.client.send_command(f"GET_TEXTURES {first}")
                out = f"(서버 미지원 → 전체 텍스처)\n{out}"
        except Exception:
            out = self.client.send_command(f"GET_TEXTURES {first}")
            out = f"(서버 미지원 → 전체 텍스처)\n{out}"

        # 보기 좋게 출력 영역 갱신
        self.texture_info.insert(tk.END, "\n" + out.strip() + "\n")
        self.texture_info.see(tk.END)


    # ---------- 머티리얼 교체(일괄) ----------
    def bulk_replace_material(self):
        if not self.selected_actor_names:
            messagebox.showinfo("알림", "액터를 선택하세요.")
            return

        # 슬롯 인덱스 입력
        idx_win = tk.Toplevel(self.root)
        idx_win.title("슬롯 인덱스 입력")
        tk.Label(idx_win, text="교체할 슬롯 인덱스:").pack(side=tk.LEFT, padx=6, pady=6)
        slot_var = tk.IntVar(value=0)
        tk.Entry(idx_win, textvariable=slot_var, width=6).pack(side=tk.LEFT, padx=6, pady=6)
        def pick_and_apply():
            idx = slot_var.get()
            idx_win.destroy()
            self._apply_material_to_selected(idx)
        tk.Button(idx_win, text="확인", command=pick_and_apply).pack(side=tk.LEFT, padx=6, pady=6)

    def on_slot_selected_bulk(self, slot_index):
        self._apply_material_to_selected(slot_index)

    def _apply_material_to_selected(self, slot_index):
        if not self.selected_actor_names:
            return
        filepath = filedialog.askopenfilename(
            title="교체할 머티리얼 선택",
            initialdir=DEFAULT_TEXTURE_DIR,
            filetypes=[("머티리얼 파일", "*.uasset")]
        )
        if not filepath: return
        upath = convert_to_unreal_path(filepath).strip()
        if not upath:
            self.texture_info.insert(tk.END, "\n❌ 경로 변환 실패\n")
            return
        # 여러 액터에 일괄 적용
        for name in self.selected_actor_names:
            cmd = f'SET_MATERIAL {name} {slot_index} "{upath}"'
            resp = self.client.send_command(cmd)
            if resp:
                self.log_output.insert(tk.END, f"\n{name}: {resp.strip()}\n")

    # ---------- 에디터 명령 ----------
    def send_editor_command(self, command: str):
        if not self.client.connect(self.client.ports[1]):  # 9998
            return "❌ Unreal Editor와 연결되지 않았습니다."
        return self.client.send_command(command)

    def spawn_asset_via_file(self):
        filepath = filedialog.askopenfilename(
            title="스폰할 에셋 선택 (.uasset 또는 .fbx)",
            initialdir=DEFAULT_FBX_EXPORT_DIR,
            filetypes=[("Unreal/FBX", "*.uasset;*.fbx"), ("Unreal Asset", "*.uasset"), ("FBX", "*.fbx"), ("All", "*.*")]
        )
        if not filepath:
            return

        ext = os.path.splitext(filepath)[1].lower()
        label = os.path.splitext(os.path.basename(filepath))[0]

        if ext == ".uasset":
            # /Game 경로로 변환하여 --asset 사용
            unreal_path = convert_to_unreal_path(filepath)          # D:\...\Content\...\Foo.uasset → /Game/.../Foo
            # 객체 경로 점 보정은 필요 없을 가능성이 큼(/Game/Foo/Bar 형태면 OK)
            if not self.client.connect(self.client.ports[1]):
                self.log_output.insert(tk.END, "\n❌ Unreal Editor와 연결되지 않았습니다.\n"); return
            cmd = f'py "{EDITOR_SCRIPT_SPAWN}" --asset "{unreal_path}" --spawn --x 1700 --y 0 --z 10 --label "{label}"'
            resp = self.client.send_command(cmd)
            self.log_output.insert(tk.END, f"\n{resp}\n")

        else:
            # 디스크 경로는 --fbx 로 임포트+스폰
            fbx_path = filepath if ext == ".fbx" else (filepath + ".fbx")
            if not os.path.isfile(fbx_path):
                messagebox.showerror("오류", f"FBX 파일을 찾을 수 없습니다:\n{fbx_path}")
                return
            if not self.client.connect(self.client.ports[1]):
                self.log_output.insert(tk.END, "\n❌ Unreal Editor와 연결되지 않았습니다.\n"); return
            cmd = (
                f'py "{EDITOR_SCRIPT_SPAWN}" '
                f'--fbx "{fbx_path}" --dest "/Game/Scripts/ExportedFBX" '
                f'--spawn --x 1700 --y 0 --z 10 --label "{label}"'
            )
            resp = self.client.send_command(cmd)
            self.log_output.insert(tk.END, f"\n{resp}\n")

    # ---------- 프리셋 UX ----------
    def refresh_preset_list(self):
        self.preset_listbox.delete(0, tk.END)
        try:
            os.makedirs(PRESET_DIR, exist_ok=True)
            files = sorted(glob.glob(os.path.join(PRESET_DIR, "*.json")))
            for f in files:
                name = os.path.splitext(os.path.basename(f))[0]
                self.preset_listbox.insert(tk.END, name)
        except Exception as e:
            messagebox.showerror("오류", f"프리셋 목록을 불러오지 못했습니다:\n{e}")

    def get_selected_preset_name(self):
        sel = self.preset_listbox.curselection()
        if not sel:
            return (self.preset_name_var.get() or "").strip()
        return self.preset_listbox.get(sel[0]).strip()

    def save_preset_btn(self):
        name = (self.preset_name_var.get() or "Preset").strip()
        if not name:
            messagebox.showinfo("알림", "프리셋 이름을 입력하세요.")
            return
        # 런타임 서버가 있으면 우선 활용 (현재 구현은 씬 전체 저장)
        if self.client.connect(self.client.ports[0]):  # 9999
            resp = self.client.send_command(f"SAVE_PRESET {name}")
        else:
            # Editor 스크립트 대체 (선택된 액터만 옵션 지원)
            cmd = f'py "{EDITOR_SCRIPT_PRESET}" --save-preset --name "{name}"'
            if self.only_selected_var.get(): cmd += " --only-selected"
            resp = self.send_editor_command(cmd)
        self.log_output.insert(tk.END, f"\n{resp}\n")
        self.refresh_preset_list()

    def load_preset_btn(self):
        name = self.get_selected_preset_name()
        if not name:
            messagebox.showinfo("알림", "로드할 프리셋을 선택하거나 이름을 입력하세요.")
            return
        ox = self.offset_x_var.get() or 0.0
        oy = self.offset_y_var.get() or 0.0
        oz = self.offset_z_var.get() or 0.0
        # 런타임 서버가 있으면 우선 활용
        if self.client.connect(self.client.ports[0]):  # 9999
            resp = self.client.send_command(f"LOAD_PRESET {name} {ox} {oy} {oz}")
        else:
            cmd = f'py "{EDITOR_SCRIPT_PRESET}" --load-preset --name "{name}" --offset-x {ox} --offset-y {oy} --offset-z {oz}'
            resp = self.send_editor_command(cmd)
        self.log_output.insert(tk.END, f"\n{resp}\n")
        self.refresh_preset_list()

    def delete_preset_btn(self):
        name = self.get_selected_preset_name()
        if not name:
            messagebox.showinfo("알림", "삭제할 프리셋을 선택하거나 이름을 입력하세요.")
            return
        p = os.path.join(PRESET_DIR, f"{name}.json")
        if os.path.isfile(p):
            try:
                os.remove(p)
                self.log_output.insert(tk.END, f"\n🧹 Deleted preset: {p}\n")
                self.refresh_preset_list()
            except Exception as e:
                messagebox.showerror("오류", f"삭제 실패: {e}")
        else:
            messagebox.showinfo("알림", f"프리셋 파일이 없습니다:\n{p}")

    # ---------- 실행 ----------
    def run(self):
        self.root.mainloop()
        self.client.close()

if __name__ == "__main__":
    ui = UnifiedUnrealEditorUI()
    ui.run()
