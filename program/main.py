# -*- coding: utf-8 -*-
# @Author  : Xuening Wang
# @Time    : 2021/11/20 17:38
# @File: main.py
# @Software: PyCharm

import argparse
import json
import math
import struct
import threading
import os
from socket import *

peer_status = 0
port1 = 22001
port2 = 22002
block_size = 2097152  # 20 MB
port_list = [22003, 22004, 22005, 22006]

share_directory = "share"
info_socket = socket(AF_INET, SOCK_STREAM)
info_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
info_socket.bind(('', port1))
info_socket.listen(2)

file_socket = socket(AF_INET, SOCK_STREAM)
file_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
file_socket.bind(('', port2))
file_socket.listen(2)

file_info = {}
new_add_file = {}
new_update_file = []
new_file_from_peer = []
new_update_from_peer = []


def _argparse():
    parser = argparse.ArgumentParser(description="This is description!")
    parser.add_argument('--ip', action='store', required=True,
                        dest='ip', help='ip addresses of peers')
    return parser.parse_args()


def get_file_block(filename, block_index):
    global block_size
    f = open(filename, 'rb')
    f.seek(block_index * block_size)
    file_block = f.read(block_size)
    f.close()
    return file_block


"""
    operation_code == 0: inform the local host of file changes
    operation_code == 1: inform the peer of new files
    operation_code == 2: inform the peer of updated files
"""


# operation_code == 0
# informs new file to the local host after receiving the peer's file information
def local_update_new_file(data):
    for file_name in data['new_add_file']:
        if file_name not in file_info:
            file = {'file_name': file_name, 'file_info': data["new_add_file"][file_name]}
            if file not in new_file_from_peer:
                new_file_from_peer.append(file)
        # Breakpoint transmission: file size < file size
        if file_name in file_info and file_info[file_name] != 1 and os.path.getsize(file_name) < \
                data["new_add_file"][file_name]["file_size"]:
            breakpoint_resume(client_sockets[1], file_name, data["new_add_file"][file_name]["file_size"])


# operation_code == 1
# informs new file to the peer
def inform_new_file(socket):
    data = {
        "operation_code": 1,
        "new_add_file": new_add_file
    }
    format_data = json.dumps(data).encode()
    encode_data = struct.pack('!I', len(format_data)) + format_data
    socket.send(encode_data)


# operation_code == 2
# informs update file to the peer
def inform_update_file(socket):
    data = {
        "operation_code": 2,
        "new_update_file": new_update_file
    }
    format_data = json.dumps(data).encode()
    encode_data = struct.pack('!I', len(format_data)) + format_data
    socket.send(encode_data)


"""
    file_scanner()
    
    Functions:
        1. Traverse the share folder
        2. Compare the results with the file dictionary
        3. Report the changes to the local host
    
"""


def file_scanner():
    global peer_status
    have_new_file = 0
    have_update_file = 0

    global file_info, new_add_file, new_update_file
    while True:
        # traverse the share directory
        new_file_info = {}
        for root, dirs, files in os.walk(share_directory, followlinks=True):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    new_file_info[file_path] = {"file_mtime": os.path.getmtime(file_path),
                                                "file_size": os.path.getsize(file_path)}
                except:
                    new_file_info[file_path] = {"file_mtime": file_info[file_path]["file_mtime"],
                                                "file_size": file_info[file_path]["file_size"]}
        # try to update the local file list
        for file in new_file_info:
            if file in file_info:
                # print(file_info)
                if file_info[file] == 1:  # file is pending to be downloaded
                    new_file_info[file] = 1
                else:
                    # file has existed and been modified
                    if new_file_info[file]["file_mtime"] > file_info[file]["file_mtime"]:
                        file_info[file] = new_file_info[file]
                        if file not in new_update_file:
                            new_update_file.append(file)
                            have_update_file = 1
            else:
                # file not in file_info:
                new_add_file[file] = new_file_info[file]
                file_info[file] = new_file_info[file]
                have_new_file = 1

        # if peer is online, inform the peer to download/update the files
        # download
        if have_new_file == 1 and peer_status == 1:
            inform_new_file(client_sockets[0])
            have_new_file = 0
        # update
        if have_update_file == 1 and peer_status == 1:
            inform_update_file(client_sockets[0])
            have_update_file = 0
        new_update_file = []


"""
    file_downloader()

    Functions:
        1. Check requests from peer (new_file_from_peer and new_update_from_peer)
        2. Call different methods to download the file

"""


