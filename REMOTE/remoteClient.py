# client.py
import socket
import pickle
import struct
import mss
import numpy as np
import cv2

SERVER_IP = "211.223.193.168"   # 서버 IP 입력
SERVER_PORT = 9500

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((SERVER_IP, SERVER_PORT))

with mss.mss() as sct:
    monitor = sct.monitors[1]  # 첫 번째 모니터 전체 캡처
    while True:
        # 화면 캡처 → numpy 배열로 변환
        img = sct.grab(monitor)
        frame = np.array(img)[:, :, :3]  # BGRA → BGR 변환 (마지막 채널 제거)

        # JPEG 압축 (전송 속도 최적화)
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 50])

        # 직렬화
        data = pickle.dumps(buffer)
        size = struct.pack("Q", len(data))   # ✅ 8바이트로 패킷 크기 전송

        # 서버로 전송
        client_socket.sendall(size + data)
