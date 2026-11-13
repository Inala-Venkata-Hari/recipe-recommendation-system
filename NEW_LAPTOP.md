# Move to another laptop

The `small-test-big-data` branch includes the current ML experiment and a self-contained
`offline_presentation/` folder with all three app snapshots, their demo datasets,
prepared inventory/offers, trained model, slides, invoices and reset scripts.
`main` and `small-test` remain separate versions; this package does not merge them.

## First setup — internet needed to install Python packages

Install Git and Python 3.11 or newer, then:

```bash
git clone --branch small-test-big-data https://github.com/Inala-Venkata-Hari/recipe-recommendation-system.git
cd recipe-recommendation-system/offline_presentation
python setup_presentation.py
python manage.py start
```

On Linux/macOS, use `python3` if `python` is unavailable. On Windows, `py` may be
used in place of `python`. The setup script creates a new local `.venv`; an old
laptop's environment is never copied. The manager finds this local interpreter.

Open `index.html`, or the three apps directly:

- Original: http://localhost:8601
- Synthetic: http://localhost:8602
- Real reference data + ML: http://localhost:8603

After setup, the package works without internet. No dataset download, model
training, API key, currency conversion or Git branch switching is required.
The bundled `presentation.pdf` can be opened without Python.

```bash
python manage.py status
python manage.py stop
python manage.py reset
python manage.py start
```

Reset only restores the package's prepared scenario copies. Reload tabs afterward.
Fixed scenario dates are deliberate: synthetic 2026-11-05, real-data 2026-11-12.
The real-data model is trained on simulated outcomes; it is not validated retail
forecasting. Price adjustment uses a pinned CPI snapshot, not a live price feed.

## What is included / excluded

Included: all source changes; trained JSON model; training code and evaluation;
USDA derived reference catalog and formulations used by the demo; synthetic data;
prepared simulated seller inventory and ML-based published offers; slides; example
invoices; source/license notes; reproducible model and offline-flow tests.

Excluded: `.venv`, caches, logs, PID state, raw downloaded third-party archives,
private credentials and the old laptop's mutable seller workspace. The reproducible
prepared workspace is included instead. USDA download links and full builders
remain available in the source. There is no promise of live retailer prices.

The root `usda_trial.py` still supports separately imported local data. For the
ready-to-run transfer, use the included `offline_presentation` manager: its dataset
is bundled, so the normal root-level ignored data folder is not required.

For the walkthrough see `offline_presentation/PRESENTATION_GUIDE.md`; ML details
are in `ML_MODEL.md`. Legacy `requirements-environment.txt` records the old laptop's
exact versions; use the portable `offline_presentation/requirements.txt` for setup.
