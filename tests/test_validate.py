"""
Tests for the checks in 3-publish.py, the publish gate.

The gate exists because every silent failure in this project had the same
shape: the pipeline produced something, nothing complained, and the something
was wrong. These tests check both directions - that a bad dataset is stopped,
and (just as important) that a healthy one is not, because a gate that fails on
good data gets switched off within a week.
"""
import json
from datetime import datetime, timedelta

import pandas as pd
import pytest


COLUMNS = ["Property ID", "Purchase price", "Property legal description",
           "Download date / time", "Zoning"]


def _write_csv(path, rows=200, description="LOT 1 DP 123456",
               download=None, zoning="R2"):
    """Writes a small but structurally realistic cleaned CSV."""
    if download is None:
        download = datetime.now().strftime('%Y%m%d %H:%M')
    frame = pd.DataFrame({
        "Property ID": [str(i) for i in range(rows)],
        "Purchase price": ["750000"] * rows,
        "Property legal description": [description] * rows,
        "Download date / time": [download] * rows,
        "Zoning": [zoning] * rows,
    })
    frame.to_csv(path, index=False)
    return path


@pytest.fixture
def gate(publish_mod, tmp_path, monkeypatch):
    """Points the module at a scratch CSV and baseline."""
    monkeypatch.setattr(publish_mod, 'FINAL_CSV_PATH', str(tmp_path / 'clean.csv'))
    monkeypatch.setattr(publish_mod, 'BASELINE_PATH', str(tmp_path / 'baseline.json'))
    monkeypatch.setattr(publish_mod, 'MIN_PLAUSIBLE_ROWS', 10)
    return publish_mod


# ------------------------------------------------------------ happy paths ---

def test_a_healthy_dataset_passes_and_writes_a_baseline(gate, tmp_path):
    _write_csv(gate.FINAL_CSV_PATH)

    gate.main()   # must not raise SystemExit

    baseline = json.loads((tmp_path / 'baseline.json').read_text())
    assert baseline['row_count'] == 200
    assert baseline['columns'] == COLUMNS


def test_first_run_with_no_baseline_passes(gate):
    """A gate that fails on day one is a gate nobody turns on."""
    _write_csv(gate.FINAL_CSV_PATH)
    gate.main()


def test_an_unchanged_second_run_passes(gate):
    _write_csv(gate.FINAL_CSV_PATH)
    gate.main()
    gate.main()   # same data twice must stay green


# --------------------------------------------------------- the real checks ---

def test_a_large_row_count_drop_is_stopped(gate):
    _write_csv(gate.FINAL_CSV_PATH, rows=1000)
    gate.main()

    _write_csv(gate.FINAL_CSV_PATH, rows=500)   # 50% gone
    with pytest.raises(SystemExit) as excinfo:
        gate.main()
    assert excinfo.value.code != 0


def test_a_small_row_count_drop_is_tolerated(gate):
    """The Valuer General does restate and withdraw sales."""
    _write_csv(gate.FINAL_CSV_PATH, rows=1000)
    gate.main()

    _write_csv(gate.FINAL_CSV_PATH, rows=980)   # 2%, within tolerance
    gate.main()


def test_glued_legal_descriptions_are_stopped(gate):
    """
    The A1 regression canary. This is the exact shape Phase 1 fixed:
    '1/SP104291' and '71/SP104291' concatenated into one field.
    """
    _write_csv(gate.FINAL_CSV_PATH, description="1/SP10429171/SP104291")

    with pytest.raises(SystemExit) as excinfo:
        gate.main()
    assert excinfo.value.code != 0


def test_legitimate_long_descriptions_are_not_flagged(gate):
    """
    Guards the mistake this canary replaced. A ">70 characters" rule was
    specified originally, but 85,570 real rows legitimately exceed it - pre-2001
    records hold the whole description in one field. That rule would have failed
    every single run.
    """
    long_but_valid = ("LOT 167 DP 729325.(CLOSED RD) BEING THE WHOLE OF THE LAND "
                      "IN CERTIFICATE OF TITLE VOLUME 1234 FOLIO 567 TOGETHER "
                      "WITH RIGHT OF CARRIAGEWAY")
    assert len(long_but_valid) > 70
    _write_csv(gate.FINAL_CSV_PATH, description=long_but_valid)
    gate.main()


