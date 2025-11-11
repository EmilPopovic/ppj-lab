1:
	./scripts/test1.sh $(filter-out 1,$(MAKECMDGOALS))

2:
	./scripts/test2.sh $(filter-out 2,$(MAKECMDGOALS))

3:
	./scripts/test3.sh $(filter-out 3,$(MAKECMDGOALS))

4:
	./scripts/test4.sh $(filter-out 4,$(MAKECMDGOALS))

%:
	@:

.PHONY: 1 2 3 4
