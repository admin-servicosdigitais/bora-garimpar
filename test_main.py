from main import _is_same_domain, _normalize_text


def test_normalize_text():
    assert _normalize_text("  Engenheiro   de Dados \n Senior ") == "engenheiro de dados senior"


def test_is_same_domain_true():
    assert _is_same_domain("https://careers.example.com/jobs", "https://careers.example.com/vaga/123")


def test_is_same_domain_false():
    assert not _is_same_domain("https://careers.example.com/jobs", "https://example.com/vaga/123")
