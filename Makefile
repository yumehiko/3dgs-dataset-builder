ADDON_NAME := three_dgs_dataset_builder
DIST_DIR := dist
ZIP_PATH := $(DIST_DIR)/$(ADDON_NAME).zip

.PHONY: package test

package:
	mkdir -p $(DIST_DIR)
	rm -f $(ZIP_PATH)
	zip -r $(ZIP_PATH) $(ADDON_NAME) -x "*/__pycache__/*" "*.pyc" ".DS_Store"

test:
	pytest -q
