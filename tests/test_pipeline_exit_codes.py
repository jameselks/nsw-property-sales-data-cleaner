"""
Tests for the exit codes of 2-extract.py and 3-publish.py.

Phase 0 gave 1-download.py exit codes, and the cron chains the scripts with
`&&`. That protects against a failed download and nothing else: until these
tests passed, scripts 2 and 3 contained no sys.exit at all, so the chain ran on
regardless of what they did.

The failure this guards is the one that has actually been happening in
production: extract produces nothing, exits 0, and publish then re-zips
yesterday's CSV and stamps it with today's date.
"""
import os
import time
import pytest


# ------------------------------------------------- 2-extract.py exit codes ---

def test_extract_exits_non_zero_when_no_data_was_produced(extract_mod, tmp_path,
                                                          monkeypatch):
    """
    An empty result means something upstream broke - a corrupt archive, an
    empty data/, a parser that matched nothing. Exiting 0 here lets the rest of
    the chain publish whatever CSV happens to be lying around.
    """
    import pandas as pd
    monkeypatch.setattr(extract_mod, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(extract_mod, 'FINAL_CSV_PATH', str(tmp_path / 'out.csv'))
    monkeypatch.setattr(extract_mod, 'build_dataframe', lambda _: pd.DataFrame())

    with pytest.raises(SystemExit) as excinfo:
        extract_mod.main()

    assert excinfo.value.code != 0


def test_extract_exits_zero_on_a_normal_run(extract_mod, tmp_path, monkeypatch):
    """The happy path must stay quiet, or the chain never runs at all."""
    import pandas as pd
    frame = pd.DataFrame({'Property ID': ['1'], 'Purchase price': [750000]})
    monkeypatch.setattr(extract_mod, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(extract_mod, 'FINAL_CSV_PATH', str(tmp_path / 'out.csv'))
    monkeypatch.setattr(extract_mod, 'build_dataframe', lambda _: frame)

    extract_mod.main()   # must not raise SystemExit

    assert (tmp_path / 'out.csv').exists()


def test_extract_does_not_leave_a_stale_csv_behind_on_failure(extract_mod,
                                                              tmp_path, monkeypatch):
    """
    The dangerous case. Yesterday's CSV is still on disk; today's run produces
    nothing. Extract must not exit 0 and leave that file looking current.
    """
    import pandas as pd
    stale = tmp_path / 'out.csv'
    stale.write_text('Property ID\n999\n')

    monkeypatch.setattr(extract_mod, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(extract_mod, 'FINAL_CSV_PATH', str(stale))
    monkeypatch.setattr(extract_mod, 'build_dataframe', lambda _: pd.DataFrame())

    with pytest.raises(SystemExit) as excinfo:
        extract_mod.main()

    assert excinfo.value.code != 0
    # the stale file is still there - that is precisely why the exit code matters
    assert stale.read_text() == 'Property ID\n999\n'


# ------------------------------------------------- 3-publish.py exit codes ---

def test_archive_exits_non_zero_when_the_csv_is_missing(publish_mod, tmp_path,
                                                        monkeypatch):
    """Previously this branch just `return`ed, which the shell reads as success."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as excinfo:
        publish_mod.create_archives(source_csv=str(tmp_path / 'missing.csv'))

    assert excinfo.value.code != 0


def test_archive_refuses_to_publish_a_stale_csv(publish_mod, tmp_path, monkeypatch):
    """
    The 81-day production failure in miniature. The CSV exists, so the old
    existence check passed, but nothing had rewritten it for months - and it got
    republished every morning with a fresh date stamp on it.
    """
    monkeypatch.chdir(tmp_path)
    csv = tmp_path / 'stale.csv'
    csv.write_text('Property ID\n1\n')

    # backdate it well past the allowed age
    old = time.time() - (publish_mod.MAX_CSV_AGE_HOURS + 24) * 3600
    os.utime(csv, (old, old))

    with pytest.raises(SystemExit) as excinfo:
        publish_mod.create_archives(source_csv=str(csv))

    assert excinfo.value.code != 0
    assert not list(tmp_path.glob('*.zip')), 'a stale CSV must not be published'


def test_archive_publishes_a_fresh_csv(publish_mod, tmp_path, monkeypatch):
    """A CSV written by the run that just finished must sail through."""
    monkeypatch.chdir(tmp_path)
    csv = tmp_path / 'fresh.csv'
    csv.write_text('Property ID\n1\n')

    publish_mod.create_archives(source_csv=str(csv))   # must not raise

    assert (tmp_path / 'archive.zip').exists()
    assert list(tmp_path.glob('nsw-property-sales-data-updated*.zip'))


def test_publish_main_runs_checks_then_packages(publish_mod, tmp_path, monkeypatch):
    """
    The whole point of merging the two scripts: main() must not package
    anything until the checks have passed, and must package when they do.
    """
    from datetime import datetime

    monkeypatch.chdir(tmp_path)
    csv = tmp_path / 'clean.csv'
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    rows = '\n'.join(f'{i},750000,1/SP104291,{now}' for i in range(50))
    csv.write_text(
        'Property ID,Purchase price,Property legal description,'
        f'Download date / time\n{rows}\n')

    monkeypatch.setattr(publish_mod, 'FINAL_CSV_PATH', str(csv))
    monkeypatch.setattr(publish_mod, 'BASELINE_PATH', str(tmp_path / 'baseline.json'))
    monkeypatch.setattr(publish_mod, 'MIN_PLAUSIBLE_ROWS', 10)

    publish_mod.main()   # must not raise

    assert (tmp_path / 'archive.zip').exists()
    assert (tmp_path / 'baseline.json').exists()


def test_publish_main_checks_freshness_before_reading_the_csv(publish_mod, tmp_path,
                                                              monkeypatch):
    """
    A stale CSV must be rejected by main() itself, not only by create_archives().

    It must also be rejected WITHOUT reading the file - on the real dataset that
    read costs half a minute, and there is no point spending it on a file we
    already know this run did not write.
    """
    monkeypatch.chdir(tmp_path)
    csv = tmp_path / 'clean.csv'
    csv.write_text('Property ID\n1\n')
    old = time.time() - (publish_mod.MAX_CSV_AGE_HOURS + 24) * 3600
    os.utime(csv, (old, old))

    def explode(_path):
        raise AssertionError('a stale CSV must be rejected before it is read')

    monkeypatch.setattr(publish_mod, 'FINAL_CSV_PATH', str(csv))
    monkeypatch.setattr(publish_mod, 'BASELINE_PATH', str(tmp_path / 'baseline.json'))
    monkeypatch.setattr(publish_mod, 'collect_metrics', explode)

    with pytest.raises(SystemExit) as excinfo:
        publish_mod.main()

    assert excinfo.value.code != 0
    assert not list(tmp_path.glob('*.zip')), 'nothing may be packaged'
    assert not (tmp_path / 'baseline.json').exists(), 'no baseline on failure'
