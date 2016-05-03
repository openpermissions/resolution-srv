# (C) Copyright Open Permissions Platform Coalition 2015-2016
.PHONY: clean requirements test pylint html docs

SHELL                 = /bin/bash

# You should not set these variables from the command line.
# Directory that this Makfile is in
SERVICEDIR            = $(shell pwd)

# Directory containing the source code
SOURCE_DIR            = resolution

# Directory to output the test reports
TEST_REPORTS_DIR      = tests/unit/reports

# You can set these variables from the command line.
# App to build docs from python sphinx commented code
SPHINXAPIDOC          = sphinx-apidoc

# Directory to build docs in
BUILDDIR              = $(SERVICEDIR)/_build

# Service version (required for $(SPHINXAPIDOC))
SERVICE_VERSION       = 0.4.0

# Service release (required for $(SPHINXAPIDOC))
SERVICE_RELEASE       = 0.4.0

# Directory to output python in source sphinx documentation
BUILD_SOURCE_DOC_DIR  = $(BUILDDIR)/in_source

# Directory to output markdown converted docs to
BUILD_SERVICE_DOC_DIR = $(BUILDDIR)/service/html

# Directory to output markdown converted docs to
BUILD_API_DOC_DIR     = $(BUILDDIR)/api/html

# Directory to find markdown docs
DOC_DIR               = $(SERVICEDIR)/documents

# Directory to find markdown docs
MD_DOC_DIR            = $(DOC_DIR)/markdown

# Directory to find markdown docs
API_DOC_DIR           = $(DOC_DIR)/apiary

# Requirement variant to build, can be dev or prod
REQUIREMENT           = prod

ENVS                  = prod dev

# Create list of target .html file names to be created based on all .md files found in the 'doc markdown directory'
md_docs :=	$(patsubst $(MD_DOC_DIR)/%.md,$(BUILD_SERVICE_DOC_DIR)/%.html,$(wildcard $(MD_DOC_DIR)/*.md)) \
			$(BUILD_SERVICE_DOC_DIR)/README.html

# Create list of target .html file names to be created based on all .md files found in the 'doc apiary directory'
api_docs :=	$(patsubst $(API_DOC_DIR)/%.md,$(BUILD_API_DOC_DIR)/%.html,$(wildcard $(API_DOC_DIR)/*.md))

clean:
	rm -fr $(TEST_REPORTS_DIR)

# Install requirements
requirements:
	pip install -r $(SERVICEDIR)/requirements/$(REQUIREMENT).txt

# Run tests
test:
	mkdir -p $(TEST_REPORTS_DIR)
	py.test \
		-s \
		--cov $(SOURCE_DIR) tests \
		--cov-report html \
		--cov-report xml \
		--junitxml=$(TEST_REPORTS_DIR)/unit-tests-report.xml
	cloverpy $(TEST_REPORTS_DIR)/coverage.xml > $(TEST_REPORTS_DIR)/clover.xml

# Run pylint
pylint:
	mkdir -p $(TEST_REPORTS_DIR)
	@pylint $(SOURCE_DIR)/ --output-format=html > $(TEST_REPORTS_DIR)/pylint-report.html || {\
	 	echo "\npylint found some problems."\
		echo "Please refer to the report: $(TEST_REPORTS_DIR)/pylint-report.html\n";\
	 }

# Create .html docs from source code comments in python sphinx format
html:
	$(SPHINXAPIDOC) \
		-s rst \
		--full \
		-f \
		-V $(SERVICE_VERSION) \
		-R $(SERVICE_RELEASE) \
		-H $(SOURCE_DIR) \
		-A "Open Permissions Platform Coalition" \
		-o $(BUILDDIR)/rst $(SOURCE_DIR)
	cd $(BUILDDIR)/rst && PYTHONPATH=$(SERVICEDIR) make html BUILDDIR=$(BUILD_SOURCE_DOC_DIR)

# Dependencies of .html document files created from files in the 'doc directory'
$(BUILD_SERVICE_DOC_DIR)/%.html : $(MD_DOC_DIR)/%.md
	mkdir -p $(dir $@)
	grip $< --export $@

# Dependenciy of .html document files created from README.md
$(BUILD_SERVICE_DOC_DIR)/README.html : $(SERVICEDIR)/README.md
	mkdir -p $(dir $@)
	grip $< --export $@

# Create .html docs from all markdown files
md_docs: $(md_docs)
ifneq ($(wildcard $(MD_DOC_DIR)),)
# Copy dependent files required to render the views, e.g. images
	rsync \
		--exclude '*.md' \
		--exclude 'eap' \
		--exclude 'drawio' \
		-r \
		$(MD_DOC_DIR)/ $(BUILD_SERVICE_DOC_DIR)
endif

# Dependencies of .html document files created from files in the 'doc directory'
$(BUILD_API_DOC_DIR)/%.html : $(API_DOC_DIR)/%.md
	mkdir -p $(dir $@)
	apiary preview --output $@ --path $<

# Create .html docs from all apiary files
api_docs: $(api_docs)
ifneq ($(wildcard $(API_DOC_DIR)),)
# Copy dependent files required to render the views, e.g. images
	rsync \
		--exclude '*.md' \
		--exclude 'eap' \
		--exclude 'drawio' \
		-r \
		$(API_DOC_DIR)/ $(BUILD_API_DOC_DIR)
endif

# Create all docs
docs: html md_docs api_docs

# Create egg_locks
egg_locks:
	for env_type in $$(echo "$(ENVS)"); do \
		top_level="$(SERVICEDIR)/requirements/"$$env_type"_top_level.txt" ; \
		if [ -e $$top_level ]; then \
			venv_path="$(SERVICEDIR)/_"$$env_type"_" ; \
			req_file="$(SERVICEDIR)/requirements/"$$env_type".txt" ; \
			rm -rf $$venv_path ; \
			virtualenv $$venv_path ; \
			source $$venv_path"/bin/activate" ; \
			pip install -r $$top_level ; \
			echo "################################################" > $$req_file ; \
			echo "## DO NOT EDIT - AUTOMATICALLY GENERATED FILE ##" >> $$req_file ; \
			echo "################################################" >> $$req_file ; \
			pip freeze >> $$req_file ; \
			deactivate ; \
			rm -rf $$venv_path ; \
		fi; \
	done

dev_install:
	python setup.py develop
