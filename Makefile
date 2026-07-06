KUBECONFIG ?= /etc/rancher/k3s/k3s.yaml
NS         := digital-twin

.PHONY: images import secrets deploy undeploy smoke fetch-now forecast-now status

images:            ## Build all container images (needs docker)
	./scripts/build-images.sh

import:            ## Import images into k3s containerd (needs sudo)
	./scripts/k3s-import-images.sh

secrets:           ## Create in-cluster secrets (random DB password)
	KUBECONFIG=$(KUBECONFIG) ./scripts/create-secrets.sh

deploy:            ## Apply all manifests
	kubectl --kubeconfig $(KUBECONFIG) apply -k deploy/k8s

undeploy:
	kubectl --kubeconfig $(KUBECONFIG) delete -k deploy/k8s

fetch-now:         ## One-off synthetic-data generation run
	kubectl --kubeconfig $(KUBECONFIG) -n $(NS) create job --from=cronjob/simulated-data-fetch data-fetch-manual-$$(date +%s)

forecast-now:      ## One-off forecasting run (needs API token secret)
	kubectl --kubeconfig $(KUBECONFIG) -n $(NS) create job --from=cronjob/simulated-forecasting forecasting-manual-$$(date +%s)

smoke:             ## End-to-end smoke test against the deployed stack
	./scripts/smoke_test.sh

status:
	kubectl --kubeconfig $(KUBECONFIG) -n $(NS) get pods,svc,cronjobs,jobs
