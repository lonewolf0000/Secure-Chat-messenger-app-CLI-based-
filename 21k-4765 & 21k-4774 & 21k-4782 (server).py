import socket
import threading
import pickle
import os
import sys

chat_groups = {}
file_transfer_condition = threading.Condition()

class ChatGroup:
    def __init__(self, admin, client_socket):
        self.admin = admin
        self.clients = {}
        self.offline_messages = {}
        self.all_members = set()
        self.online_members = set()
        self.join_requests = set()
        self.wait_clients = {}

        self.clients[admin] = client_socket
        self.all_members.add(admin)
        self.online_members.add(admin)

    def disconnect_member(self, username):
        self.online_members.remove(username)
        del self.clients[username]

    def connect_member(self, username, client_socket):
        self.online_members.add(username)
        self.clients[username] = client_socket

    def send_message(self, message, sender):
        for member in self.online_members:
            if member != sender:
                self.clients[member].send(bytes(sender + ": " + message, "utf-8"))

def handle_chat(client_socket, username, group_name):
    while True:
        msg = client_socket.recv(1024).decode("utf-8")
        if msg == "/view_requests":
            client_socket.send(b"/view_requests")
            client_socket.recv(1024).decode("utf-8")
            if username == chat_groups[group_name].admin:
                client_socket.send(b"/sending_data")
                client_socket.recv(1024)
                client_socket.send(pickle.dumps(chat_groups[group_name].join_requests))
            else:
                client_socket.send(b"You're not an admin.")
        elif msg == "/approve_request":
            client_socket.send(b"/approve_request")
            client_socket.recv(1024).decode("utf-8")
            if username == chat_groups[group_name].admin:
                client_socket.send(b"/proceed")
                username_to_approve = client_socket.recv(1024).decode("utf-8")
                if username_to_approve in chat_groups[group_name].join_requests:
                    chat_groups[group_name].join_requests.remove(username_to_approve)
                    chat_groups[group_name].all_members.add(username_to_approve)
                    if username_to_approve in chat_groups[group_name].wait_clients:
                        chat_groups[group_name].wait_clients[username_to_approve].send(b"/accepted")
                        chat_groups[group_name].connect_member(username_to_approve, chat_groups[group_name].wait_clients[username_to_approve])
                        del chat_groups[group_name].wait_clients[username_to_approve]
                    print("Member Approved:", username_to_approve, "| Group:", group_name)
                    client_socket.send(b"User has been added to the group.")
                else:
                    client_socket.send(b"The user has not requested to join.")
            else:
                client_socket.send(b"You're not an admin.")
        elif msg == "/disconnect":
            client_socket.send(b"/disconnect")
            client_socket.recv(1024).decode("utf-8")
            chat_groups[group_name].disconnect_member(username)
            print("User Disconnected:", username, "| Group:", group_name)
            break
        elif msg == "/message_send":
            client_socket.send(b"/message_send")
            message = client_socket.recv(1024).decode("utf-8")
            chat_groups[group_name].send_message(message, username)
        elif msg == "/wait_disconnect":
            client_socket.send(b"/wait_disconnect")
            del chat_groups[group_name].wait_clients[username]
            print("Waiting Client:", username, "Disconnected")
            break
        elif msg == "/all_members":
            client_socket.send(b"/all_members")
            client_socket.recv(1024).decode("utf-8")
            client_socket.send(pickle.dumps(chat_groups[group_name].all_members))
        elif msg == "/online_members":
            client_socket.send(b"/online_members")
            client_socket.recv(1024).decode("utf-8")
            client_socket.send(pickle.dumps(chat_groups[group_name].online_members))
        elif msg == "/change_admin":
            client_socket.send(b"/change_admin")
            client_socket.recv(1024).decode("utf-8")
            if username == chat_groups[group_name].admin:
                client_socket.send(b"/proceed")
                new_admin_username = client_socket.recv(1024).decode("utf-8")
                if new_admin_username in chat_groups[group_name].all_members:
                    chat_groups[group_name].admin = new_admin_username
                    print("New Admin:", new_admin_username, "| Group:", group_name)
                    client_socket.send(b"Your adminship is now transferred to the specified user.")
                else:
                    client_socket.send(b"The user is not a member of this group.")
            else:
                client_socket.send(b"You're not an admin.")
        elif msg == "/who_admin":
            client_socket.send(b"/who_admin")
            group_name = client_socket.recv(1024).decode("utf-8")
            client_socket.send(bytes("Admin: " + chat_groups[group_name].admin, "utf-8"))
        elif msg == "/kick_member":
            client_socket.send(b"/kick_member")
            client_socket.recv(1024).decode("utf-8")
            if username == chat_groups[group_name].admin:
                client_socket.send(b"/proceed")
                username_to_kick = client_socket.recv(1024).decode("utf-8")
                if username_to_kick in chat_groups[group_name].all_members:
                    chat_groups[group_name].all_members.remove(username_to_kick)
                    if username_to_kick in chat_groups[group_name].online_members:
                        chat_groups[group_name].clients[username_to_kick].send(b"/kicked")
                        chat_groups[group_name].online_members.remove(username_to_kick)
                        del chat_groups[group_name].clients[username_to_kick]
                    print("User Removed:", username_to_kick, "| Group:", group_name)
                    client_socket.send(b"The specified user is removed from the group.")
                else:
                    client_socket.send(b"The user is not a member of this group.")
            else:
                client_socket.send(b"You're not an admin.")
        elif msg == "/file_transfer":
            client_socket.send(b"/file_transfer")
            filename = client_socket.recv(1024).decode("utf-8")
            if filename == "~error~":
                continue
            client_socket.send(b"/send_file")
            remaining = int.from_bytes(client_socket.recv(4), 'big')
            f = open(filename, "wb")
            while remaining:
                data = client_socket.recv(min(remaining, 4096))
                remaining -= len(data)
                f.write(data)
            f.close()
            print("File received:", filename, "| User:", username, "| Group:", group_name)
            for member in chat_groups[group_name].online_members:
                if member != username:
                    member_client = chat_groups[group_name].clients[member]
                    member_client.send(b"/receive_file")
                    with file_transfer_condition:
                        file_transfer_condition.wait()
                    member_client.send(bytes(filename, "utf-8"))
                    with file_transfer_condition:
                        file_transfer_condition.wait()
                    with open(filename, 'rb') as f:
                        data = f.read()
                        data_len = len(data)
                        member_client.send(data_len.to_bytes(4, 'big'))
                        member_client.send(data)
            client_socket.send(bytes(filename + " successfully sent to all online group members.", "utf-8"))
            print("File sent", filename, "| Group: ", group_name)
            os.remove(filename)
        elif msg == "/send_filename" or msg == "/send_file":
            with file_transfer_condition:
                file_transfer_condition.notify()
        else:
            print("UNIDENTIFIED COMMAND:", msg)

