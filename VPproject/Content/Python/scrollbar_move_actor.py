import socket
import threading
import tkinter as tk


class UnrealSocketServer:
    def __init__(self, host='127.0.0.1', port=9999):
        self.HOST = host
        self.PORT = port
        self.conn = None
        self.server_socket = None
        self.thread = threading.Thread(target=self.start_server, daemon=True)
        self.thread.start()

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.HOST, self.PORT))
        self.server_socket.listen()
        print("🟢 Unreal 연결 대기 중...")

        self.conn, addr = self.server_socket.accept()
        print(f"🔗 Unreal 연결됨: {addr}")

    def send_command(self, command):
        if not self.conn:
            print("❌ Unreal과 아직 연결되지 않았습니다.")
            return

        try:
            self.conn.sendall((command.strip() + "\n").encode('ascii'))
            print("📤 명령 전송:", command)
            response = self.conn.recv(1024)
            print("📨 응답 수신:", response.decode())
        except Exception as e:
            print("❌ 통신 오류:", e)

    def request_actor_list(self, callback=None):
        if not self.conn:
            print("❌ Unreal과 아직 연결되지 않았습니다.")
            return
    
        try:
            self.conn.sendall(("LIST\n").encode("ascii"))
            self.conn.settimeout(2.0)
    
            full_response = b""
            while True:
                try:
                    chunk = self.conn.recv(2048)
                    if not chunk:
                        break
                    full_response += chunk
                    if len(chunk) < 2048:
                        break
                except socket.timeout:
                    break
                
            decoded = full_response.decode()
            print("📄 현재 액터 목록:\n", decoded)
    
            if callback:
                callback(decoded)
    
        except Exception as e:
            print("❌ 액터 목록 요청 실패:", e)

# ✅ GUI 클래스
class ActorCommandUI:
    def __init__(self, socket_server):
        self.socket_server = socket_server
        self.root = tk.Tk()
        self.root.title("🎮 Unreal Actor 조작")

        # 누적 좌표 초기값
        self.position = {"X": 0, "Y": 0, "Z": 0}

        # 액터 이름 입력
        tk.Label(self.root, text="Actor Name").grid(row=0, column=0)
        self.entry_name = tk.Entry(self.root)
        self.entry_name.grid(row=0, column=1)

        # 슬라이더 설정 (무제한처럼 동작하게)
        self.scale_x = tk.Scale(self.root, from_=-100, to=100, orient=tk.HORIZONTAL, label="X", command=lambda v: self.on_slider_change("X", int(v)))
        self.scale_x.set(0)
        self.scale_x.grid(row=1, column=0, columnspan=2)

        self.scale_y = tk.Scale(self.root, from_=-100, to=100, orient=tk.HORIZONTAL, label="Y", command=lambda v: self.on_slider_change("Y", int(v)))
        self.scale_y.set(0)
        self.scale_y.grid(row=2, column=0, columnspan=2)

        self.scale_z = tk.Scale(self.root, from_=-100, to=100, orient=tk.HORIZONTAL, label="Z", command=lambda v: self.on_slider_change("Z", int(v)))
        self.scale_z.set(0)
        self.scale_z.grid(row=3, column=0, columnspan=2)

        tk.Button(self.root, text="Send MOVE", command=self.send_move).grid(row=4, columnspan=2)
        tk.Button(self.root, text="Get Actor List", command=self.get_actor_list).grid(row=5, columnspan=2)

        # 리스트박스
        tk.Label(self.root, text="Actor 목록").grid(row=6, column=0, columnspan=2)
        self.actor_listbox = tk.Listbox(self.root, height=10, width=40)
        self.actor_listbox.grid(row=7, column=0, columnspan=2)
        self.actor_listbox.bind('<<ListboxSelect>>', self.on_actor_selected)

    def on_slider_change(self, axis, value):
        if value == 0:
            return  # 중앙에 있을 땐 변화 없음

        # 누적 좌표에 델타 적용
        self.position[axis] += value
        print(f"🧭 {axis} 변경됨: 누적 위치 = {self.position[axis]}")

        # 슬라이더 초기화
        if axis == "X":
            self.scale_x.set(0)
        elif axis == "Y":
            self.scale_y.set(0)
        elif axis == "Z":
            self.scale_z.set(0)

        # 이동 명령 전송
        self.send_move()

    def send_move(self):
        name = self.entry_name.get().strip()
        if not name:
            return
        x, y, z = self.position["X"], self.position["Y"], self.position["Z"]
        command = f"MOVE {name} {x} {y} {z}"
        self.socket_server.send_command(command)

    def get_actor_list(self):
        self.socket_server.request_actor_list(callback=self.update_actor_list)

    def update_actor_list(self, actor_text):
        self.actor_listbox.delete(0, tk.END)
        for name in actor_text.strip().splitlines():
            self.actor_listbox.insert(tk.END, name)

    def on_actor_selected(self, event):
        selected = self.actor_listbox.curselection()
        if selected:
            actor_name = self.actor_listbox.get(selected[0])
            self.entry_name.delete(0, tk.END)
            self.entry_name.insert(0, actor_name)

    def run(self):
        self.root.mainloop()

# 실행
if __name__ == "__main__":
    server = UnrealSocketServer()
    gui = ActorCommandUI(server)
    gui.run()
