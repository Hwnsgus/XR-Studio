import socket
import threading
import tkinter as tk

# 소켓 서버
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
            self.conn.sendall(command.encode())
            print("📤 명령 전송:", command)
            response = self.conn.recv(1024)
            print("📨 응답 수신:", response.decode())
        except Exception as e:
            print("❌ 통신 오류:", e)
            
    def get_actor_list(self):
        self.send_command("LIST")

    def request_actor_list(self):  
        if not self.conn:
            print("❌ Unreal과 아직 연결되지 않았습니다.")
            return

        try:
            command = "LIST"
            self.conn.sendall((command.strip() + "\n").encode('utf-8'))

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

            print("📄 현재 액터 목록:\n", full_response.decode())
        except Exception as e:
            print("❌ 액터 목록 요청 실패:", e)


    

# GUI 컴포넌트
class ActorCommandUI:
    def __init__(self, socket_server):
        self.socket_server = socket_server
        self.root = tk.Tk()
        self.root.title("🎮 Unreal Actor 이동")

        # UI 요소
        tk.Label(self.root, text="Actor Name").grid(row=0, column=0)
        self.entry_name = tk.Entry(self.root)
        self.entry_name.grid(row=0, column=1)

        tk.Label(self.root, text="X").grid(row=1, column=0)
        self.entry_x = tk.Entry(self.root)
        self.entry_x.grid(row=1, column=1)

        tk.Label(self.root, text="Y").grid(row=2, column=0)
        self.entry_y = tk.Entry(self.root)
        self.entry_y.grid(row=2, column=1)

        tk.Label(self.root, text="Z").grid(row=3, column=0)
        self.entry_z = tk.Entry(self.root)
        self.entry_z.grid(row=3, column=1)

        tk.Button(self.root, text="Get Actor List", command=self.get_actor_list).grid(row=5, columnspan=2)

        tk.Button(self.root, text="Send", command=self.send_command).grid(row=4, columnspan=2)

    def send_command(self):
        name = self.entry_name.get().strip()
        try:
            x = float(self.entry_x.get())
            y = float(self.entry_y.get())
            z = float(self.entry_z.get())
        except ValueError:
            print("❌ 좌표 입력 오류")
            return

        command = f"MOVE {name} {x} {y} {z}"
        self.socket_server.send_command(command)

    def run(self):
        self.root.mainloop()

    def get_actor_list(self):
        self.socket_server.request_actor_list()


# 실행
if __name__ == "__main__":
    server = UnrealSocketServer()
    gui = ActorCommandUI(server)
    gui.run()