def file_downloader():
    global new_file_from_peer, new_update_from_peer
    while True:
        new_file = {}
        if new_file_from_peer:
            for index_i, value in enumerate(new_file_from_peer):
                new_file = new_file_from_peer.pop(index_i)
                download_file(new_file, client_sockets[1])
        if new_update_from_peer:
            for index_i, value in enumerate(new_update_from_peer):
                new_file = new_update_from_peer.pop(index_i)
            if new_file:
                update_file(new_file["file_name"], client_sockets[1])


# file block
def make_file_blocks(msg, connection_socket):
    block_index = struct.unpack('!I', msg[4:8])[0]
    file_name = msg[8:].decode()
    file_block = get_file_block(file_name, block_index)
    connection_socket.send(file_block)


"""
    @Three conditions of sending files

    download_file(file, socket): Downloading new files
    update_file(file, sock): Updating the modified file
    breakpoint_resume(sock, file_name, total_file_size): Under 'update_file', Resuming from the breakpoint

"""


# download file on the client
def download_file(file, socket1):
    block_index = 0
    operation_code = 3
    file_size = file["file_info"]["file_size"]
    file_name = file["file_name"]
    file_info[file_name] = 1

    if not os.path.exists(os.path.split(file_name)[0]):
        os.mkdir(os.path.split(file_name)[0])
    rest_file_size = file_size
    total_block_number = math.ceil(file_size / block_size)

    with open(file_name, 'wb') as f:

        while rest_file_size > 0:
            if block_index <= total_block_number:
                data = struct.pack('!II', operation_code, block_index)
                encode_message = data + file_name.encode()
                data_length = len(encode_message)
                data_msg = struct.pack('!I', data_length) + encode_message
                socket1.send(data_msg)

            msg = socket1.recv(block_size * 3)
            f.write(msg)
            receive_data_size = len(msg)
            rest_file_size = rest_file_size - receive_data_size
            block_index += 1

    f.close()
    file_info[file_name] = {"file_mtime": os.path.getmtime(file_name), "file_size": os.path.getsize(file_name)}


# update file by re-sharing it
def update_file(file, socket2):
    operation_code = 3
    file_name = file
    file_info[file_name] = 1

    with open(file_name, 'rb+') as f:
        rest_file_size = block_size
        data = struct.pack('!II', operation_code, 0)
        encode_message = data + file_name.encode()
        data_length = len(encode_message)
        data_msg = struct.pack('!I', data_length) + data + file_name.encode()
        socket2.send(data_msg)

        text = b''
        while rest_file_size > 0:
            msg = socket2.recv(block_size)
            text += msg
            receive_data_size = len(msg)
            rest_file_size = rest_file_size - receive_data_size
        f.write(text)
    f.close()

    file_info[file_name] = {"file_mtime": os.path.getmtime(file_name),
                            "file_size": os.path.getsize(file_name)}

    print("Successfully update", file_name)


# For "broken files", restart file sharing
def breakpoint_resume(sock, file_name, total_file_size):
    operation_code = 3
    file_info[file_name] = 1

    # calculate the blocks required
    current_file_size = os.path.getsize(file_name)
    current_block_index = math.floor(current_file_size / block_size)
    rest_file_size = total_file_size - current_block_index * block_size
    total_block_number = math.ceil(total_file_size / block_size)
    request_block_index = current_block_index
    f = open(file_name, 'rb+')
    f.seek(current_block_index * block_size, 0)

    while rest_file_size > 0:
        if request_block_index <= total_block_number:
            data = struct.pack('!II', operation_code, request_block_index)
            encode_message = data + file_name.encode()
            data_length = len(encode_message)
            request_msg = struct.pack('!I', data_length) + encode_message
            sock.send(request_msg)

        msg = sock.recv(block_size * 3)
        f.write(msg)
        receive_data_size = len(msg)
        rest_file_size = rest_file_size - receive_data_size
        request_block_index += 1

    f.close()
    print("Resume from interruption")
    file_info[file_name] = {"file_mtime": os.path.getmtime(file_name),
                            "file_size": os.path.getsize(file_name)}


# Close the sockets and reset them
def reset_client_sockets():
    port_list.append(client_sockets[0].getsockname()[1])
    client_sockets[0].close()
    port_list.append(client_sockets[1].getsockname()[1])
    client_sockets[1].close()

    client_sockets[0] = socket(AF_INET, SOCK_STREAM)
    client_sockets[0].setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    client_sockets[0].bind(("", port_list.pop()))

    client_sockets[1] = socket(AF_INET, SOCK_STREAM)
    client_sockets[1].setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    client_sockets[1].bind(("", port_list.pop()))


