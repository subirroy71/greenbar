.PHONY: help test gate video video-demo gif clean

help:  ## show targets
	@grep -hE '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN{FS=":.*## "}{printf "  %-12s %s\n",$$1,$$2}'

test:  ## run the test suite
	pytest -q

gate:  ## run the scoped gate on this repo's own contract
	greenbar gate scoped --contract contracts/enforcement-hardening.md

video:  ## prepare NotebookLM inputs (AUDIENCE/FORMAT/MINUTES/TONE override defaults)
	python scripts/notebooklm/prepare_video.py \
		$(if $(AUDIENCE),--audience $(AUDIENCE)) $(if $(FORMAT),--format $(FORMAT)) \
		$(if $(MINUTES),--minutes $(MINUTES)) $(if $(TONE),--tone $(TONE))

video-demo:  ## same, plus a live captured CLI walkthrough as an extra source
	python scripts/notebooklm/prepare_video.py --with-demo \
		$(if $(AUDIENCE),--audience $(AUDIENCE)) $(if $(FORMAT),--format $(FORMAT)) \
		$(if $(MINUTES),--minutes $(MINUTES)) $(if $(TONE),--tone $(TONE))

gif:  ## render a real CLI GIF (needs charmbracelet/vhs: brew install vhs)
	@command -v vhs >/dev/null || { echo "vhs not installed — run: brew install vhs"; exit 1; }
	vhs scripts/notebooklm/demo.tape

clean:  ## remove build artifacts
	rm -rf build dist *.egg-info src/*.egg-info .greenbar
