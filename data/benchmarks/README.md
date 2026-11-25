# Benchmarks

Public benchmark data used by the evaluation. Each benchmark lives in its own folder with its license and source link. Generated or downloaded data is never committed; only small gold files are (under `data/gold/`).

| Benchmark | How it is obtained | License and notes |
|---|---|---|
| TPC-H (scale factor 0.1) | Generated locally by DuckDB's `tpch` extension (`uv run python -m joinpilot.synth.tpch`) | The TPC-H specification and dbgen are from the [Transaction Processing Performance Council](https://www.tpc.org/tpch/). DuckDB is MIT-licensed. JoinPilot's numbers on TPC-H are not official, audited TPC-H results. |