def inform_peer(msg_b, connection_socket):  # local host receives message from the peer
    global peer_status
    message = json.loads(msg_b.decode())
    # print(message)
    if message["operation_code"] == 0:
        if peer_status == 1:
            # close the socket manually and restart
            peer_status = 0
            reset_client_sockets()
        client_sockets[0].connect((ip, port1))
        client_sockets[1].connect((ip, port2))
        peer_status = 1

        if message["server_operation_code"] == 1:
            local_update_new_file(message)

        if new_add_file:
            data = {
                "operation_code": 0,
                "server_operation_code": 1,
                "new_add_file": new_add_file
            }
            operation_message = json.dumps(data).encode()
            data_msg = struct.pack('!I', len(operation_message)) + operation_message
            connection_socket.send(data_msg)
        else:
            data = {
                "operation_code": 0,
                "server_operation_code": 0
            }
            operation_message = json.dumps(data).encode()
            data_msg = struct.pack('!I', len(operation_message)) + operation_message
            connection_socket.send(data_msg)

    elif message["operation_code"] == 1:
        local_update_new_file(message)

    elif message["operation_code"] == 2:
        for file in message["new_update_file"]:
            if file not in new_update_from_peer:
                new_update_from_peer.append({"file_name": file})


def detect_peer():  # peer sends the message to the local host
    global peer_status
    try:
        client_sockets[0].connect((ip, port1))
        client_sockets[1].connect((ip, port2))
    except:
        peer_status = 0
    else:
        peer_status = 1

        if new_add_file:
            data = {
                "operation_code": 0,
                "server_operation_code": 1,
                "new_add_file": new_add_file
            }
            encode_message = json.dumps(data).encode()
            data_msg = struct.pack('!I', len(encode_message)) + encode_message
            client_sockets[0].send(data_msg)
        else:
            data = {
                "operation_code": 0,
                "server_operation_code": 0
            }
            encode_message = json.dumps(data).encode()
            data_msg = struct.pack('!I', len(encode_message)) + encode_message
            client_sockets[0].send(data_msg)
        msg = client_sockets[0].recv(4)
        length = struct.unpack('!I', msg)[0]
        msg = client_sockets[0].recv(length)
        unformatted_data = json.loads(msg.decode())
        if unformatted_data["server_operation_code"] == 1:
            local_update_new_file(unformatted_data)


"""
    info_sender()

    Functions:
        1. Listen the port 
        2. Send messages to inform peers of file information change

"""


# Starting the server...
def info_sender():
    while True:
        connection_socket1, addr1 = info_socket.accept()
        t = threading.Thread(target=sub_connection_info, args=(connection_socket1,))
        t.start()


"""
    info_sender()

    Functions:
        1. Listen the port 
        2. Receive file request messages and send file blocks to the peer 

"""


# Starting the file socket..
def file_sender():
    while True:
        connection_socket2, addr2 = file_socket.accept()
        t = threading.Thread(target=sub_connection_file, args=(connection_socket2, addr2,))
        t.start()


# Sub
#
# connection for sending the file information
def sub_connection_info(connection_socket):
    while True:
        try:
            msg1 = connection_socket.recv(4)
        except:
            break
        else:
            if not msg1:
                break
            length = struct.unpack('!I', msg1)[0]
            msg1 = connection_socket.recv(length)
            inform_peer(msg1, connection_socket)


# Sub connection for sending the file blocks
def sub_connection_file(connection_socket, address):
    while True:
        try:
            # receive header length, avoid sticky packets
            msg2 = connection_socket.recv(4)
        except:
            break
        else:
            if not msg2:
                break
            header_length_b = msg2[:4]  # header length
            data_length = struct.unpack('!I', header_length_b)[0]
            msg2 = connection_socket.recv(data_length)  # data
            try:
                make_file_blocks(msg2, connection_socket)
            except:
                print(address[0], "offline")
                break


if __name__ == '__main__':
    parser = _argparse()
    ip = parser.ip

    info_sender = threading.Thread(target=info_sender)
    info_sender.start()

    file_sender = threading.Thread(target=file_sender)
    file_sender.start()

    file_scanner = threading.Thread(target=file_scanner)
    file_scanner.start()

    # Client socket 1 is used for receiving file information
    client_socket1 = socket(AF_INET, SOCK_STREAM)
    client_socket1.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    bind_port1 = port_list.pop()
    client_socket1.bind(("", bind_port1))
    # Client socket 2 is used for receiving file blocks
    client_socket2 = socket(AF_INET, SOCK_STREAM)
    client_socket2.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    bind_port2 = port_list.pop()
    client_socket2.bind(("", bind_port2))
    # Use a list to store the client sockets, in order to pass the sockets in functions
    client_sockets = [client_socket1, client_socket2]

    detect_peer()  # start sending the file
    file_downloader = threading.Thread(target=file_downloader)
    file_downloader.start()
