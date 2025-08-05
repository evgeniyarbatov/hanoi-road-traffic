PROJECT_NAME := $(shell basename $(PWD))
VENV_PATH = ~/.venv/$(PROJECT_NAME)

URL = https://download.geofabrik.de/asia/vietnam-latest.osm.pbf
COUNTRY_OSM_FILE = $$(basename $(URL))

OSM_DIR = osm

all: venv install

venv:
	@python3 -m venv $(VENV_PATH)

install: venv
	@source $(VENV_PATH)/bin/activate && \
	pip install --disable-pip-version-check -q -r requirements.txt

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
	w/highway=footway,pedestrian,path,cycleway,steps \
	w/foot=yes \
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

	ogr2ogr -f SQLite $(OSM_DIR)/hanoi.sqlite osm/hanoi-main-roads.geojson -nln hanoi_main_roads
	ogr2ogr -f SQLite $(OSM_DIR)/hanoi.sqlite osm/hanoi-pedestrian.geojson -nln hanoi_pedestrian -update

	rm $(OSM_DIR)/hanoi-main-near-pedestrian.geojson
	ogr2ogr -f GeoJSON $(OSM_DIR)/hanoi-main-near-pedestrian.geojson \
			$(OSM_DIR)/hanoi.sqlite \
			-dialect sqlite \
			-sql "SELECT m.* FROM hanoi_main_roads m JOIN hanoi_pedestrian p ON ST_Distance(m.geometry, p.geometry) < 10"

	ogr2ogr -f "OSM" $(OSM_DIR)/hanoi-main-near-pedestrian.osm \
	$(OSM_DIR)/hanoi-main-near-pedestrian.geojson


