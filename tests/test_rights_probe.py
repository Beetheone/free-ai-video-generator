"""Permissions are fixture metadata; no fixture is asserted to be real footage."""
import json

from documentary.core import Blocked
from documentary.rights_probe import inspect_rights


def fixture_page(license_name="CC BY 4.0"):
    return {"title": "File:Explicit fixture.webm", "imageinfo": [{
        "url": "https://upload.wikimedia.org/fixture.webm", "size": 20000,
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Explicit_fixture.webm",
        "extmetadata": {"LicenseShortName": {"value": license_name},
                        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0/"},
                        "Artist": {"value": "Fixture author"}}}]}


def test_permission_candidate_never_becomes_visually_verified_or_downloaded(tmp_path):
    class Web:
        def json(self, *a):
            return {"query": {"pages": {"1": fixture_page()}}}
        def get(self, *a, **k):
            raise AssertionError("Metadata probe must not download footage")
    report = inspect_rights(Web(), ["fixture query"], tmp_path)
    assert report["status"] == "CANDIDATES_REQUIRE_FRAME_MATCH"
    assert report["candidate_count"] == 1
    assert report["visual_relevance_verified"] is False and report["downloaded_bytes"] == 0
    assert "尚未下載或辨識畫面" in (tmp_path / "FOOTAGE_GAPS.md").read_text()


def test_restricted_metadata_is_a_gap_not_permission(tmp_path):
    class Web:
        def json(self, *a):
            return {"query": {"pages": {"1": fixture_page("CC BY-NC 4.0")}}}
    report = inspect_rights(Web(), ["fixture query"], tmp_path)
    assert report["status"] == "NO_SUPPORTED_LICENSED_CANDIDATES"
    assert report["candidate_count"] == 0 and report["rejected_entries"] == 1
    assert report['rejected_license_names'] == {'CC BY-NC 4.0': 1}
    assert "並不代表全網都沒有" in (tmp_path / "FOOTAGE_GAPS.md").read_text()


def test_network_failure_is_not_claimed_as_absent_rights(tmp_path):
    class Web:
        def json(self, *a):
            raise Blocked("NETWORK", "fixture-secret withheld")
    report = inspect_rights(Web(), ["fixture query"], tmp_path)
    assert report["status"] == "SOURCE_UNAVAILABLE"
    assert "fixture-secret" not in json.dumps(report)
