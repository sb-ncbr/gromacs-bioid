VERSION      ?= latest
REPO         ?= cerit.io/tomsko
CONT_PREFIX  ?= gromacs-bioid-
CONTAINERS   := api worker web

# Default target: build and push all containers
.PHONY: all build-all push-all
all: build-all push-all

# Build all containers
.PHONY: build-all
build-all: $(CONTAINERS:%=build-%)

# Push all containers
.PHONY: push-all
push-all: $(CONTAINERS:%=push-%)

# Build a single container
.PHONY: build-%
build-%:
	@echo "Building $(CONT_PREFIX)$*:$(VERSION)"
	docker build -t $(REPO)/$(CONT_PREFIX)$*:$(VERSION) -f Dockerfile.$* --progress=plain .

# Push a single container
.PHONY: push-%
push-%:
	@echo "Pushing $(CONT_PREFIX)$*:$(VERSION)"
	docker push $(REPO)/$(CONT_PREFIX)$*:$(VERSION)

# Deploy all containers via Helm
.PHONY: deploy
deploy:
	@echo "Deploying all containers with tags from values.yaml"
	helm upgrade --install gmx-bioid ./gmxbioid-chart -f ./gmxbioid-chart/values.yaml -n pavlik-ns

# Retrieve last deployed version
.PHONY: last-version
last-version:
	@helm get manifest gmx-bioid -n gromacs-bioid-ns | grep "image:" | awk '{print $$2}'
