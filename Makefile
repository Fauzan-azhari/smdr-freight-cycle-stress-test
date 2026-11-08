PY ?= .venv/bin/python
export PYTHONPATH := src

.PHONY: all data deck registry excel paper test
all: data deck registry excel paper test   ## bangun ulang seluruh rantai dan uji

data:       ## 01_raw -> 03_canonical -> 04_marts
	$(PY) -m smdr.raw_export
	$(PY) -m smdr.fs_ingest
	$(PY) -m smdr.fs_checks
	$(PY) -m smdr.macro_ingest
	$(PY) -m smdr.macro_checks
	$(PY) -m smdr.baseline
	$(PY) -m smdr.marts

deck:       ## data dan 8 slide (menulis data/00_registry/deck_dependencies.csv)
	cd deck_v5 && $(PY) data.py && $(PY) slides.py

registry:   ## sources, lineage, kamus, kontrak skema
	$(PY) -m smdr.registry

excel:      ## model Excel berumus hidup (butuh LibreOffice untuk verifikasi)
	$(PY) -m smdr.excel_model

paper:      ## naskah notebooks/paper.ipynb dan paper.html
	$(PY) notebooks/build_paper.py

test:
	$(PY) -m unittest discover -s tests
