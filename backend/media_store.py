from pathlib import Path
import shutil


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CRASH_MEDIA_ROOT = PROJECT_ROOT / "uploads" / "crash-media"


def media_dir(case_id: str) -> Path:
    path = CRASH_MEDIA_ROOT / case_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def relative_media_path(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def public_media_path(path: Path | None) -> str | None:
    relative = relative_media_path(path)
    return f"/{relative}" if relative else None


def copy_media_file(source: Path | None, destination: Path) -> Path | None:
    if source is None or not source.exists():
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def store_case_media(
    case_id: str,
    *,
    original_path: Path | None,
    key_frame_path: Path | None = None,
    thumbnail_path: Path | None = None,
    annotated_path: Path | None = None,
) -> dict[str, str | None]:
    folder = media_dir(case_id)
    original_suffix = (original_path.suffix if original_path else ".mp4") or ".mp4"
    annotated_suffix = (annotated_path.suffix if annotated_path else ".mp4") or ".mp4"

    original = copy_media_file(original_path, folder / f"original{original_suffix}")
    key_frame = copy_media_file(key_frame_path, folder / "keyframe.jpg")
    thumbnail = copy_media_file(thumbnail_path or key_frame_path, folder / "thumbnail.jpg")
    annotated = copy_media_file(annotated_path, folder / f"annotated{annotated_suffix}")

    return {
        "videoPath": relative_media_path(original),
        "keyFramePath": relative_media_path(key_frame),
        "thumbnailPath": relative_media_path(thumbnail),
        "annotatedPath": relative_media_path(annotated),
    }
