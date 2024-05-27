import socket
import threading
import pickle
import sys

client_state = {}

def listen_to_server(server_socket):
    while True:
        msg = server_socket.recv(1024).decode("utf-8")
        if msg == "/view_requests":
            server_socket.send(bytes(".", "utf-8"))
            response = server_socket.recv(1024).decode("utf-8")
            if response == "/sending_data":
                server_socket.send(b"/ready_for_data")
                data = pickle.loads(server_socket.recv(1024))
                if data == set():
                    print("No pending requests.")
                else:
                    print("Pending Requests:")
                    for element in data:
                        print(element)
            else:
                print(response)
        elif msg == "/approve_request":
            server_socket.send(bytes(".", "utf-8"))
            response = server_socket.recv(1024).decode("utf-8")
            if response == "/proceed":
                client_state["input_message"] = False
                print("Please enter the username to approve: ")
                with client_state["input_condition"]:
                    client_state["input_condition"].wait()
                client_state["input_message"] = True
                server_socket.send(bytes(client_state["user_input"], "utf-8"))
                print(server_socket.recv(1024).decode("utf-8"))
            else:
                print(response)
        elif msg == "/disconnect":
            server_socket.send(bytes(".", "utf-8"))
            client_state["is_alive"] = False
            break
        elif msg == "/message_send":
            server_socket.send(bytes(client_state["user_input"], "utf-8"))
            client_state["send_message_lock"].release()
        elif msg == "/all_members":
            server_socket.send(bytes(".", "utf-8"))
            data = pickle.loads(server_socket.recv(1024))
            print("All Group Members:")
            for element in data:
                print(element)
        elif msg == "/online_members":
            server_socket.send(bytes(".", "utf-8"))
            data = pickle.loads(server_socket.recv(1024))
            print("Online Group Members:")
            for element in data:
                print(element)
        elif msg == "/change_admin":
            server_socket.send(bytes(".", "utf-8"))
            response = server_socket.recv(1024).decode("utf-8")
            if response == "/proceed":
                client_state["input_message"] = False
                print("Please enter the username of the new admin: ")
                with client_state["input_condition"]:
                    client_state["input_condition"].wait()
                client_state["input_message"] = True
                server_socket.send(bytes(client_state["user_input"], "utf-8"))
                print(server_socket.recv(1024).decode("utf-8"))
            else:
                print(response)
        elif msg == "/who_admin":
            server_socket.send(bytes(client_state["group_name"], "utf-8"))
            print(server_socket.recv(1024).decode("utf-8"))
        elif msg == "/kick_member":
            server_socket.send(bytes(".", "utf-8"))
            response = server_socket.recv(1024).decode("utf-8")
            if response == "/proceed":
                client_state["input_message"] = False
                print("Please enter the username to kick: ")
                with client_state["input_condition"]:
                    client_state["input_condition"].wait()
                client_state["input_message"] = True
                server_socket.send(bytes(client_state["user_input"], "utf-8"))
                print(server_socket.recv(1024).decode("utf-8"))
            else:
                print(response)
        elif msg == "/kicked":
            client_state["is_alive"] = False
            client_state["input_message"] = False
            print("You have been kicked. Press any key to quit.")
            break
        elif msg == "/file_transfer":
            client_state["input_message"] = False
            print("Please enter the filename: ")
            with client_state["input_condition"]:
                client_state["input_condition"].wait()
            client_state["input_message"] = True
            filename = client_state["user_input"]
            try:
                f = open(filename, 'rb')
                f.close()
            except FileNotFoundError:
                print("The requested file does not exist.")
                server_socket.send(bytes("~error~", "utf-8"))
                continue
            server_socket.send(bytes(filename, "utf-8"))
            server_socket.recv(1024)
            print("Uploading file to server...")
            with open(filename, 'rb') as f:
                data = f.read()
                data_len = len(data)
                server_socket.send(data_len.to_bytes(4, 'big'))
                server_socket.send(data)
            print(server_socket.recv(1024).decode("utf-8"))
        elif msg == "/receive_file":
            print("Receiving shared group file...")
            server_socket.send(b"/send_filename")
            filename = server_socket.recv(1024).decode("utf-8")
            server_socket.send(b"/send_file")
            remaining = int.from_bytes(server_socket.recv(4), 'big')
            f = open(filename, "wb")
            while remaining:
                data = server_socket.recv(min(remaining, 4096))
                remaining -= len(data)
                f.write(data)
            f.close()
            print("Received file saved as", filename)
        else:
            print(msg)

