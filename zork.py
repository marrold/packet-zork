import socket
import threading
import queue
import os
import pty
import selectors
import time
import signal
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class ClientThread(threading.Thread):
    def __init__(self, client_socket, client_address, cmd_queue, max_connections, program):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.client_address = client_address
        self.cmd_queue = cmd_queue
        self.max_connections = max_connections
        self.program = program
        self.child_pid = None

    def run(self):
        if self.cmd_queue.qsize() >= self.max_connections:
            self.client_socket.sendall(b'Try again later\n')
            self.client_socket.close()
        else:
            self.cmd_queue.put(1)
            try:
                self.send_welcome_message()  # Send welcome message to the client
                self.run_command()
            except OSError as e:
                pass
            finally:
                self.cmd_queue.get()
                self.client_socket.close()
                if self.child_pid:
                    os.killpg(os.getpgid(self.child_pid), signal.SIGTERM)  # Kill the child process group if it's still running

    def send_welcome_message(self):
        message = b"\nWelcome to Zork. This is a modified version of https://github.com/icculus/mojozork.\nTo exit, enter 'quit' at the prompt.\n\n"
        self.client_socket.sendall(message)

    def run_command(self):
        master_fd, slave_fd = pty.openpty()
        pid = os.fork()

        if pid == 0:  # Child process
            os.setsid()  # Start a new session for the child process
            os.close(master_fd)
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ignore SIGINT in the child process
            os.execl(self.program, self.program)
        else:  # Parent process
            self.child_pid = pid
            os.close(slave_fd)

            sel = selectors.DefaultSelector()
            sel.register(master_fd, selectors.EVENT_READ)
            sel.register(self.client_socket, selectors.EVENT_READ)

            buffer = b""
            last_sent_command = b""
            try:
                while True:
                    ready = sel.select()
                    for key, _ in ready:
                        if key.fileobj is master_fd:
                            output = os.read(master_fd, 1)
                            buffer += output
                            if output == b'>':
                                if buffer.strip():
                                    if buffer.startswith(last_sent_command):
                                        buffer = buffer[len(last_sent_command):]
                                    self.send_buffered_text(buffer)
                                buffer = b""
                                last_sent_command = b""
                        elif key.fileobj is self.client_socket:
                            data = self.client_socket.recv(1024)
                            if data:
                                data = data.replace(b'\r\n', b'\n')  # replace \r\n with \n
                                last_sent_command = data.rstrip()  # Store last sent command
                                if data == b'\xff\xf4\xff\xfd\x06':  # Ctrl + C Telnet negotiation code
                                    logging.info(f"Received Ctrl + C from {self.client_address}")
                                    os.killpg(os.getpgid(self.child_pid), signal.SIGINT)  # Send SIGINT signal to the child process
                                    self.client_socket.close()  # Close the socket
                                    return
                                else:
                                    os.write(master_fd, data)
                            else:
                                break
            except OSError as e:
                pass
            finally:
                os.close(master_fd)
                if self.child_pid:
                    os.killpg(os.getpgid(self.child_pid), signal.SIGTERM)  # Kill the child process group if it's still running

    def send_buffered_text(self, text):
        if not text.endswith(b'\n'):
            text += b'\n'
        total_sent = 0
        while total_sent < len(text):
            try:
                sent = self.client_socket.send(text[total_sent:])
                if sent == 0:
                    raise RuntimeError("Socket connection broken")
                total_sent += sent
            except socket.error as e:
                logging.error(f"Socket error occurred while sending data: {str(e)}")
                return

def handle_interrupt(signal, frame):
    # Handle SIGINT signal
    logging.info("Interrupt signal received. Exiting...")
    os._exit(0)

def main():
    # Register SIGINT handler
    signal.signal(signal.SIGINT, handle_interrupt)

    max_connections = 10
    cmd_queue = queue.Queue(maxsize=max_connections)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', 2323))
    server_socket.listen(max_connections)

    logging.info('Server is listening on 0.0.0.0:2323')

    your_program = '/opt/zork/mojozork'

    try:
        while True:
            (client_socket, client_address) = server_socket.accept()
            logging.info(f'Accepted connection from {client_address}')

            new_thread = ClientThread(client_socket, client_address, cmd_queue, max_connections, your_program)
            new_thread.start()
    except KeyboardInterrupt:
        logging.info('Server is shutting down')
    finally:
        server_socket.close()

if __name__ == '__main__':
    main()

