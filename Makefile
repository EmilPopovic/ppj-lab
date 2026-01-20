1:
	python3 scripts/test1.py $(filter-out 1,$(MAKECMDGOALS))

2:
	python3 scripts/test2.py $(filter-out 2,$(MAKECMDGOALS))

3:
	python3 scripts/test3.py $(filter-out 3,$(MAKECMDGOALS))

4:
	python3 scripts/test4.py $(filter-out 4,$(MAKECMDGOALS))

%:
	@:

.PHONY: 1 2 3 4
