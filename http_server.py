import os
import socket
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Server:

    def __init__(self):
        self.host = "0.0.0.0"
        self.port = 5050
        self.conns = 1
        self.start_time = time.time()

    def listener(self):
        # Main server loop
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, self.port))
            s.listen(self.conns)
            print(f"Server listening on {self.host}:{self.port}")

            while True:
                conn, addr = s.accept()
                print(f"Connected by {addr}\n")
                self.handle_client(conn)

    def send_response(self, conn, status_code, content_type, body):
        # Sends response 
        status_text = {
            200: "OK",
            404: "Not Found",
            500: "Internal Server Error",
        }.get(status_code, "OK")

        if isinstance(body, str):
            body_bytes = body.encode()
        else:
            body_bytes = body

        response_headers = (
            f"HTTP/1.1 {status_code} {status_text}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"Connection: close\r\n"
            "\r\n"
        )

        # Log the response
        print("----- RESPONSE SENT -----")
        print(response_headers + (body if isinstance(body, str) else ""))
        print("-------------------------\n")

        # Send response
        conn.sendall(response_headers.encode("utf-8") + body_bytes)
        conn.close()

    def handle_client(self, conn):
        # Tries to parse request
        try:
            buffer = b""
            while b"\r\n\r\n" not in buffer:
                chunk = conn.recv(1024)
                if not chunk:
                    return
                buffer += chunk

            header_data = buffer.decode(errors="replace")
            header_text, _, _ = header_data.partition("\r\n\r\n")
            lines = header_text.split("\r\n")

            request_line = lines[0]
            parts = request_line.split()
            if len(parts) != 3:
                return self.send_response(conn, 500, "text/plain", "Invalid Request")

            verb, path, version = parts

            headers = {}
            for line in lines[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip()] = value.strip()

            # ---------------- PRINT REQUEST ----------------
            print("----- REQUEST RECEIVED -----")
            print(f"{verb}{path}{version}")
            for k, v in headers.items():
                print(f"{k}: {v}")
            print("----------------------------\n")

            # ---------------------- ROUTES --------------------------
            if verb.upper() == "GET":
                if path == "/":
                    try:
                        file_path = os.path.join(BASE_DIR, "index.html")
                        with open(file_path, "r", encoding="utf-8") as f:
                            html_content = f.read()
                        return self.send_response(
                            conn, 200, "text/html",
                            html_content
                        )
                    except FileNotFoundError as e:
                        print("Error reading HTML:", e)
                        return self.send_response(
                            conn, 500, "text/plain",
                            "index.html not found on server"
                        )

                elif path == "/time":
                    return self.send_response(
                        conn, 200, "text/plain",
                        f"The current date and time is {time.ctime()}"
                    )

                elif path == "/uptime":
                    uptime = int(time.time() - self.start_time)
                    return self.send_response(
                        conn, 200, "text/plain",
                        f"Server uptime: {uptime} seconds"
                    )
                
                else:
                    self.send_response(conn, 404, "text/plain", "Not Found")

        except Exception as e:
            try:
                return self.send_response(conn, 500, "text/plain", "Server Error")
            except:
                conn.close()


if __name__ == "__main__":

    server = Server()
    server.listener()


