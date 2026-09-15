.PHONY: check install uninstall

## push 前の自己点検
check:
	@python3 scripts/validate.py

## 作業中の1本を ~/.claude/skills へ写す（例: make install name=eli15）
install:
	@python3 scripts/install.py install "$(name)"

## 作業場から消す（例: make uninstall name=eli15）
uninstall:
	@python3 scripts/install.py uninstall "$(name)"
