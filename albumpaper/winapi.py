
import ctypes
from ctypes import wintypes

# https://stackoverflow.com/questions/8799646/preventing-multiple-instances-of-my-application

class MutexNotAquiredError(Exception):
    pass


class NamedMutex:
    create_mutex = ctypes.windll.kernel32.CreateMutexA
    create_mutex.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCSTR]
    create_mutex.restype = wintypes.HANDLE

    wait_for_single_object = ctypes.windll.kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait_for_single_object.restype = wintypes.DWORD

    release_mutex = ctypes.windll.kernel32.ReleaseMutex
    release_mutex.argtypes = [wintypes.HANDLE]
    release_mutex.restype = wintypes.BOOL

    close_handle = ctypes.windll.kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    def __init__(self, name: bytes):
        self.handle = self.create_mutex(None, False, name)
        if self.wait_for_single_object(self.handle, 0) != 0:
            raise MutexNotAquiredError

    def release(self):
        self.release_mutex(self.handle)
        self.close_handle(self.handle)


# https://stackoverflow.com/a/6156606/7274182
# https://docs.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-system_power_status
class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ('ACLineStatus', wintypes.BYTE),
        ('BatteryFlag', wintypes.BYTE),
        ('BatteryLifePercent', wintypes.BYTE),
        ('SystemStatusFlag', wintypes.BYTE),
        ('BatteryLifeTime', wintypes.DWORD),
        ('BatteryFullLifeTime', wintypes.DWORD),
    ]

def battery_saver_enabled() -> bool:
    SYSTEM_POWER_STATUS_P = ctypes.POINTER(SYSTEM_POWER_STATUS)

    GetSystemPowerStatus = ctypes.windll.kernel32.GetSystemPowerStatus
    GetSystemPowerStatus.argtypes = [SYSTEM_POWER_STATUS_P]
    GetSystemPowerStatus.restype = wintypes.BOOL

    status = SYSTEM_POWER_STATUS()

    return bool(status.SystemStatusFlag)

print(battery_saver_enabled())