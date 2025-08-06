PROJECT_NAME := $(shell basename $(PWD))
VENV_PATH = ~/.venv/$(PROJECT_NAME)

URL = https://download.geofabrik.de/asia/vietnam-latest.osm.pbf
COUNTRY_OSM_FILE = $$(basename $(URL))

OSM_DIR = osm
DATA_DIR = data

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
	osmconvert $(OSM_DIR)/$(COUNTRY_OSM_FILE) -B=$(OSM_DIR)/hanoi.poly -o=$(OSM_DIR)/hanoi.osm.pbf;

	osmium tags-filter $(OSM_DIR)/hanoi.osm.pbf \
	w/highway=motorway,primary,secondary,tertiary,trunk \
	-o $(OSM_DIR)/hanoi-main-roads.osm.pbf \
	--overwrite

	osmium tags-filter $(OSM_DIR)/hanoi.osm.pbf \
	w/highway=footway \
	w/highway=pedestrian \
	w/highway=steps \
	-o $(OSM_DIR)/hanoi-pedestrian.osm.pbf \
	--overwrite

	osmium cat --overwrite $(OSM_DIR)/hanoi-main-roads.osm.pbf \
	-o $(OSM_DIR)/hanoi-main-roads.osm; 
	osmium cat --overwrite $(OSM_DIR)/hanoi-pedestrian.osm.pbf \
	-o $(OSM_DIR)/hanoi-pedestrian.osm; 

roads:
	osmium export --overwrite $(OSM_DIR)/hanoi-main-roads.osm.pbf \
	-o $(OSM_DIR)/hanoi-main-roads.geojson
	osmium export --overwrite $(OSM_DIR)/hanoi-pedestrian.osm.pbf \
	-o $(OSM_DIR)/hanoi-pedestrian.geojson

	rm -f $(OSM_DIR)/hanoi.sqlite

	ogr2ogr -f SQLite -dsco SPATIALITE=YES \
	$(OSM_DIR)/hanoi.sqlite \
	$(OSM_DIR)/hanoi-main-roads.geojson \
	-nln hanoi_main_roads \
	-lco GEOMETRY_NAME=geometry

	ogr2ogr -f SQLite -dsco SPATIALITE=YES \
	$(OSM_DIR)/hanoi.sqlite \
	$(OSM_DIR)/hanoi-pedestrian.geojson \
	-nln hanoi_pedestrian \
	-lco GEOMETRY_NAME=geometry \
	-update

	rm -f $(OSM_DIR)/hanoi-main-near-pedestrian.geojson
	ogr2ogr -f GeoJSON $(OSM_DIR)/hanoi-main-near-pedestrian.geojson \
	$(OSM_DIR)/hanoi.sqlite \
	-dialect sqlite \
	-sql "SELECT m.* FROM hanoi_main_roads m WHERE EXISTS (SELECT 1 FROM hanoi_pedestrian p WHERE ST_Distance(m.geometry, p.geometry) < 5)"

	geojsontoosm $(OSM_DIR)/hanoi-main-near-pedestrian.geojson \
	| xmllint --format - \
	> $(OSM_DIR)/hanoi-main-near-pedestrian.osm  

	osmium renumber -o $(OSM_DIR)/hanoi-main-near-pedestrian-renumbered.osm  $(OSM_DIR)/hanoi-main-near-pedestrian.osm  

ways:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/ways.py \
	$(OSM_DIR)/hanoi-main-near-pedestrian-renumbered.osm \
	$(DATA_DIR)/ways.csv

query:
	source $(VENV_PATH)/bin/activate && \
	python3.11 scripts/query.py \
	--osm $(OSM_DIR)/hanoi-main-near-pedestrian-renumbered.osm \

