# Command-line reference

The `alphatonic` command lists or serves saved study trials. It does not evaluate input files; run
evaluations through the [Python API](api.md). `python -m alphatonic` runs the same command.

## List trials

```sh
alphatonic list DIRECTORY [--horizon N] [--sort COLUMN] [--ascending | --descending] [--limit N]
```

| Option | Behaviour |
| --- | --- |
| `DIRECTORY` | Study directory. |
| `--horizon N` | Horizon in bars. Defaults to the smallest saved horizon. |
| `--sort COLUMN` | Board column, such as `adjusted_p`. Defaults to `created_at`. |
| `--ascending`, `--descending` | Override the sort direction. Default direction depends on the column; see below. Missing values come last. |
| `--limit N` | Maximum rows to print; default 20. |

`created_at`, `assets`, `cs_ic`, `cs_z`, `ts_ic`, `ts_cosine`, `ts_timing` and `trials` sort
descending by default. Other sortable columns use ascending order. `parameters` cannot be used as a
sort column. With no `--sort`, trials appear newest first.

The output includes signal, sample, cross-sectional IC and z-statistic, adjusted p-value,
time-series IC and family trial count. Unavailable values appear as a dash. Records that cannot be
read are reported after the table.

## Serve a study

```sh
alphatonic serve DIRECTORY [--host ADDRESS] [--port N] [--name NAME]
```

| Option | Behaviour |
| --- | --- |
| `DIRECTORY` | Study directory. |
| `--host ADDRESS` | Listen address; default `127.0.0.1` (this machine only). |
| `--port N` | Port; default 8000. |
| `--name NAME` | Study name shown on the page and in the tearsheets the server draws. |

Serving requires the `report` extra. Open `http://127.0.0.1:8000` with the defaults. The page links
to trial tearsheets and records, and reloads saved records on each request. A tearsheet that the
study did not store is drawn from the trial's tables when you open it. `/study.json` provides
the [JSON board](results.md#json-documents). Press Ctrl+C in the terminal to stop the server.

For a complete workflow, see [keep every trial in a study](../how-to/run-a-study.md).
