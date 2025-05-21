# from PySyncObj, modified

import os
import mmap
import struct
import shutil
from typing import List, Tuple, Optional

from .version import VERSION
from .pickle import to_bytes, loads, dumps


class Journal:
    def add(self, command: bytes, idx: int, term: int):
        raise NotImplementedError

    def clear(self):
        raise NotImplementedError

    def deleteEntriesFrom(self, entryFrom: int):
        raise NotImplementedError

    def deleteEntriesTo(self, entryTo: int):
        raise NotImplementedError

    def __getitem__(self, item: int):
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError

    def _destroy(self):
        raise NotImplementedError

    def setRaftCommitIndex(self, raftCommitIndex: int):
        raise NotImplementedError

    def getRaftCommitIndex(self) -> int:
        raise NotImplementedError

    def onOneSecondTimer(self):
        pass


class MemoryJournal(Journal):
    def __init__(self):
        self._journal: List[Tuple[bytes, int, int]] = []
        self._lastCommitIndex = 0

    def add(self, command: bytes, idx: int, term: int):
        self._journal.append((command, idx, term))

    def clear(self):
        self._journal.clear()

    def deleteEntriesFrom(self, entryFrom: int):
        del self._journal[entryFrom:]

    def deleteEntriesTo(self, entryTo: int):
        self._journal = self._journal[entryTo:]

    def __getitem__(self, item: int):
        return self._journal[item]

    def __len__(self):
        return len(self._journal)

    def _destroy(self):
        self.clear()

    def setRaftCommitIndex(self, raftCommitIndex: int):
        self._lastCommitIndex = raftCommitIndex

    def getRaftCommitIndex(self) -> int:
        return self._lastCommitIndex


class ResizableFile:
    def __init__(self, fileName: str, initialSize: int = 1024, resizeFactor: float = 2.0, defaultContent: Optional[bytes] = None):
        self._fileName = fileName
        self._resizeFactor = resizeFactor
        if not os.path.exists(fileName):
            with open(fileName, 'wb') as f:
                if defaultContent is not None:
                    f.write(defaultContent)
        self._f = open(fileName, 'r+b')
        self._mm = mmap.mmap(self._f.fileno(), 0)
        currSize = self._mm.size()
        if currSize < initialSize:
            try:
                self._mm.resize(initialSize)
            except SystemError:
                self._extend(initialSize - currSize)

    def write(self, offset: int, values: bytes):
        size = len(values)
        if offset + size > self._mm.size():
            try:
                new_size = int(self._mm.size() * self._resizeFactor)
                self._mm.resize(new_size)
            except SystemError:
                self._extend(new_size - self._mm.size())
        self._mm[offset:offset + size] = values

    def read(self, offset: int, size: int) -> bytes:
        return self._mm[offset:offset + size]

    def _extend(self, bytesToAdd: int):
        self._mm.flush()
        self._mm.close()
        self._f.close()
        with open(self._fileName, 'ab') as f:
            f.write(b'\0' * bytesToAdd)
        self._f = open(self._fileName, 'r+b')
        self._mm = mmap.mmap(self._f.fileno(), 0)

    def _destroy(self):
        self._mm.flush()
        self._mm.close()
        self._f.close()

    def flush(self):
        self._mm.flush()


class MetaStorer:
    def __init__(self, path: str):
        self._path = path

    def getMeta(self):
        try:
            with open(self._path, 'rb') as f:
                return loads(f.read())
        except Exception:
            return {}

    def storeMeta(self, meta):
        temp_path = self._path + '.tmp'
        with open(temp_path, 'wb') as f:
            f.write(dumps(meta))
            f.flush()
        shutil.move(temp_path, self._path)

    def getPath(self):
        return self._path


