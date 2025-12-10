VENV_PATH := .venv

PYTHON := $(VENV_PATH)/bin/python
PIP := $(VENV_PATH)/bin/pip
REQUIREMENTS := requirements.txt

venv:
	@python3 -m venv $(VENV_PATH)

install: venv
	@$(PIP) install --disable-pip-version-check -q --upgrade pip
	@$(PIP) install --disable-pip-version-check -q -r $(REQUIREMENTS)

URL = https://download.geofabrik.de/asia/vietnam-latest.osm.pbf
COUNTRY_OSM_FILE = $$(basename $(URL))

OSM_DIR = osm
DATA_DIR = data

RADIUS_KM = 30
START_LAT = 20.994847371543745
START_LON = 105.86769532886133
CIRCLE = osm/circle.poly

all: venv install

	pip install --disable-pip-version-check -q -r requirements.txt

docker:
	open -a Docker
	while ! docker info > /dev/null 2>&1; do \
		sleep 1; \
	done

	docker compose up -d

country:
	if [ ! -f $(OSM_DIR)/$(COUNTRY_OSM_FILE) ]; then \
		wget $(URL) -P $(OSM_DIR); \
	fi

circle:
	@source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/get-circle.py \
	$(START_LAT) \
	$(START_LON) \
	$(RADIUS_KM) \
	$(CIRCLE);

city:
	osmconvert $(OSM_DIR)/$(COUNTRY_OSM_FILE) \
		-B=$(CIRCLE) \
		--complete-ways \
		--complete-multipolygons \
		-o=$(OSM_DIR)/hanoi.osm.pbf
	osmium cat --overwrite $(OSM_DIR)/hanoi.osm.pbf -o $(OSM_DIR)/hanoi.osm; 

	osmium tags-filter $(OSM_DIR)/hanoi.osm.pbf \
		w/highway=motorway,primary,secondary \
		-o $(OSM_DIR)/hanoi-roads.osm.pbf \
		--overwrite
	osmium cat --overwrite $(OSM_DIR)/hanoi-roads.osm.pbf -o $(OSM_DIR)/hanoi-roads.osm; 

ways:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/ways.py \
	$(OSM_DIR)/hanoi-roads.osm \
	$(DATA_DIR)/ways.csv

distance:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/distance.py \
	$(START_LAT) \
	$(START_LON) \
	$(DATA_DIR)/ways.csv \
	$(DATA_DIR)/distance.csv;

score:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/score.py

centrality:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/centrality.py

metrics:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/metrics.py

merge:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/merge.py

select:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/select_ways.py data/merged.csv

query:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/query.py \
	data/road_segments_top_road_segments.csv --continuous

dump:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/dump.py

extract:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/extract.py

animate:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/animate.py

cleanvenv:
	@rm -rf $(VENV_PATH)