def test_pre_2001_dimension_text_is_not_flagged(gate):
    """
    The specific false positives that ruled out the looser candidate patterns:
    '[A-Z]{2}\\d+/' fires on 5,932 legitimate rows like these.
    """
    for description in ["111//255589 DIMENSIONS: FRONT: DP255589A ARC12/31.27X40.87/29.49",
                        "140//755691 PH BROADWATER POR 140 CP38/2 LEASE TYPE: CP",
                        "36, 37/B/8957 LOTS 36/37 SEC B DP 8957 IRR100/CKX49.68/64.31"]:
        _write_csv(gate.FINAL_CSV_PATH, description=description)
        gate.main()   # each must pass


def test_stale_data_is_stopped(gate):
    """
    The 81-day production failure. The file is perfectly well-formed; it is
    simply describing sales that stopped arriving months ago.
    """
    old = (datetime.now() - timedelta(days=120)).strftime('%Y%m%d %H:%M')
    _write_csv(gate.FINAL_CSV_PATH, download=old)

    with pytest.raises(SystemExit) as excinfo:
        gate.main()
    assert excinfo.value.code != 0


def test_normal_download_lag_is_tolerated(gate):
    """
    1-download.py deliberately skips the most recent 14 days and the files are
    weekly, so ~21 days behind is healthy. Failing on that would cry wolf daily.
    """
    lagging = (datetime.now() - timedelta(days=21)).strftime('%Y%m%d %H:%M')
    _write_csv(gate.FINAL_CSV_PATH, download=lagging)
    gate.main()


def test_a_column_disappearing_is_stopped(gate):
    _write_csv(gate.FINAL_CSV_PATH)
    gate.main()

    frame = pd.read_csv(gate.FINAL_CSV_PATH, dtype=str)
    frame.drop(columns=['Zoning']).to_csv(gate.FINAL_CSV_PATH, index=False)

    with pytest.raises(SystemExit) as excinfo:
        gate.main()
    assert excinfo.value.code != 0


def test_a_column_emptying_out_is_stopped(gate):
    """A field moving position in the source layout looks exactly like this."""
    _write_csv(gate.FINAL_CSV_PATH, rows=1000)
    gate.main()

    frame = pd.read_csv(gate.FINAL_CSV_PATH, dtype=str)
    frame.loc[frame.index[:900], 'Zoning'] = None   # 90% null, was 0%
    frame.to_csv(gate.FINAL_CSV_PATH, index=False)

    with pytest.raises(SystemExit) as excinfo:
        gate.main()
    assert excinfo.value.code != 0


def test_a_missing_csv_is_stopped(gate):
    with pytest.raises(SystemExit) as excinfo:
        gate.main()
    assert excinfo.value.code != 0


def test_an_effectively_empty_csv_is_stopped(gate):
    _write_csv(gate.FINAL_CSV_PATH, rows=2)   # below MIN_PLAUSIBLE_ROWS

    with pytest.raises(SystemExit) as excinfo:
        gate.main()
    assert excinfo.value.code != 0


# ------------------------------------------------------------- robustness ---

def test_a_corrupt_baseline_does_not_block_a_good_run(gate, tmp_path):
    """
    A damaged baseline is our problem, not the dataset's. Failing here would
    block publishing over a file we can simply rewrite.
    """
    (tmp_path / 'baseline.json').write_text('{not valid json')
    _write_csv(gate.FINAL_CSV_PATH)

    gate.main()

    assert json.loads((tmp_path / 'baseline.json').read_text())['row_count'] == 200


def test_failure_does_not_overwrite_the_baseline(gate, tmp_path):
    """
    The baseline must keep describing the last GOOD run. Overwriting it with a
    bad one would let the next run compare against garbage and pass.
    """
    _write_csv(gate.FINAL_CSV_PATH, rows=1000)
    gate.main()

    _write_csv(gate.FINAL_CSV_PATH, rows=100)
    with pytest.raises(SystemExit):
        gate.main()

    assert json.loads((tmp_path / 'baseline.json').read_text())['row_count'] == 1000
