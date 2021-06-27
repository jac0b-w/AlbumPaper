#https://stackoverflow.com/questions/8799646/preventing-multiple-instances-of-my-application

import ctypes
from ctypes import wintypes

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