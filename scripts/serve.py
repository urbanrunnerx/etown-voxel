import http.server, socketserver
socketserver.TCPServer.allow_reuse_address = True
h = http.server.SimpleHTTPRequestHandler
s = socketserver.TCPServer(("127.0.0.1", 8765), h)
print("listening 8765", flush=True)
s.serve_forever()
