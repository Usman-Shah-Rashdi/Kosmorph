import json
import kosmorph.modules  # noqa: F401
from kosmorph.core.contracts import ConflictPolicy
from kosmorph.core.registry import registry
from kosmorph.core.runner import TaskRunner
from kosmorph.core.safety import UndoJournal


def test_registry_has_all_core_and_foldr_actions():
    ids = {spec.id for spec in registry.all_actions()}
    assert "organizer.sort" in ids
    assert "convert.image" in ids
    assert "convert.office_to_pdf" in ids
    assert "convert.structured" in ids
    assert "pdf.merge" in ids
    assert "files.batch_rename" in ids
    assert "files.find_duplicates" in ids
    assert "files.clean_empty_dirs" in ids


def test_foldr_organizer_categories_ignore_and_id_undo(tmp_path):
    (tmp_path / "photo.png").write_bytes(b"fake")
    (tmp_path / "model.stl").write_bytes(b"solid cube")
    (tmp_path / "notes.md").write_text("# hello", encoding="utf-8")
    (tmp_path / "ignored.tmp").write_text("skip me", encoding="utf-8")
    (tmp_path / ".kosmosignore").write_text("*.tmp\n", encoding="utf-8")

    runner = TaskRunner()
    journal = UndoJournal(journal_path=tmp_path / "history.json")

    preview = runner.run_sync("organizer.sort", target_dir=tmp_path, dry_run=True)
    assert preview.success
    assert len(preview.operations) == 3
    assert (tmp_path / "photo.png").exists()

    executed = runner.run_sync("organizer.sort", target_dir=tmp_path, dry_run=False)
    assert executed.success
    assert (tmp_path / "Images" / "photo.png").exists()
    assert (tmp_path / "3D_Models" / "model.stl").exists()
    assert (tmp_path / "Documents" / "notes.md").exists()
    assert (tmp_path / "ignored.tmp").exists()

    op_id = executed.metadata["undo_id"]
    assert op_id is not None

    restored, skipped, _ = UndoJournal().undo(operation_id=op_id)
    assert restored == 3
    assert skipped == 0
    assert (tmp_path / "photo.png").exists()
    assert not (tmp_path / "3D_Models").exists()


def test_empty_dirs_and_duplicates(tmp_path):
    empty_nested = tmp_path / "a" / "b" / "c"
    empty_nested.mkdir(parents=True)

    (tmp_path / "dup1.txt").write_bytes(b"same-data")
    (tmp_path / "dup2.txt").write_bytes(b"same-data")
    (tmp_path / "unique.txt").write_bytes(b"other-data")

    runner = TaskRunner()
    dup_res = runner.run_sync("files.find_duplicates", target_dir=tmp_path)
    assert dup_res.success
    assert len(dup_res.metadata["duplicates"]) == 1

    empty_res = runner.run_sync("files.clean_empty_dirs", target_dir=tmp_path, dry_run=False)
    assert empty_res.success
    assert not (tmp_path / "a").exists()


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
