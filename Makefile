PYTHON_MAIN=aurora_echo/__init__.py
FINAL_EXECUTABLE=aurora-echo
BUILD_DIR=build
PYTHON_INTERPRETER=python3

.PHONY: all clean build

all: clean build

clean:
	@rm -rf *.pyc
	@echo "Project .pyc's removed."
	@rm -rf $(BUILD_DIR)
	@echo "Build directory removed."

build: build/_virtualenv
	@rm -f $(BUILD_DIR)/$(FINAL_EXECUTABLE)
	@sh -c '. $(BUILD_DIR)/_virtualenv/bin/activate; $(PYTHON_INTERPRETER) eggsecute.py $(PYTHON_MAIN) $(BUILD_DIR)/$(FINAL_EXECUTABLE)'
	@chmod a+x $(BUILD_DIR)/$(FINAL_EXECUTABLE)
	@echo "Package created."

build/_virtualenv:
	@command -v virtualenv >/dev/null 2>&1 || { echo >&2 "This build requires virtualenv to be installed.  Aborting."; exit 1; }
	@mkdir -p $(BUILD_DIR)
	@if [ -d $(BUILD_DIR)/_virtualenv ]; then \
		echo "Existing virtualenv found. Skipping virtualenv creation."; \
	else \
		virtualenv -p `which $(PYTHON_INTERPRETER)` $(BUILD_DIR)/_virtualenv; \
		sh -c '. $(BUILD_DIR)/_virtualenv/bin/activate; pip install .'; \
	fi