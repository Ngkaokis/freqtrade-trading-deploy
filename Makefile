GIT_SHORT_HASH ?= git-$(shell git rev-parse --short=8 HEAD)
VALUE_FILE := helm/bot-1/values.yaml
K8S_NAMESPACE := freqtrade 

.PHONY: deploy-k8s-config
deploy-k8s-config: 
	helm template freqtrade helm \
		--debug \
		-f $(VALUE_FILE) \
		-n $(K8S_NAMESPACE) \
		--set-string appVersion="$(GIT_SHORT_HASH)"

.PHONY: deploy-common-dependency
deploy-common-dependency:
	helm upgrade common common --install \
		-f common/values.yaml \
		-n freqtrade \
		--set-string appVersion="$(GIT_SHORT_HASH)"

.PHONY: deploy-bot-1
deploy-bot-1:
	helm upgrade bot-1 helm --install \
		--wait --wait-for-jobs --cleanup-on-fail \
		-f helm/bot-1/values.yaml \
		-n freqtrade \
		--set-string appVersion="$(GIT_SHORT_HASH)"


.PHONY: deploy-bot-2
deploy-bot-2:
	helm upgrade bot-2 helm --install \
		--wait --wait-for-jobs --cleanup-on-fail \
		-f helm/bot-2/values.yaml \
		-n freqtrade \
		--set-string appVersion="$(GIT_SHORT_HASH)"

.PHONY: deploy-bot-3
deploy-bot-3:
	helm upgrade bot-3 helm --install \
		--wait --wait-for-jobs --cleanup-on-fail \
		-f helm/bot-3/values.yaml \
		-n freqtrade \
		--set-string appVersion="$(GIT_SHORT_HASH)"

.PHONY: port-forwrd-bot-1
port-forwrd-bot-1:
	kubectl -n "freqtrade" port-forward deployments/bot-1 8080:8080

.PHONY: port-forwrd-bot-2
port-forwrd-bot-2:
	kubectl -n "freqtrade" port-forward deployments/bot-2 8080:8080

.PHONY: port-forwrd-bot-3
port-forwrd-bot-3:
	kubectl -n "freqtrade" port-forward deployments/bot-3 8080:8080
