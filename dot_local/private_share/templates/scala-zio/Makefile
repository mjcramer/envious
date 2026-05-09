SHELL := /usr/bin/env bash

help: ## Print this help message
	@echo -e "\033[34m'make'\033[0m can take the form"
	@echo -e "    \033[34mmake\033[0m [\033[36m<command>\033[0m ...]"
	@echo -e "where \033[36m<command>\033[0m can be"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: format
format: ## Format all Scala source files
	@sbt scalafmtAll scalafmtSbt

.PHONY: test
test: ## Run all tests
	@sbt test

.PHONY: build
build: ## Compile the project
	@sbt compile

.PHONY: run
run: ## Run the application
	@sbt run

.PHONY: docker
docker: ## Build and publish Docker image locally
	@sbt Docker/publishLocal

.PHONY: package
package: ## Build the universal package
	@sbt Universal/packageBin
