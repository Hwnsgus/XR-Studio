import socket

HOST = "127.0.0.1"
PORT = 7777

message = "MOVE StaticMeshActor_0 0 0 100"

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    s.sendall(message.encode())
    print("✅ 명령 전송 완료:", message)
