.PHONY: all figures clean

all: main.pdf

# Figures are produced by three scripts:
#   figures/make_figures.py       -> fig0-fig12 (numbered result/robustness figures)
#   figures/make_reorg_figures.py -> showcase, headline, substrate, E2, cross-model grid
#   pilot/mech_figs.py            -> mechanism figures (E3, E6 load)
FIGS_NUMBERED = \
	figures/fig0_protocol_schematic.pdf \
	figures/fig1_inverse_correlation.pdf \
	figures/fig2_xvendor_thermal.pdf \
	figures/fig3_heatpipes_pareto.pdf \
	figures/fig4_failure_modes.pdf \
	figures/fig5_cost_pareto.pdf \
	figures/fig6_multiseed_envelopes.pdf \
	figures/fig7_stochasticity.pdf \
	figures/fig8_probe_circularity.pdf \
	figures/fig9_reference_bias.pdf \
	figures/fig10_inter_judge_scatter.pdf \
	figures/fig11_iter_pareto.pdf \
	figures/fig12_headline_multiseed.pdf

FIGS_REORG = \
	figures/fig1_showcase.pdf \
	figures/fig_headline.pdf \
	figures/fig_substrate_frontier.pdf \
	figures/fig_e2_collapse.pdf \
	figures/fig_xmodel_grid.pdf

FIGS_MECH = \
	figures/fig_mech_e3.pdf \
	figures/fig_mech_e6load.pdf

figures: $(FIGS_NUMBERED) $(FIGS_REORG) $(FIGS_MECH)

figures/phase3_data.json: figures/extract_data.py
	cd .. && python3 paper/figures/extract_data.py

$(FIGS_NUMBERED) &: figures/make_figures.py figures/phase3_data.json
	cd .. && python3 paper/figures/make_figures.py

$(FIGS_REORG) &: figures/make_reorg_figures.py figures/phase3_data.json
	cd .. && python3 paper/figures/make_reorg_figures.py

$(FIGS_MECH) &: ../pilot/mech_figs.py
	cd .. && python3 pilot/mech_figs.py

main.pdf: main.tex arxiv.sty figures
	pdflatex -interaction=nonstopmode main.tex
	pdflatex -interaction=nonstopmode main.tex

clean:
	rm -f main.aux main.log main.out main.toc main.bbl main.blg
