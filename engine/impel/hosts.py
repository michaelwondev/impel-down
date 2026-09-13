"""/etc/hosts의 전용 블록을 규칙에 맞춰 다시 쓴다. 블록 밖은 건드리지 않는다."""
import os
import subprocess
from typing import Callable, List, Optional

from .rules import is_valid_hostname

BEGIN = "# impel-down"
END = "# /impel-down"


def render_block(hosts: List[str]) -> str:
    valid = sorted({h for h in hosts if is_valid_hostname(h)})
    if not valid:
        return ""
    return "\n".join([BEGIN] + ["127.0.0.1 %s" % h for h in valid] + [END]) + "\n"


def replace_block(text: str, hosts: List[str]) -> str:
    """기존 블록(시작~끝 표식)을 떼고 새 블록을 붙인다.

    끝 표식이 없으면 블록 범위를 알 수 없으므로 시작 표식 줄만 지우고 나머지는 전부 보존한다.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == BEGIN), None)
    if start is not None:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() == END), None)
        if end is None:
            del lines[start]
        else:
            del lines[start:end + 1]
    body = "\n".join(lines).rstrip("\n") + "\n"
    block = render_block(hosts)
    if not block:
        return body
    return body + "\n" + block


def flush_dns() -> None:
    subprocess.run(["dscacheutil", "-flushcache"], check=False)
    subprocess.run(["killall", "-HUP", "mDNSResponder"], check=False)


def write_hosts(hosts: List[str], path: str = "/etc/hosts",
                flush: Optional[Callable[[], None]] = None) -> bool:
    """블록을 갱신한다. 내용이 바뀌었으면 True. 쓰기는 임시 파일 후 교체."""
    with open(path, encoding="utf-8") as f:
        old = f.read()
    new = replace_block(old, hosts)
    if new == old:
        return False
    tmp = path + ".impel-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
    (flush or flush_dns)()
    return True