def get_user_input(server_socket):
    while client_state["is_alive"]:
        client_state["send_message_lock"].acquire()
        client_state["user_input"] = input()
        client_state["send_message_lock"].release()
        with client_state["input_condition"]:
            client_state["input_condition"].notify()
        if client_state["user_input"] == "/1":
            server_socket.send(b"/view_requests")
        elif client_state["user_input"] == "/2":
            server_socket.send(b"/approve_request")
        elif client_state["user_input"] == "/3":
            server_socket.send(b"/disconnect")
            break
        elif client_state["user_input"] == "/4":
            server_socket.send(b"/all_members")
        elif client_state["user_input"] == "/5":
            server_socket.send(b"/online_members")
        elif client_state["user_input"] == "/6":
            server_socket.send(b"/change_admin")
        elif client_state["user_input"] == "/7":
            server_socket.send(b"/who_admin")
        elif client_state["user_input"] == "/8":
            server_socket.send(b"/kick_member")
        elif client_state["user_input"] == "/9":
            server_socket.send(b"/file_transfer")
        elif client_state["input_message"]:
            client_state["send_message_lock"].acquire()
            server_socket.send(b"/message_send")

def wait_server_listen(server_socket):
    while not client_state["is_alive"]:
        msg = server_socket.recv(1024).decode("utf-8")
        if msg == "/accepted":
            client_state["is_alive"] = True
            print("Your join request has been approved. Press any key to begin chatting.")
            break
        elif msg == "/wait_disconnect":
            client_state["join_disconnect"] = True
            break

def wait_user_input(server_socket):
    while not client_state["is_alive"]:
        client_state["user_input"] = input()
        if client_state["user_input"] == "/1" and not client_state["is_alive"]:
            server_socket.send(b"/wait_disconnect")
            break

def main():
    if len(sys.argv) < 3:
        print("USAGE: python client.py <IP> <Port>")
        print("EXAMPLE: python client.py localhost 8000")
        return
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.connect((sys.argv[1], int(sys.argv[2])))
    client_state["input_condition"] = threading.Condition()
    client_state["send_message_lock"] = threading.Lock()
    client_state["username"] = input("Welcome to BAATKARO! Please enter your username: ")
    client_state["group_name"] = input("Please enter the name of the group: ")
    client_state["is_alive"] = False
    client_state["join_disconnect"] = False
    client_state["input_message"] = True
    server_socket.send(bytes(client_state["username"], "utf-8"))
    server_socket.recv(1024)
    server_socket.send(bytes(client_state["group_name"], "utf-8"))
    response = server_socket.recv(1024).decode("utf-8")
    if response == "/admin_ready":
        print("You have created the group", client_state["group_name"], "and are now an admin.")
        client_state["is_alive"] = True
    elif response == "/ready":
        print("You have joined the group", client_state["group_name"])
        client_state["is_alive"] = True
    elif response == "/wait":
        print("Your request to join the group is pending admin approval.")
        print("Available Commands:\n/1 -> Disconnect\n")
    wait_user_input_thread = threading.Thread(target=wait_user_input, args=(server_socket,))
    wait_server_listen_thread = threading.Thread(target=wait_server_listen, args=(server_socket,))
    user_input_thread = threading.Thread(target=get_user_input, args=(server_socket,))
    listen_to_server_thread = threading.Thread(target=listen_to_server, args=(server_socket,))
    wait_user_input_thread.start()
    wait_server_listen_thread.start()
    while True:
        if client_state["is_alive"] or client_state["join_disconnect"]:
            break
    if client_state["is_alive"]:
        print("Available Commands:\n/1 -> View Join Requests (Admins)\n/2 -> Approve Join Requests (Admin)\n/3 -> Disconnect\n/4 -> View All Members\n/5 -> View Online Group Members\n/6 -> Transfer Adminship\n/7 -> Check Group Admin\n/8 -> Kick Member\n/9 -> File Transfer\nType anything else to send a message")
        wait_user_input_thread.join()
        wait_server_listen_thread.join()
        user_input_thread.start()
        listen_to_server_thread.start()
    while True:
        if client_state["join_disconnect"]:
            server_socket.shutdown(socket.SHUT_RDWR)
            server_socket.close()
            wait_user_input_thread.join()
            wait_server_listen_thread.join()
            print("Disconnected from BAATKARO.")
            break
        elif not client_state["is_alive"]:
            server_socket.shutdown(socket.SHUT_RDWR)
            server_socket.close()
            user_input_thread.join()
            listen_to_server_thread.join()
            print("Disconnected from BAATKARO.")
            break

if __name__ == "__main__":
    main()

