# Personal Portfolio Analysis Platform Research

Research date: 2026-06-29

## Patterns Worth Building

1. Asset allocation is the primary control surface.
   SEC/Investor.gov frames allocation as splitting a portfolio among stocks, bonds, cash and other categories based on time horizon and risk tolerance. For this project, that means every report should start from target-vs-current allocation before asking AI for interpretation.

2. Rebalancing should be rules-based.
   Vanguard describes threshold rebalancing with a 5 percentage point drift example, and its rebalancing research repeatedly uses time-and-threshold rules. This matches the existing `rebalance_threshold` setting and should remain deterministic instead of being left to the model.

3. Portfolio X-Ray style reporting is more useful than generic fund commentary.
   Morningstar describes Portfolio X-Ray as evaluating holdings from multiple angles, including asset allocation, exposure, overlap, sector and structure. This project cannot fully look through every Chinese fund yet, but it can start with asset class, concentration, top holdings by value, and QDII/equity/cash exposure.

4. Concentration risk deserves a first-class section.
   FINRA's concentration-risk guidance stresses diversification across and within major asset classes. For a personal fund portfolio, top-3 holding weight and largest single holding are simple, actionable proxies.

5. AI should explain, challenge and sequence actions.
   The model should not invent calculations. It should consume structured diagnostics, check whether rule-based rebalancing fits the current market signals, and produce a conservative execution plan.

## Sources

- Vanguard, "Rebalancing your portfolio": https://investor.vanguard.com/investor-resources-education/portfolio-management/rebalancing-your-portfolio
- SEC/Investor.gov, "Beginners' Guide to Asset Allocation, Diversification, and Rebalancing": https://www.investor.gov/additional-resources/general-resources/publications-research/info-sheets/beginners-guide-asset
- Morningstar, "X-Ray Help": https://www.morningstar.com/help-center/portfolio/xray
- Morningstar Developer, "Portfolio X-Ray": https://developer.morningstar.com/direct-web-services/documentation/direct-web-services/portfolio-x-ray/overview
- BlackRock, "Portfolio construction course": https://www.blackrock.com/americas-offshore/en/education/portfolio-construction
- FINRA, "Concentrate on Concentration Risk": https://www.finra.org/investors/insights/concentration-risk

