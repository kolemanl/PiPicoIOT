import os
import socket
import time
import machine
import json

led = machine.Pin('LED', machine.Pin.OUT)
CONFIG_FILE = "config.json"

def save_config(ssid, password):
    try:
        with open(CONFIG_FILE, "w") as file:
            json.dump({
                "ssid": ssid,
                "password": password
            }, file)
        print("Config saved:", ssid)
    except Exception as e:
        print("Error saving config:", e)
        
def pct_decode(s: str) -> str:
    """Simple percent-decoder and +->space for form values."""
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == '+':
            out.append(' ')
            i += 1
        elif c == '%' and i + 2 < len(s):
            try:
                val = int(s[i+1:i+3], 16)
                if 0x20 <= val <= 0x7E:
                    out.append(chr(val))  # printable ASCII
                else:
                    out.append("'")  # convert smart quotes to plain apostrophe
                i += 3
            except:
                out.append('%')
                i += 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)

class Server:

    def __init__(self, config_mode):
        self.host = "0.0.0.0"
        self.port = 80
        self.conns = 1
        self.start_time = time.time()
        self.config_mode = config_mode

    def listener(self):
        # Main server loop
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((self.host, self.port))
        s.listen(self.conns)

        print("Server listening...")

        while True:
            conn, addr = s.accept()
            print("Connected:", addr)
            self.handle_client(conn, self.config_mode)

    def send_redirect(self, conn, location):
        headers = (
            "HTTP/1.1 302 Moved\r\n"
            f"Location: {location}\r\n"
            "Content-Length: 0\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        print("----- RESPONSE SENT (redirect) -----")
        print(headers)
        print("-----------------------------------\n")
        conn.sendall(headers.encode("utf-8"))
        conn.close()
        
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
        print("body: ", body)
        # Log the response
        print("----- RESPONSE SENT -----")
        print(response_headers + (body if isinstance(body, str) else ""))
        print("-------------------------\n")

        # Send response
        conn.sendall(response_headers.encode("utf-8") + body_bytes)
        conn.close()

    def handle_client(self, conn, config_mode):
        # Tries to parse request
        try:
            buffer = b""
            while b"\r\n\r\n" not in buffer:
                chunk = conn.recv(1024)
                if not chunk:
                    return
                buffer += chunk

            header_data = buffer.decode()
            header_text, _, remainder = header_data.partition("\r\n\r\n")
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
            if config_mode and path == "/":
                self.send_redirect(conn, "/config.html")
                return
            
            if verb.upper() == "GET":
                if path == "/":
                    try:
                        file_path = "index.html"
                        with open(file_path, "r") as f:
                            html_content = f.read()
                            
                                # Replace placeholder with current LED state
                        led_state = "ON" if led.value() else "OFF"
                        html_content = html_content.replace("{{LED_STATE}}", led_state)
                        
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

                elif path == "/config.html":
                    # serve config page
                    try:
                        file_path = "config.html"
                        with open(file_path, "r") as f:
                            html_content = f.read()
                        return self.send_response(conn, 200, "text/html", html_content)
                    except FileNotFoundError as e:
                        print("Error reading config.html:", e)
                        return self.send_response(conn, 500, "text/plain", "config.html not found on server")
                
                else:
                    self.send_response(conn, 404, "text/plain", "Not Found")
                    
            elif verb.upper() == "POST":
                pass
                # Ensure Content-Length to know how many bytes to read for body
                content_length = int(headers.get("Content-Length", "0"))
                body_bytes = remainder.encode("utf-8") if remainder else b""

                print(body_bytes)
                print(content_length)
                # remainder may be truncated due to replace errors; best-effort
                # read the remaining bytes if content_length > len(body_bytes)
                to_read = content_length - len(body_bytes)
                while to_read > 0:
                    chunk = conn.recv(1024)
                    if not chunk:
                        break
                    body_bytes += chunk
                    to_read -= len(chunk)

                body_text = body_bytes.decode("utf-8")
                # Log the body
                print("POST body:", body_text)

                # POST route: save config
                if path == "/save_config":
                    # Expect body like: ssid=MySSID&password=MyPass
                    params = {}
                    for kv in body_text.split("&"):
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            params[k] = pct_decode(v)
                    ssid = params.get("ssid", "")
                    password = params.get("password", "")

                    # Basic guard
                    if not ssid:
                        return self.send_response(conn, 400, "text/plain", "SSID required")

                    # Save config
                    try:
                        print(ssid, password)
                        save_config(ssid, password)
                        # reply then reboot
                        self.send_response(conn, 200, "text/plain", "Saved. Rebooting...")
                        time.sleep(1.5)
                        try:
                            # MicroPython reset
                            machine.reset()
                        except Exception as e:
                            print("Reset failed / not on Pico:", e)
                        return
                    except Exception as e:
                        print("Error saving config:", e)
                        return self.send_response(conn, 500, "text/plain", "Failed to save config")

                # POST route: toggle LED (only allowed in normal mode)
                elif path == "/toggle":
                    if self.config_mode:
                        # Must redirect to config page instead of allowing toggle
                        return self.send_redirect(conn, "/config.html")
                    try:
                        current = led.value()
                        print(current)
                        led.value(0 if current else 1)
                        return self.send_response(conn, 200, "text/plain", "OK")
                    except Exception as e:
                        print("Error toggling LED:", e)
                        return self.send_response(conn, 500, "text/plain", "LED toggle failed")

                else:
                    return self.send_response(conn, 404, "text/plain", "Not Found")

            else:
                # Method not allowed
                return self.send_response(conn, 405, "text/plain", "")

        except Exception as e:
            try:
                print(e)
                return self.send_response(conn, 500, "text/plain", "Server Error")
            except:
                conn.close()



