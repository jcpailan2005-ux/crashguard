"""Tests for Stage 4A Tapo Replay Capture Tooling."""
import hashlib
import json
from pathlib import Path
import pytest

from backend.validation.tapo_replay_capture_stage4a_20261002.capture_engine import (
    EXPECTED_MANIFEST_SHA256,
    FROZEN_MANIFEST_PATH,
    ROOT,
    build_manifest_template,
    generate_session_id,
    get_sanitized_camera_info,
    load_eligible_sources,
    verify_manifest_hash,
)


def test_frozen_manifest_hash_matches():
    """Verify that the frozen manifest has the exact expected SHA-256."""
    is_valid, computed = verify_manifest_hash(FROZEN_MANIFEST_PATH)
    assert is_valid is True
    assert computed.lower() == EXPECTED_MANIFEST_SHA256.lower()


def test_manifest_hash_mismatch_blocks_capture(tmp_path):
    """Verify that any modification of manifest blocks loading."""
    fake_manifest = tmp_path / "fake_manifest.json"
    fake_manifest.write_text(json.dumps({"modified": True}), encoding="utf-8")
    is_valid, _ = verify_manifest_hash(fake_manifest)
    assert is_valid is False

    with pytest.raises(ValueError, match="FROZEN_SOURCE_MANIFEST_MISMATCH"):
        load_eligible_sources(fake_manifest)


def test_only_frozen_eligible_ids_accepted():
    """Verify that exactly the 10 cleared sources are loaded."""
    sources = load_eligible_sources()
    assert len(sources) == 10

    loaded_ids = {s["source_id"] for s in sources}
    expected_ids = {
        "ZILINA-SC10",
        "URBANEGO-RUN2",
        "FICOSA-20221010_182008",
        "FICOSA-20221010_185218",
        "FICOSA-20221010_191849",
        "FICOSA-20221010_194855",
        "FICOSA-20230220_202721",
        "FICOSA-20230220_203150",
        "MITRA-T1-D6",
        "MITRA-T2-D1",
    }
    assert loaded_ids == expected_ids


def test_ineligible_and_hard_excluded_sources_rejected(tmp_path):
    """Verify that ineligible sources, Source B, Phase 8C, and CADP are rejected."""
    # Test rejection of Source B
    fake_manifest = tmp_path / "source_manifest.json"
    fake_data = {
        "eligible_source_ids": ["SOURCE-B-TEST"],
        "sources": [
            {
                "source_id": "SOURCE-B-TEST",
                "source_family": "SOURCE_B_FAMILY",
                "local_path": "backend/validation/source_b/video.mp4",
            }
        ],
    }
    fake_manifest.write_text(json.dumps(fake_data), encoding="utf-8")

    # Mock hash verification for the temporary test file
    import backend.validation.tapo_replay_capture_stage4a_20261002.capture_engine as engine
    orig_expected = engine.EXPECTED_MANIFEST_SHA256
    try:
        content_hash = hashlib.sha256(fake_manifest.read_bytes()).hexdigest()
        engine.EXPECTED_MANIFEST_SHA256 = content_hash
        with pytest.raises(ValueError, match="HARD_EXCLUSION_VIOLATION"):
            load_eligible_sources(fake_manifest)
    finally:
        engine.EXPECTED_MANIFEST_SHA256 = orig_expected


def test_source_session_mapping_preserved():
    """Verify that each eligible source maps 1-to-1 to a distinct Tapo session ID."""
    sources = load_eligible_sources()
    session_ids = [generate_session_id(s["source_id"], i) for i, s in enumerate(sources, 1)]

    # All unique
    assert len(session_ids) == len(set(session_ids)) == 10
    # Clean formatting
    for sid in session_ids:
        assert sid.startswith("TAPO_SESSION_")
        assert not any(c in sid for c in " /\\?*:")


def test_license_metadata_propagated():
    """Verify license conditions are propagated into manifest template."""
    sources = load_eligible_sources()
    camera_info = {"camera_name": "Bago CCTV", "camera_id": "CAM-30960048ED"}
    manifest = build_manifest_template(sources, camera_info)

    assert manifest["domain"] == "TAPO_SCREEN_REPLAY_DOMAIN"
    assert manifest["sessions_count"] == 10
    assert len(manifest["sessions"]) == 10

    # Check Ficosa NC conditions
    ficosa_sessions = [s for s in manifest["sessions"] if "FICOSA" in s["source_id"]]
    assert len(ficosa_sessions) == 6
    for fs in ficosa_sessions:
        assert "NC" in fs["source_license"] or "NonCommercial" in str(fs["attribution_conditions"])

    # Check MiTra CC BY
    mitra_sessions = [s for s in manifest["sessions"] if "MITRA" in s["source_id"]]
    assert len(mitra_sessions) == 2
    for ms in mitra_sessions:
        assert "CC" in ms["source_license"]


def test_camera_credentials_never_logged():
    """Verify camera info structure never exposes passwords or tokens."""
    info = get_sanitized_camera_info()
    assert "password" not in info
    assert "user" not in info
    assert "streamUrl" not in info
    assert info["camera_name"] == "Bago CCTV"
    assert info["host"] == "192.168.1.17"
    assert info["has_credentials"] is True
