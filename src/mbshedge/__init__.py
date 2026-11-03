"""Dynamic Treasury hedging of Agency MBS: shared research code.

Modules
-------
config       project root discovery, configuration, run modes, and paths
sources      data adapters (FRED, FHFA NMDB, Yahoo, Tiingo, local files), cache, and manifest
synthetic    labeled synthetic worlds used for the smoke run and simulations
prepare      raw files -> daily, weekly, and monthly panels with availability-time alignment
instruments  synthetic constant-maturity par Treasury pricing, duration, and DV01
exposure     realized and exponentially weighted empirical duration, Cochran's Q
models       forecast models and the walk-forward runner
backtest     the common position, trade, cost, and P&L engine
evaluation   risk metrics, bootstrap intervals, forecast tests, and cost verdicts
simulation   known-truth recovery studies and full-pipeline simulated worlds
freeze       experiment freeze record and test-evaluation log
claims       machine-readable claim ledger
plotting     consistent figure style and figure/table export
teaching     the deterministic mortgage-versus-Treasury teaching example
pipeline     high-level steps shared by notebooks and simulations
bundle       return-bundle packaging
"""

__version__ = "1.0.0"
