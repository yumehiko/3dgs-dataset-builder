ADDON_NAME := three_dgs_dataset_builder
ZIP_PATH := $(ADDON_NAME).zip

.PHONY: package test

package:
	rm -f $(ZIP_PATH)
	zip -r $(ZIP_PATH) $(ADDON_NAME) -x "*/__pycache__/*" "*.pyc" ".DS_Store"

test:
	pytest -q
