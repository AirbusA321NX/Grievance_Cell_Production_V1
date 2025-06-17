# roles.py
from enum import Enum

class RoleEnum(str, Enum):
    user = "user"
    employee = "employee"
    admin = "admin"
    super_admin = "super_admin"
