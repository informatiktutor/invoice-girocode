SERVICE_DIR=/etc/systemd/system
SCRIPT_DIR=/usr/local/libexec/invoice-girocode

install: clean
	systemctl stop *.service
	mkdir -p $(SCRIPT_DIR)
	cp *.service $(SERVICE_DIR)
	cp -r service/* $(SCRIPT_DIR)
	cp -r service/.[^.]* $(SCRIPT_DIR)
	python3 -m venv $(SCRIPT_DIR)/venv
	$(SCRIPT_DIR)/venv/bin/pip install -U pip
	$(SCRIPT_DIR)/venv/bin/pip install -r ./requirements.txt
	systemctl enable --now *.service

clean:
	rm -rf $(SCRIPT_DIR)

.PHONY: install clean
