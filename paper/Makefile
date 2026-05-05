.PHONY: all figures clean

all: main.pdf

figures: figures/fig1_inverse_correlation.pdf figures/fig2_xvendor_thermal.pdf figures/fig3_heatpipes_pareto.pdf figures/fig4_failure_modes.pdf

figures/phase3_data.json: figures/extract_data.py
	cd .. && python3 paper/figures/extract_data.py

figures/%.pdf: figures/make_figures.py figures/phase3_data.json
	cd .. && python3 paper/figures/make_figures.py

main.pdf: main.tex neurips_2024.sty figures
	pdflatex -interaction=nonstopmode main.tex
	pdflatex -interaction=nonstopmode main.tex

clean:
	rm -f main.aux main.log main.out main.toc main.bbl main.blg
