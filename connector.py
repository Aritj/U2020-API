import telnetlib

from typing import Dict, Callable, Any

class HuaweiMaeClient:
    mml_prompt = b'---    END'
    mae_prompt = "Escape character is '^]'."

    def __init__(self, host: str, port: int, username: str, password: str, timeout: int = 1, encoding = "ascii"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.encoding = encoding

    def connect(self):
        self.telnet = telnetlib.Telnet(self.host, self.port, self.timeout)
        try:
            self.telnet.read_until(self.mae_prompt.encode(self.encoding), timeout=self.timeout)
        except EOFError:
            pass

    def close(self):
        if self.telnet is not None:
            try:
                self.telnet.close()
            finally:
                self.telnet = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _send_and_read(self, cmd: str) -> str:
        self.telnet.write((cmd + "\r\n").encode(self.encoding))
        data = self.telnet.read_until(self.mml_prompt, timeout=self.timeout)
        return data.decode(self.encoding, errors="ignore")

    def _login(self, username: str, password: str) -> str:
        return self._send_and_read(f'LGI:OP="{username}", PWD="{password}";')

    def _reg_ne(self, ip: str) -> str:
        return self._send_and_read(f'REG NE:IP="{ip}";') 

    def _reg_vnfc(self, name: str) -> str:
        return self._send_and_read(f'REG VNFC:NAME="{name}";')

    def query_ne_dict(self, ne_dict: [str, str], vnfc: str, query: str, parse: Callable[[str], Any]) -> Dict[str, Any]:
        self._login(self.username, self.password)

        response_dict = {}

        for name, ip in ne_dict.items():
            self._reg_ne(ip)
            self._reg_vnfc(vnfc)
            output = self._send_and_read(query)
            response_dict[f'{name} ({ip})'] = parse(output)


        return response_dict