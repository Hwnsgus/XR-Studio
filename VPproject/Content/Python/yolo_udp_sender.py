import cv2
import socket
from ultralytics import YOLO

# UDP 설정
UDP_IP = "192.168.1.131"  # Unreal 실행 중인 PC IP
UDP_PORT = 8080
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# YOLO 모델 로딩
model = YOLO("yolov8n.pt")  # lightweight model

# 스트림 소스
cap = cv2.VideoCapture("http://192.168.1.131:8080/stream.ts")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        continue

    results = model.track(frame, classes=[0], persist=True)  # class 0 = person

    for r in results:
        if r.boxes.id is not None:
            box = r.boxes.xyxy[0].cpu().numpy()  # 첫 번째 인물만
            cx = int((box[0] + box[2]) / 2)
            cy = int((box[1] + box[3]) / 2)
            msg = f"{cx},{cy}"
            sock.sendto(msg.encode(), (UDP_IP, UDP_PORT))

    cv2.imshow("Tracking", frame)
    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()