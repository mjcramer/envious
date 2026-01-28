#kubectl config view \
#  --raw \
#  --minify \
#  --context=docker-desktop \
#  > docker-desktop-kubeconfig

bitnami_repo := "https://charts.bitnami.com/bitnami"
argocd_repo := "https://argoproj.github.io/argo-helm"
deploy_namespace := "deploy"
seer_namespace := "seer"

help: ## Print this help message
	@echo -e "\033[34m'make'\033[0m can take the form"
	@echo -e "    \033[34mmake\033[0m [\033[36m<command>\033[0m ...]"
	@echo -e "where \033[36m<command>\033[0m can be"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

all: ##
	helm repo add argocd ${argocd_repo}
	helm repo add bitnami ${bitnami_repo}
	helm repo update
	kubectl get namespace ${deploy_namespace} || kubectl create namespace ${deploy_namespace}
	helm install argocd argo/argo-cd \
		--namespace ${deploy_namespace} \
		--values local/argocd-values.yaml
	kubectl get namespace ${seer_namespace} || kubectl create namespace ${seer_namespace}
	helm install kafka bitnami/kafka \
		--namespace ${seer_namespace} \
		--values local/kafka-values.yaml
	helm install postgres bitnami/postgresql \
		--namespace ${seer_namespace} \
		--values local/postgres-values.yaml

forward:
	kubectl port-forward service/argocd-server 8080:80 \
		--namespace ${deploy_namespace}

secret:
	kubectl get secret argocd-initial-admin-secret \
		--namespace ${deploy_namespace} \
      	--output jsonpath="{.data.password}" | base64 -d && echo
