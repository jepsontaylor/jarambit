"""Atomic, immutable software receipts. This module executes no received argv."""
import json
import os
import uuid
from pathlib import Path
from .contracts import validate_receipt, require


def publish_receipt(path, receipt, case, artifacts):
    validate_receipt(receipt, case, artifacts)
    path = Path(path)
    require(not path.exists(), 'immutable receipt already exists')
    data = (json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.pending.' + str(os.getpid()) + '.' + uuid.uuid4().hex)
    linked = False
    try:
        with temp.open('xb') as output:
            output.write(data); output.flush(); os.fsync(output.fileno())
        # Atomic no-clobber publication, including competing same-name attempts.
        os.link(temp, path)
        linked = True
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        temp.unlink()
    except Exception:
        # A pending file is evidence of an incomplete attempt; retain it for diagnosis.
        if linked and temp.exists() and path.exists() and temp.stat().st_ino == path.stat().st_ino:
            path.unlink()  # remove only the just-created link; pending evidence remains
        raise
    return path
