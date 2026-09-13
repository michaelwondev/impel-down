from impel.hosts import BEGIN, END, render_block, replace_block, write_hosts

BASE = "127.0.0.1\tlocalhost\n::1 localhost\n"


def test_render_block_sorted_and_validated():
    out = render_block(["b.example", "a.example", "bad host", "x.example/path"])
    assert out == "# impel-down\n127.0.0.1 a.example\n127.0.0.1 b.example\n# /impel-down\n"


def test_replace_block_appends_when_absent():
    assert replace_block(BASE, ["a.example"]) == BASE + "\n# impel-down\n127.0.0.1 a.example\n# /impel-down\n"


def test_replace_block_replaces_existing_keeps_rest_and_is_idempotent():
    old = BASE + "\n# impel-down\n127.0.0.1 old.example\n# /impel-down\n\n# other block\n1.2.3.4 keep.example\n"
    out = replace_block(old, ["new.example"])
    assert "old.example" not in out and "1.2.3.4 keep.example" in out
    assert out.endswith("# impel-down\n127.0.0.1 new.example\n# /impel-down\n")
    assert out.count(BEGIN) == 1 and out.count(END) == 1
    assert replace_block(out, ["new.example"]) == out


def test_replace_block_removes_when_empty():
    old = BASE + "\n# impel-down\n127.0.0.1 old.example\n# /impel-down\n"
    assert replace_block(old, []) == BASE


def test_replace_block_keeps_lines_after_dangling_begin():
    # 끝 표식이 없으면 블록 범위를 모른다 — 시작 표식만 지우고 그 뒤 줄은 전부 보존
    old = BASE + "\n# impel-down\n127.0.0.1 old.example\n1.2.3.4 user.example\n"
    out = replace_block(old, ["new.example"])
    assert "1.2.3.4 user.example" in out and "::1 localhost" in out and "127.0.0.1 old.example" in out
    assert out.count(BEGIN) == 1 and out.count(END) == 1


def test_write_hosts_atomic_flushes_and_noops_when_unchanged(tmp_path):
    p = tmp_path / "hosts"
    p.write_text(BASE, encoding="utf-8")
    flushed = []
    assert write_hosts(["a.example"], path=str(p), flush=lambda: flushed.append(1)) is True
    assert p.read_text(encoding="utf-8").endswith("127.0.0.1 a.example\n# /impel-down\n")
    assert flushed == [1] and not (tmp_path / "hosts.impel-tmp").exists()
    assert write_hosts(["a.example"], path=str(p), flush=lambda: flushed.append(2)) is False
    assert flushed == [1]
