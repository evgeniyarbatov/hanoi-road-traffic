PROJECT_NAME := $(shell basename $(PWD))
VENV_PATH = ~/.venv/$(PROJECT_NAME)

URL = https://download.geofabrik.de/asia/vietnam-latest.osm.pbf
COUNTRY_OSM_FILE = $$(basename $(URL))

OSM_DIR = osm
DATA_DIR = data

START_LAT = 20.994847371543745
START_LON = 105.86769532886133

all: venv install

venv:
	@python3 -m venv $(VENV_PATH)

install: venv
	@source $(VENV_PATH)/bin/activate && \
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

city:
	osmconvert $(OSM_DIR)/$(COUNTRY_OSM_FILE) \
		-B=$(OSM_DIR)/hanoi.poly \
		--complete-ways \
		--complete-multipolygons \
		-o=$(OSM_DIR)/hanoi.osm.pbf

	osmium cat --overwrite $(OSM_DIR)/hanoi.osm.pbf -o $(OSM_DIR)/hanoi.osm; 

score:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/score.py

query:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/query.py \
	--osm $(OSM_DIR)/hanoi-main-near-pedestrian-renumbered.osm \

ways:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/ways.py \
	$(OSM_DIR)/hanoi-main-near-pedestrian-renumbered.osm \
	$(DATA_DIR)/ways.csv

distance:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/distance.py \
	$(START_LAT) \
	$(START_LON) \
	$(DATA_DIR)/ways.csv;