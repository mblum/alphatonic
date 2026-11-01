from alphatonic import Study
from alphatonic.report.board import render_board


def test_study_saved_tables_reload_and_report(panel, config, tmp_path):
    study = Study(tmp_path, name="Research project")
    trial = study.evaluate(
        *panel,
        config,
        signal="Signal",
        parameters={"length": 10},
        report=True,
        context={"Universe": "Five assets"},
        note="Trial note",
    )
    fresh = Study(tmp_path, name="Research project")
    assert fresh.trial(trial.id) == trial
    assert "Signal" in fresh.render_tearsheet(trial.id)
    page = render_board(
        fresh, horizon="1", sort="cs_ic", order="desc", signal="Signal", show=["cs", "testing"]
    )
    assert trial.id in page and "p × trials" in page and "Signal" in page
    assert "Signal" in render_board(fresh, sort="invalid", horizon="invalid")
    assert trial.id not in render_board(fresh, signal="absent")
