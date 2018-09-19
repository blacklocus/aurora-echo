PYTHON_MAIN=aurora_echo/__init__.py
FINAL_EXECUTABLE=aurora-echo
BUILD_DIR=build
VIRTUALENV=$(BUILD_DIR)/_virtualenv
VIRTUALENV_BIN=$(VIRTUALENV)/bin
ACTIVATE=$(VIRTUALENV_BIN)/activate
PYTHON_INTERPRETER=python3

.PHONY: all clean build lint

all: clean build

clean:
	@rm -rf *.pyc
	@echo "Project .pyc's removed."
	@rm -rf $(BUILD_DIR)
	@echo "Build directory removed."

build: $(ACTIVATE)
	rm -f $(BUILD_DIR)/$(FINAL_EXECUTABLE)
	$(VIRTUALENV_BIN)/python eggsecute.py $(PYTHON_MAIN) $(BUILD_DIR)/$(FINAL_EXECUTABLE)
	chmod a+x $(BUILD_DIR)/$(FINAL_EXECUTABLE)
	echo "Package created."

lint: $(ACTIVATE)
	$(VIRTUALENV_BIN)/python setup.py flake8

$(VIRTUALENV) $(ACTIVATE) :
	@command -v virtualenv >/dev/null 2>&1 || { echo >&2 "This build requires virtualenv to be installed.  Aborting."; exit 1; }
	@mkdir -p $(BUILD_DIR)
	@if [ -d $(VIRTUALENV) ]; then \
		echo "Existing virtualenv found. Skipping virtualenv creation."; \
	else \
		virtualenv -p `which $(PYTHON_INTERPRETER)` $(VIRTUALENV); \
		. $(ACTIVATE); pip install .; \
	fi