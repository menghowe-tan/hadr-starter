"""Deploy idempotence — hash logic only; the host is never contacted here."""

import json

import deploy


def make_out(tmp_path, content="page"):
    out = tmp_path / "out"
    (out / "dashboard").mkdir(parents=True)
    (out / "dashboard" / "index.html").write_text(content)
    return out


def make_data(tmp_path, out_hash=None):
    data = tmp_path / "data"
    data.mkdir()
    manifest = {"deploy_state": {"out_hash": out_hash}} if out_hash else {}
    (data / "manifest.json").write_text(json.dumps(manifest))
    return data


def test_same_content_is_a_noop(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("NETLIFY_AUTH_TOKEN", raising=False)
    out = make_out(tmp_path)
    data = make_data(tmp_path, out_hash=deploy.tree_hash(out))
    assert deploy.main(["--out", str(out), "--data", str(data)]) == 0
    assert "skipped: content unchanged" in capsys.readouterr().out


def test_changed_content_would_deploy(tmp_path, capsys):
    out = make_out(tmp_path, content="new page")
    data = make_data(tmp_path, out_hash="something-else")
    assert deploy.main(["--out", str(out), "--data", str(data), "--dry-run"]) == 0
    assert "would deploy" in capsys.readouterr().out


def test_hash_covers_paths_and_bytes(tmp_path):
    a = make_out(tmp_path / "a", content="x")
    b = make_out(tmp_path / "b", content="y")
    assert deploy.tree_hash(a) != deploy.tree_hash(b)


def test_empty_out_refuses(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert deploy.main(["--out", str(out), "--dry-run"]) == 1
