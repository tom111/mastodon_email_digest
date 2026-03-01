.PHONY: run help build print install uninstall logs

VERSION := $(shell git describe --abbrev=0 --tags 2>/dev/null || echo dev)
BUILD_DATE := "$(shell date -u)"
VCS_REF := $(shell git log -1 --pretty=%h)
NAME := $(shell pwd | xargs basename)
VENDOR := "Matt Hodges"
ORG := hodgesmr
WORKDIR := "/opt/${NAME}"

DOCKER_SCAN_SUGGEST=false

FLAGS ?=
INSTALL_DIR ?= /opt/mastodon_email_digest
LOG_FILE ?= $(HOME)/mastodon_digest.log

print:
	@echo BUILD_DATE=${BUILD_DATE}
	@echo NAME=${NAME}
	@echo ORG=${ORG}
	@echo VCS_REF=${VCS_REF}
	@echo VENDOR=${VENDOR}
	@echo VERSION=${VERSION}
	@echo WORKDIR=${WORKDIR}

.EXPORT_ALL_VARIABLES:
build:
	docker build -f Dockerfile \
	-t ${ORG}/${NAME}:${VERSION} \
	-t ${ORG}/${NAME}:latest . \
	--build-arg VERSION=${VERSION} \
	--build-arg BUILD_DATE=${BUILD_DATE} \
	--build-arg VCS_REF=${VCS_REF} \
	--build-arg NAME=${NAME} \
	--build-arg VENDOR=${VENDOR} \
	--build-arg ORG=${ORG} \
	--build-arg WORKDIR=${WORKDIR}

.EXPORT_ALL_VARIABLES:
help:
	docker run --env-file .env -it --rm -v "$(PWD)/render:${WORKDIR}/render" ${ORG}/${NAME} -h

.EXPORT_ALL_VARIABLES:
run:
	docker run --env-file .env -it --rm -v "$(PWD)/render:${WORKDIR}/render" ${ORG}/${NAME} ${FLAGS}
	python -m webbrowser -t "file://$(PWD)/render/index.html"

# Install crontab entry for daily digest at 16:00 local time
install:
	@echo "Installing crontab entry..."
	@(crontab -l 2>/dev/null | grep -v mastodon_email_digest; \
	  echo "0 16 * * * cd $(INSTALL_DIR) && $(INSTALL_DIR)/venv/bin/python run.py -n 24 -s FriendWeighted -t lax --log-file $(LOG_FILE) >> $(LOG_FILE) 2>&1") | crontab -
	@echo "Crontab entry installed. Logs will go to $(LOG_FILE)"

# Remove the crontab entry
uninstall:
	@echo "Removing crontab entry..."
	@crontab -l 2>/dev/null | grep -v mastodon_email_digest | crontab -
	@echo "Done."

# Tail the digest log
logs:
	tail -f $(LOG_FILE)
