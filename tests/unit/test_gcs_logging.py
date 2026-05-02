import src.storage.gcs as gcs


def test_gcs_unavailable_warning_only_prints_once(monkeypatch, capsys):
    monkeypatch.setattr(gcs, "_client", None)
    monkeypatch.setattr(gcs, "_client_init_attempted", False)

    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "google.cloud":
            raise RuntimeError("no adc")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert gcs.get_client() is None
    assert gcs.get_client() is None

    output = capsys.readouterr().out
    assert output.count("GCS unavailable — running in local-only mode") == 1
