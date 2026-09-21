import pytest
from bootstrap_social_proxy import archive_init_command, stable_rollout_count

SOURCE = "https://github.com/delimitrou/DeathStarBench.git"
REVISION = "6ecb09706140f8730b5385c08f1386c654c3c526"


@pytest.mark.parametrize("depth", ["", "--depth 1 "])
def test_archive_command_preserves_copy_step_and_pins_revision(depth):
    original = f"git clone {depth}{SOURCE} /DeathStarBench && cp -r /DeathStarBench/src/* /dst/"

    command = archive_init_command(original, SOURCE, REVISION)

    assert "git clone" not in command
    assert f"DeathStarBench/tar.gz/{REVISION}" in command
    assert "--strip-components=1 -C /DeathStarBench" in command
    assert command.endswith("cp -r /DeathStarBench/src/* /dst/")
    assert archive_init_command(command, SOURCE, REVISION) == command


def test_archive_command_rejects_unknown_upstream_shape():
    with pytest.raises(ValueError, match="Unexpected DeathStarBench init command"):
        archive_init_command("git clone https://example.invalid/repo /tmp/repo", SOURCE, REVISION)


def test_rollout_must_remain_complete_for_multiple_polls():
    def complete(deployment):
        return deployment["ready"]

    count = stable_rollout_count([{"ready": True}, {"ready": True}], complete, 0)
    count = stable_rollout_count([{"ready": True}, {"ready": False}], complete, count)
    assert count == 0

    for expected in (1, 2, 3):
        count = stable_rollout_count([{"ready": True}, {"ready": True}], complete, count)
        assert count == expected
