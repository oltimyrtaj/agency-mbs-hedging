# Local inputs (optional)

Files placed here are used only when the automatic download fails, or for the history of
PIMCO's Mortgage-Backed Securities Fund before its 2024 ETF conversion (`pimco_ptrix_nav.csv`,
built by `tools/convert_pimco_nav.py`). The exact formats are in `docs/data_sources.md`.
Licensed data (CRSP, Bloomberg) placed here stays out of the public repository. Never put API keys or
passwords in this folder. Credentials go in environment variables (FRED_API_KEY, TIINGO_API_KEY).
