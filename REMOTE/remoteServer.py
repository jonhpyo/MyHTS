import socket
import cv2
import pickle
import struct
import numpy as np

HOST = "0.0.0.0"
PORT = 9500

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen(5)
print("📡 서버 대기중...")

conn, addr = server_socket.accept()
print("✅ 연결됨:", addr)

data = b""
payload_size = struct.calcsize("Q")  # 8바이트

while True:
    while len(data) < payload_size:
        data += conn.recv(4096)

    packed_size = data[:payload_size]
    data = data[payload_size:]
    msg_size = struct.unpack("Q", packed_size)[0]

    while len(data) < msg_size:
        data += conn.recv(4096)

    frame_data = data[:msg_size]
    data = data[msg_size:]

    # 압축 해제 (JPG → numpy → BGR frame)
    buffer = pickle.loads(frame_data)
    frame = cv2.imdecode(np.frombuffer(buffer, dtype=np.uint8), cv2.IMREAD_COLOR)

    cv2.imshow("Remote Screen", frame)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC 종료
        break

conn.close()
server_socket.close()
cv2.destroyAllWindows()
