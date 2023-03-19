# Large Efficient Flexible and Trusty (LEFT) File Sharing Program
This program is a TCP file sharing tool built using Python Socket and multithreading. It allows for efficient, flexible, and reliable file sharing between two virtual machines. The program includes features such as automatic file synchronization and breakpoint resume, implemented through a self-designed application-layer protocol with specialized message types and error handling mechanisms.

### Guideline

Install the Python package paramiko:

```shell
$ pip install paramiko
```



Modify the IP addresses in the `main.py` to yours: 

```python
PC_A_IP = ('192.168.49.128', 8001)
PC_B_IP = ('192.168.49.129', 8001)
```

Run the test script `main.py`:

```shell
$ python main.py
```

