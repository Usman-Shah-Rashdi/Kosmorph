import json
import kosmorph.modules  # noqa: F401
from kosmorph.core.contracts import ConflictPolicy
from kosmorph.core.registry import registry
from kosmorph.core.runner import TaskRunner
from kosmorph.core.safety import UndoJournal


def test_registry_has_core_actions():
    ids = {spec.id for spec in registry.all_actions()}
    assert "organizer.sort" in ids
    assert "convert.image" in ids
    assert "convert.structured" in ids
    assert "pdf.merge" in ids
    assert "files.batch_rename" in ids
    assert "files.find_duplicates" in ids


def test_organizer_dry_run_execute_and_undo(tmp_path):
    (tmp_path / "photo.png").write_bytes(b"fake")
    (tmp_path / "notes.md").write_text("# hello", encoding="utf-8")
    (tmp_path / "ignored.tmp").write_text("skip me", encoding="utf-8")
    (tmp_path / ".kosmorphignore").write_text("*.tmp\n", encoding="utf-8")

    runner = TaskRunner()
    preview = runner.run_sync("organizer.sort", target_dir=tmp_path, dry_run=True)
    assert preview.success
    assert len(preview.operations) == 2
    assert (tmp_path / "photo.png").exists()

    executed = runner.run_sync("organizer.sort", target_dir=tmp_path, dry_run=False)
    assert executed.success
    assert (tmp_path / "Images" / "photo.png").exists()
    assert (tmp_path / "Documents" / "notes.md").exists()
    assert (tmp_path / "ignored.tmp").exists()

    restored, skipped, _ = UndoJournal().undo_last()
    assert restored == 2
    assert skipped == 0
    assert (tmp_path / "photo.png").exists()


def test_structured_json_to_csv_and_dedup(tmp_path):
    src = tmp_path / "users.json"
    src.write_text(json.dumps([{"id": "1", "name": "Ada"}, {"id": "1", "name": "Ada"}]), encoding="utf-8")

    runner = TaskRunner()
    res = runner.run_sync("convert.structured", paths=[src], target_format="csv")
    assert res.success
    csv_path = tmp_path / "users.csv"
    assert csv_path.exists()

    dedup = runner.run_sync("tables.deduplicate_csv", path=csv_path, conflict_policy=ConflictPolicy.RENAME)
    assert dedup.success
    assert dedup.metadata["removed_rows"] == 1


def test_duplicate_finder(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"identical-content")
    (tmp_path / "b.txt").write_bytes(b"identical-content")
    (tmp_path / "c.txt").write_bytes(b"unique-content")

    runner = TaskRunner()
    res = runner.run_sync("files.find_duplicates", target_dir=tmp_path)
    assert res.success
    assert len(res.metadata["duplicates"]) == 1
