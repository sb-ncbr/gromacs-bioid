"""Uploaded archives are unpacked into the run's input folder (2026-11-17).

The legacy pipeline unpacked .zip uploads (src/executor/task_creator.py);
src_new accepted archives (and told users with too many files to bundle
them) but nothing unpacked them, so an archive upload failed as
missing_input. Done here, at submission, so the input check, the worker
and reruns all see the files.

Safe by construction: members are written by their base name only (no
paths, so nothing lands outside the run), folders are flattened (deposits
nest their files; input discovery reads the top level), only file types
BioID accepts are kept, links/devices/hidden files and __MACOSX are
skipped, nested archives are not unpacked, and sizes are capped while
copying (a member's declared size can lie: decompression bombs).
"""
from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path
from typing import BinaryIO, Iterator

from .security import allowed_upload

ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz")
MAX_MEMBER_BYTES = 128 * 1024 * 1024   # as one uploaded file
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_MEMBERS = 500


class ArchiveError(ValueError):
    pass


def is_archive(name: str) -> bool:
    return name.lower().endswith(ARCHIVE_SUFFIXES)


def _members(path: Path) -> Iterator[tuple[str, BinaryIO]]:
    """(member path, open stream) for every regular file in the archive."""
    if path.name.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                # symlinks in zips: unix mode in the high bits of external_attr
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    continue
                with zf.open(info) as stream:
                    yield info.filename, stream
    else:
        with tarfile.open(path, "r:*") as tf:
            for member in tf:
                if not member.isfile():  # links, devices, folders
                    continue
                stream = tf.extractfile(member)
                if stream is not None:
                    with stream:
                        yield member.name, stream


def unpack(input_dir: Path) -> list[str]:
    """Unpack every archive in input_dir next to it; returns the names written.

    ArchiveError on an unreadable archive, a size or count above the limits,
    or two members (or a member and an upload) with the same file name.
    """
    written: list[str] = []
    total = 0
    taken = {p.name for p in input_dir.iterdir()}
    for archive in sorted(p for p in input_dir.iterdir() if p.is_file() and is_archive(p.name)):
        try:
            for member_path, stream in _members(archive):
                parts = member_path.replace("\\", "/").split("/")
                name = parts[-1]
                if (not name or name.startswith(".") or "__MACOSX" in parts
                        or is_archive(name) or not allowed_upload(name)):
                    continue
                if name in taken:
                    raise ArchiveError(
                        f"'{name}' appears twice (in {archive.name} and elsewhere); "
                        "file names must be unique once folders are flattened.")
                if len(written) >= MAX_MEMBERS:
                    raise ArchiveError(f"{archive.name}: more than {MAX_MEMBERS} files.")
                target = input_dir / name
                size = 0
                with open(target, "wb") as out:
                    while chunk := stream.read(1024 * 1024):
                        size += len(chunk)
                        total += len(chunk)
                        if size > MAX_MEMBER_BYTES or total > MAX_TOTAL_BYTES:
                            out.close()
                            target.unlink(missing_ok=True)
                            raise ArchiveError(
                                f"{archive.name}: '{name}' or the archive as a whole is too large "
                                f"once unpacked (at most {MAX_MEMBER_BYTES >> 20} MiB per file, "
                                f"{MAX_TOTAL_BYTES >> 30} GiB in all).")
                        out.write(chunk)
                taken.add(name)
                written.append(name)
        except (zipfile.BadZipFile, tarfile.TarError, EOFError, OSError) as exc:
            raise ArchiveError(f"{archive.name} could not be unpacked: {exc}") from exc
    return written

