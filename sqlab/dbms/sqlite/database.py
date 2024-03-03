
import hashlib
import sqlite3

from ...database import AbstractDatabase
from ...text_tools import FAIL, OK, RESET, WARNING
from ...text_tools import repr_single

def string_hash(s):
    """ Python equivalent of the eponym SQL user-function."""
    return int(hashlib.sha256(s.encode()).hexdigest()[:10], 16)

class BitXor:
    """ Python equivalent of MySQL bit_xor aggregate function."""
    def __init__(self):
        self.result = 0

    def step(self, value):
        if value is not None:
            self.result ^= value

    def finalize(self):
        return self.result


class Database(AbstractDatabase):

    def __init__(self):
        self.cnx.create_aggregate("bit_xor", 1, BitXor)
        self.cnx.create_function("string_hash", 1, string_hash)
