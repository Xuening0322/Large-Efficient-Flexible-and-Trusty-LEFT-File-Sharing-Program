# -*- coding: utf-8 -*-
# @Author  : Xuening Wang
# @Time    : 2021/11/27 2:37
# @File: kill.py
# @Software: PyCharm
import os
import pandas as pd


def kill_port(port):
    find_port = 'netstat -aon | findstr %s' % port
    result = os.popen(find_port)
    info = result.read().split('\n')
    data = []
    for line in info:
        if not line:
            continue
        temp = [str for str in line.split(" ") if str]
        data.append(temp)
    parser_cmd(data)


def parser_cmd(data):
    columns = ["type", "secret", "open", "status", "pid"]
    df = pd.DataFrame(data=data, columns=list(columns))
    for index in range(len(data)):
        pid = df.loc[index, 'pid']
        kill_pid(pid)


def kill_pid(pid):
    find_kill = 'taskkill -f -pid %s' % pid
    print(find_kill)
    result = os.popen(find_kill)
    print(result)


if __name__ == '__main__':

    kill_port(22001)
    kill_port(22002)
    kill_port(22003)