def handshake(client_socket):
    username = client_socket.recv(1024).decode("utf-8")
    client_socket.send(b"/send_groupname")
    group_name = client_socket.recv(1024).decode("utf-8")
    if group_name in chat_groups:
        if username in chat_groups[group_name].all_members:
            chat_groups[group_name].connect_member(username, client_socket)
            client_socket.send(b"/ready")
            print("User Connected:", username, "| Group:", group_name)
        else:
            chat_groups[group_name].join_requests.add(username)
            chat_groups[group_name].wait_clients[username] = client_socket
            chat_groups[group_name].send_message(username + " has requested to join the group.", "BAATKARO")
            client_socket.send(b"/wait")
            print("Join Request:", username, "| Group:", group_name)
        threading.Thread(target=handle_chat, args=(client_socket, username, group_name,)).start()
    else:
        chat_groups[group_name] = ChatGroup(username, client_socket)
        threading.Thread(target=handle_chat, args=(client_socket, username, group_name,)).start()
        client_socket.send(b"/admin_ready")
        print("New Group:", group_name, "| Admin:", username)

def main():
    if len(sys.argv) < 3:
        print("USAGE: python server.py <IP> <Port>")
        print("EXAMPLE: python server.py localhost 8888")
        return
    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_socket.bind((sys.argv[1], int(sys.argv[2])))
    listen_socket.listen(10)
    print("BAATKARO Server running")
    while True:
        client_socket, _ = listen_socket.accept()
        threading.Thread(target=handshake, args=(client_socket,)).start()

if __name__ == "__main__":
    main()

