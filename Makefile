.DEFAULT_GOAL := help
.PHONY: help up down build rebuild logs-frontend logs-backend status seal-secret port-forward-argocd port-forward-grafana

help:                  ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Kreator make targets:\n\n"} /^[a-zA-Z_-]+:.*?##/ {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up:                    ## Bootstrap the entire stack
	./scripts/bootstrap.sh

down:                  ## Tear down cluster and registry
	./scripts/teardown.sh

build:                 ## Build and push all app images to local registry
	./scripts/build-images.sh

rebuild: build         ## Rebuild images and restart deployments
	kubectl rollout restart deployment/frontend deployment/backend

logs-frontend:         ## Tail frontend logs
	kubectl logs -l app.kubernetes.io/name=frontend -f

logs-backend:          ## Tail backend logs
	kubectl logs -l app.kubernetes.io/name=backend -f

status:                ## Show status of all ArgoCD applications
	kubectl get applications -n argocd

seal-secret:           ## Seal a secret. Usage: make seal-secret NAME=mySecret NS=default ARGS="KEY=VALUE"
	./scripts/seal-secret.sh $(NAME) $(NS) $(ARGS)

port-forward-argocd:   ## Port-forward ArgoCD UI to localhost:8080
	kubectl port-forward svc/argocd-server -n argocd 8080:80

port-forward-grafana:  ## Port-forward Grafana to localhost:3000
	kubectl port-forward svc/grafana -n observability 3000:80
