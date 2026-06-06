from cart_autolab.literature.paper_downloader import PaperDownloader


class FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200, content_type: str = "application/pdf", url: str = "https://example.org/a.pdf"):
        self.content = content
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.url = url

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class FakeSession:
    headers = {}

    def get(self, url, **kwargs):
        return FakeResponse(b"%PDF-1.4\nmock")


def test_downloader_saves_direct_pdf_url(tmp_path):
    downloader = PaperDownloader(max_papers=1)
    downloader.session = FakeSession()
    result = downloader.download(
        [{"paper_id": "p1", "title": "CAR T IL15 paper", "url": "https://example.org/paper.pdf"}],
        tmp_path,
    )
    record = result["records"][0]
    assert record["status"] == "downloaded"
    assert record["artifacts"][0].endswith(".pdf")


def test_downloader_skips_mock_records(tmp_path):
    result = PaperDownloader(max_papers=1).download(
        [{"paper_id": "mock:1", "title": "Mock", "source_database": "Mock"}],
        tmp_path,
    )
    assert result["records"][0]["status"] == "skipped_mock_record"


def test_downloader_does_not_save_html_landing_page(tmp_path):
    downloader = PaperDownloader(max_papers=1)
    response = FakeResponse(
        b"<!doctype html><html><head></head><body>landing page</body></html>",
        content_type="text/html",
        url="https://example.org/article",
    )
    assert downloader._save_response(response, tmp_path / "papers", "paper", "landing", "text/html") is None