# Constantes para formato del journal
JOURNAL_FORMAT_VERSION = 1
APP_NAME = b'PYSYNCOBJ'
APP_VERSION = str.encode(VERSION)
NAME_SIZE = 24
VERSION_SIZE = 8
assert len(APP_NAME) < NAME_SIZE
assert len(APP_VERSION) < VERSION_SIZE
FIRST_RECORD_OFFSET = NAME_SIZE + VERSION_SIZE + 4 + 4
LAST_RECORD_OFFSET_OFFSET = NAME_SIZE + VERSION_SIZE + 4


class FileJournal(Journal):
    def __init__(self, journalFile: str):
        self._journalFile = ResizableFile(journalFile, defaultContent=self._getDefaultHeader())
        self._journal: List[Tuple[bytes, int, int]] = []
        self._metaStorer = MetaStorer(journalFile + '.meta')
        self._meta = self._metaStorer.getMeta()
        self._metaSaved = True
        self._currentOffset = FIRST_RECORD_OFFSET
        self._loadExistingEntries()

    def _getDefaultHeader(self) -> bytes:
        return (APP_NAME + b'\0' * (NAME_SIZE - len(APP_NAME)) +
                APP_VERSION + b'\0' * (VERSION_SIZE - len(APP_VERSION)) +
                struct.pack('<II', JOURNAL_FORMAT_VERSION, FIRST_RECORD_OFFSET))

    def _getLastRecordOffset(self) -> int:
        return struct.unpack('<I', self._journalFile.read(LAST_RECORD_OFFSET_OFFSET, 4))[0]

    def _setLastRecordOffset(self, offset: int):
        self._journalFile.write(LAST_RECORD_OFFSET_OFFSET, struct.pack('<I', offset))

    def _loadExistingEntries(self):
        currentOffset = FIRST_RECORD_OFFSET
        lastOffset = self._getLastRecordOffset()
        while currentOffset < lastOffset:
            try:
                size = struct.unpack('<I', self._journalFile.read(currentOffset, 4))[0]
                data = self._journalFile.read(currentOffset + 4, size)
                idx, term = struct.unpack('<QQ', data[:16])
                command = data[16:]
                self._journal.append((command, idx, term))
                currentOffset += size + 8
            except Exception:
                break  # Corrupción o truncamiento
        self._currentOffset = currentOffset

    def add(self, command: bytes, idx: int, term: int):
        self._journal.append((command, idx, term))
        data = struct.pack('<QQ', idx, term) + to_bytes(command)
        wrapped = struct.pack('<I', len(data)) + data + struct.pack('<I', len(data))
        self._journalFile.write(self._currentOffset, wrapped)
        self._currentOffset += len(wrapped)
        self._setLastRecordOffset(self._currentOffset)

    def clear(self):
        self._journal.clear()
        self._setLastRecordOffset(FIRST_RECORD_OFFSET)
        self._currentOffset = FIRST_RECORD_OFFSET

    def __getitem__(self, idx: int):
        return self._journal[idx]

    def __len__(self):
        return len(self._journal)

    def deleteEntriesFrom(self, entryFrom: int):
        self._journal = self._journal[:entryFrom]
        self.clear()
        for entry in self._journal:
            self.add(*entry)

    def deleteEntriesTo(self, entryTo: int):
        remaining = self._journal[entryTo:]
        self.clear()
        for entry in remaining:
            self.add(*entry)

    def _destroy(self):
        self._journalFile._destroy()

    def flush(self):
        self._journalFile.flush()

    def setRaftCommitIndex(self, raftCommitIndex: int):
        self._meta['raftCommitIndex'] = raftCommitIndex
        self._metaSaved = False

    def getRaftCommitIndex(self) -> int:
        return self._meta.get('raftCommitIndex', 1)

    def onOneSecondTimer(self):
        if not self._metaSaved:
            self._metaStorer.storeMeta(self._meta)
            self._metaSaved = True


def createJournal(journalFile: Optional[str] = None) -> Journal:
    return MemoryJournal() if journalFile is None else FileJournal(journalFile)

